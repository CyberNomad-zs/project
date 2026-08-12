"""TK 店铺体验分异常：总分/分项较上次任意变差 → 异常任务 + 双通道通知。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.domain import tk_anomaly
from app.domain.notify_dual import notify_dual

logger = logging.getLogger(__name__)

# 越高越好：下降=变差；越低越好：上升=变差
HIGHER_BETTER_KEYS = frozenset(
    {
        "experience_score",
        "product_satisfaction",
        "fulfillment_score",
        "customer_service_score",
        "on_time_delivery_rate",
        "on_time_rate",
        "positive_rate",
    }
)
LOWER_BETTER_KEYS = frozenset(
    {
        "cancel_rate",
        "negative_rate",
        "return_rate",
        "bad_review_rate",
        "response_hours",
        "handle_hours",
        "dissatisfaction_rate",
        "late_rate",
    }
)


def _f(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_worse(key: str, curr: float, prev: float) -> bool:
    k = key.lower()
    if k in LOWER_BETTER_KEYS or any(x in k for x in ("cancel", "negative", "return", "dissatisf", "late", "hour")):
        return curr > prev + 1e-9
    # default higher better for score-like keys
    return curr < prev - 1e-9


def classify_experience_pair(
    curr: dict[str, Any],
    prev: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    shop_ext = str(curr.get("shop_external_id") or "").strip()
    if not shop_ext:
        return []
    shop_name = str(curr.get("shop_name") or shop_ext).strip()
    if "schema-tk-smoke" in shop_name.lower() or shop_name.lower().startswith("[test]"):
        return []

    hits: list[dict[str, Any]] = []
    biz = curr.get("biz_date")
    source_url = curr.get("source_url")

    curr_score = _f(curr.get("experience_score"))
    prev_score = _f(prev.get("experience_score")) if prev else None
    if prev_score is not None and curr_score is not None and _is_worse("experience_score", curr_score, prev_score):
        drop = prev_score - curr_score
        hits.append(
            {
                "anomaly_code": "shop_experience_drop",
                "priority": "P0" if drop >= 0.5 else "P1",
                "summary": f"店铺体验分下降 · {shop_name}",
                "metric_snapshot": f"experience_score={curr_score} prev={prev_score} drop={drop:.3f}",
                "detail": f"{biz} 体验分 {curr_score} 较上次 {prev_score} 下降 {drop:.3f}",
                "current_value": curr_score,
                "current_value_label": "当前体验分",
                "compare_value": prev_score,
                "compare_value_label": "上次体验分",
                "change_magnitude": drop,
                "change_magnitude_label": "下降",
                "needs_boss_decision": drop >= 0.5,
                "description": f"体验分下降 {drop:.3f}",
                "notify_title": f"⚠️ 体验分下降 · {shop_name}",
                "notify_lines": [
                    f"店铺：{shop_name}（{shop_ext}）",
                    f"业务日：{biz}",
                    f"当前体验分：{curr_score}",
                    f"上次体验分：{prev_score}",
                    f"下降：{drop:.3f}",
                    f"链接：{source_url or '-'}",
                ],
                "dedupe_suffix": "shop_experience_drop",
            }
        )

    module_keys = [
        ("product_satisfaction", "商品满意度"),
        ("fulfillment_score", "履约物流"),
        ("customer_service_score", "客户服务"),
    ]
    worse_parts: list[str] = []
    for key, label in module_keys:
        c = _f(curr.get(key))
        p = _f(prev.get(key)) if prev else None
        if c is None or p is None:
            continue
        if _is_worse(key, c, p):
            worse_parts.append(f"{label} {p}→{c}")

    # metrics_json 子指标
    curr_m = curr.get("metrics_json") if isinstance(curr.get("metrics_json"), dict) else {}
    prev_m = prev.get("metrics_json") if prev and isinstance(prev.get("metrics_json"), dict) else {}
    for mk, cv in (curr_m or {}).items():
        if not isinstance(mk, str):
            continue
        cf = _f(cv)
        pf = _f((prev_m or {}).get(mk))
        if cf is None or pf is None:
            continue
        if _is_worse(mk, cf, pf):
            worse_parts.append(f"{mk} {pf}→{cf}")

    if worse_parts and prev:
        detail = "；".join(worse_parts[:8])
        hits.append(
            {
                "anomaly_code": "shop_experience_metric_worse",
                "priority": "P1",
                "summary": f"店铺体验分项变差 · {shop_name}",
                "metric_snapshot": detail[:400],
                "detail": f"{biz} 体验分项变差：{detail}",
                "current_value": curr_score,
                "current_value_label": "当前体验分",
                "compare_value": prev_score,
                "compare_value_label": "上次体验分",
                "change_magnitude": None,
                "change_magnitude_label": None,
                "needs_boss_decision": False,
                "description": detail[:500],
                "notify_title": f"⚠️ 体验分项变差 · {shop_name}",
                "notify_lines": [
                    f"店铺：{shop_name}（{shop_ext}）",
                    f"业务日：{biz}",
                    f"变差项：{detail}",
                    f"链接：{source_url or '-'}",
                ],
                "dedupe_suffix": "shop_experience_metric_worse",
            }
        )

    return hits


@dataclass
class ExperienceEvalStats:
    biz_date: str
    scanned: int = 0
    hit_drop: int = 0
    hit_metric: int = 0
    created_or_updated: int = 0
    notified: int = 0
    notify_skipped: int = 0
    skipped: int = 0
    missing_prev: int = 0
    errors: list[str] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "biz_date": self.biz_date,
            "scanned": self.scanned,
            "hit_drop": self.hit_drop,
            "hit_metric": self.hit_metric,
            "created_or_updated": self.created_or_updated,
            "notified": self.notified,
            "notify_skipped": self.notify_skipped,
            "skipped": self.skipped,
            "missing_prev": self.missing_prev,
            "errors": self.errors[:20],
            "samples": self.samples[:10],
        }


async def resolve_biz_date(db: AsyncSession, biz_date: date | None) -> date:
    if biz_date:
        return biz_date
    row = (await db.execute(text("SELECT MAX(biz_date) FROM tk.fact_tiktok_experience_daily"))).first()
    if row and row[0]:
        return row[0]
    return datetime.now(timezone.utc).date()


async def fetch_rows(
    db: AsyncSession, *, biz_date: date, shop_external_id: str | None = None
) -> list[dict[str, Any]]:
    clauses = ["biz_date = :biz_date"]
    params: dict[str, Any] = {"biz_date": biz_date}
    if shop_external_id:
        clauses.append("shop_external_id = :shop_external_id")
        params["shop_external_id"] = shop_external_id
    rows = (
        await db.execute(
            text(
                f"""
                SELECT id::text, shop_id::text, shop_external_id, shop_name, biz_date,
                       experience_score, product_satisfaction, fulfillment_score,
                       customer_service_score, status_label, metrics_json, source_url
                FROM tk.fact_tiktok_experience_daily
                WHERE {' AND '.join(clauses)}
                ORDER BY shop_external_id
                """
            ),
            params,
        )
    ).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        mj = d.get("metrics_json")
        if isinstance(mj, str):
            import json

            try:
                d["metrics_json"] = json.loads(mj)
            except Exception:  # noqa: BLE001
                d["metrics_json"] = {}
        out.append(d)
    return out


async def fetch_prev_map(
    db: AsyncSession, *, biz_date: date, shop_external_ids: list[str]
) -> dict[str, dict[str, Any]]:
    if not shop_external_ids:
        return {}
    rows = (
        await db.execute(
            text(
                """
                SELECT DISTINCT ON (shop_external_id)
                    shop_external_id, shop_name, biz_date,
                    experience_score, product_satisfaction, fulfillment_score,
                    customer_service_score, metrics_json, source_url
                FROM tk.fact_tiktok_experience_daily
                WHERE shop_external_id = ANY(:shops)
                  AND biz_date < :biz_date
                ORDER BY shop_external_id, biz_date DESC
                """
            ),
            {"shops": shop_external_ids, "biz_date": biz_date},
        )
    ).mappings().all()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        mj = d.get("metrics_json")
        if isinstance(mj, str):
            import json

            try:
                d["metrics_json"] = json.loads(mj)
            except Exception:  # noqa: BLE001
                d["metrics_json"] = {}
        out[str(d["shop_external_id"])] = d
    return out


async def _open_task(db: AsyncSession, dedupe_key: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text(
                """
                SELECT id::text, current_value FROM tk.fact_tk_anomaly_task
                WHERE dedupe_key = :dk AND status IN ('open', 'in_progress') LIMIT 1
                """
            ),
            {"dk": dedupe_key},
        )
    ).mappings().first()
    return dict(row) if row else None


def _should_notify(hit: dict[str, Any], existing: dict[str, Any] | None) -> bool:
    if not existing:
        return True
    curr = _f(hit.get("current_value"))
    prev = _f(existing.get("current_value"))
    if curr is None:
        return True
    if prev is None:
        return True
    # 继续恶化（分更低）再推
    return curr < prev - 0.001


async def evaluate_experience_anomalies(
    db: AsyncSession,
    *,
    biz_date: date | None = None,
    shop_external_id: str | None = None,
    project_center_task: bool = True,
    dry_run: bool = False,
    notify: bool = True,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    day = await resolve_biz_date(db, biz_date)
    stats = ExperienceEvalStats(biz_date=day.isoformat())
    rows = await fetch_rows(db, biz_date=day, shop_external_id=shop_external_id)
    stats.scanned = len(rows)
    shop_ids = [str(r["shop_external_id"]) for r in rows if r.get("shop_external_id")]
    prev_map = await fetch_prev_map(db, biz_date=day, shop_external_ids=shop_ids)
    notify_enabled = bool(notify) and bool(getattr(cfg, "tk_health_notify_feishu", True))

    for row in rows:
        shop_ext = str(row.get("shop_external_id") or "").strip()
        if not shop_ext:
            stats.skipped += 1
            continue
        prev = prev_map.get(shop_ext)
        if not prev:
            stats.missing_prev += 1
        hits = classify_experience_pair(row, prev)
        if not hits:
            stats.skipped += 1
            continue
        for hit in hits:
            code = hit["anomaly_code"]
            if code == "shop_experience_drop":
                stats.hit_drop += 1
            else:
                stats.hit_metric += 1
            dedupe = f"tiktok:{shop_ext}:{hit.get('dedupe_suffix') or code}"
            existing = await _open_task(db, dedupe)
            do_notify = notify_enabled and _should_notify(hit, existing)
            sample = {
                "shop_external_id": shop_ext,
                "anomaly_code": code,
                "will_notify": do_notify,
                "domain": "店铺体验分",
            }
            if dry_run:
                stats.samples.append(sample)
                stats.created_or_updated += 1
                if do_notify:
                    stats.notified += 1
                else:
                    stats.notify_skipped += 1
                continue
            try:
                task = await tk_anomaly.create_anomaly_task(
                    db,
                    anomaly_code=code,
                    summary=hit["summary"],
                    shop_id=row.get("shop_id"),
                    shop_external_id=shop_ext,
                    shop_name=row.get("shop_name"),
                    object_ref=shop_ext,
                    object_type="shop",
                    product_name=row.get("shop_name"),
                    priority=hit["priority"],
                    progress_note=hit["detail"],
                    metric_snapshot=hit["metric_snapshot"],
                    biz_date=day,
                    dedupe_key=dedupe,
                    source_url=row.get("source_url"),
                    project_center_task=project_center_task,
                    current_value=hit.get("current_value"),
                    current_value_label=hit.get("current_value_label"),
                    compare_value=hit.get("compare_value"),
                    compare_value_label=hit.get("compare_value_label"),
                    change_magnitude=hit.get("change_magnitude"),
                    change_magnitude_label=hit.get("change_magnitude_label"),
                    needs_boss_decision=hit.get("needs_boss_decision"),
                    description=hit.get("description"),
                )
                sample["task_id"] = task.get("id")
                stats.samples.append(sample)
                stats.created_or_updated += 1
                if do_notify:
                    try:
                        res = await notify_dual(
                            title=str(hit.get("notify_title") or hit["summary"]),
                            lines=list(hit.get("notify_lines") or []),
                            settings=cfg,
                            dry_run=False,
                        )
                        if res.get("any_sent"):
                            stats.notified += 1
                        else:
                            stats.notify_skipped += 1
                    except Exception as nexc:  # noqa: BLE001
                        stats.notify_skipped += 1
                        stats.errors.append(f"notify {shop_ext}/{code}: {nexc}")
                else:
                    stats.notify_skipped += 1
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"{shop_ext}/{code}: {exc}")

    return {**stats.as_dict(), "notify_enabled": notify_enabled, "dry_run": dry_run, "domain": "店铺体验分"}
