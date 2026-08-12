"""TK 达人健康评分 / 达人违规异常。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.domain import tk_anomaly
from app.domain.notify_dual import notify_dual

logger = logging.getLogger(__name__)


def _f(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def classify_creator_health_pair(
    curr: dict[str, Any], prev: dict[str, Any] | None
) -> list[dict[str, Any]]:
    shop_ext = str(curr.get("shop_external_id") or "").strip()
    ckey = str(curr.get("creator_key") or "").strip()
    if not shop_ext or not ckey:
        return []
    shop_name = str(curr.get("shop_name") or shop_ext).strip()
    cname = str(curr.get("creator_name") or ckey).strip()
    curr_score = _f(curr.get("health_score"))
    prev_score = _f(prev.get("health_score")) if prev else None
    if curr_score is None or prev_score is None:
        return []
    if curr_score >= prev_score:
        return []
    drop = prev_score - curr_score
    biz = curr.get("biz_date")
    return [
        {
            "anomaly_code": "creator_health_drop",
            "priority": "P0" if curr_score <= 150 or drop >= 20 else "P1",
            "summary": f"达人健康分下降 · {shop_name} · {cname}",
            "metric_snapshot": f"creator={ckey} score={curr_score} prev={prev_score} drop={drop:.0f}",
            "detail": f"{biz} 达人 {cname} 健康分 {curr_score} 较上次 {prev_score} 下降 {drop:.0f}",
            "current_value": curr_score,
            "current_value_label": "当前达人健康分",
            "compare_value": prev_score,
            "compare_value_label": "上次达人健康分",
            "change_magnitude": drop,
            "change_magnitude_label": "下降分",
            "needs_boss_decision": curr_score <= 150,
            "description": f"{cname} 健康分下降 {drop:.0f}",
            "notify_title": f"⚠️ 达人健康分下降 · {shop_name} · {cname}",
            "notify_lines": [
                f"店铺：{shop_name}（{shop_ext}）",
                f"达人：{cname}（{ckey}）",
                f"业务日：{biz}",
                f"当前：{curr_score:.0f}  上次：{prev_score:.0f}  下降：{drop:.0f}",
                f"链接：{curr.get('source_url') or '-'}",
            ],
            "creator_key": ckey,
            "creator_name": cname,
        }
    ]


@dataclass
class CreatorHealthEvalStats:
    biz_date: str = ""
    scanned: int = 0
    hit_drop: int = 0
    hit_violation: int = 0
    created_or_updated: int = 0
    notified: int = 0
    notify_skipped: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "biz_date": self.biz_date,
            "scanned": self.scanned,
            "hit_drop": self.hit_drop,
            "hit_violation": self.hit_violation,
            "created_or_updated": self.created_or_updated,
            "notified": self.notified,
            "notify_skipped": self.notify_skipped,
            "skipped": self.skipped,
            "errors": self.errors[:20],
            "samples": self.samples[:10],
        }


async def evaluate_creator_health_anomalies(
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
    if biz_date is None:
        row = (
            await db.execute(text("SELECT MAX(biz_date) FROM tk.fact_tiktok_creator_health_daily"))
        ).first()
        biz_date = row[0] if row and row[0] else datetime.now(timezone.utc).date()
    stats = CreatorHealthEvalStats(biz_date=biz_date.isoformat())
    notify_enabled = bool(notify) and bool(getattr(cfg, "tk_health_notify_feishu", True))

    clauses = ["biz_date = :biz_date"]
    params: dict[str, Any] = {"biz_date": biz_date}
    if shop_external_id:
        clauses.append("shop_external_id = :shop_external_id")
        params["shop_external_id"] = shop_external_id

    rows = (
        await db.execute(
            text(
                f"""
                SELECT id::text, shop_id::text, shop_external_id, shop_name, creator_key,
                       creator_name, creator_role, biz_date, health_score, status_label, source_url
                FROM tk.fact_tiktok_creator_health_daily
                WHERE {' AND '.join(clauses)}
                ORDER BY shop_external_id, creator_key
                """
            ),
            params,
        )
    ).mappings().all()
    stats.scanned = len(rows)

    # prev map key shop|creator
    keys = [(str(r["shop_external_id"]), str(r["creator_key"])) for r in rows]
    prev_map: dict[tuple[str, str], dict[str, Any]] = {}
    if keys:
        shop_ids = list({k[0] for k in keys})
        prev_rows = (
            await db.execute(
                text(
                    """
                    SELECT DISTINCT ON (shop_external_id, creator_key)
                        shop_external_id, creator_key, creator_name, biz_date, health_score, source_url
                    FROM tk.fact_tiktok_creator_health_daily
                    WHERE shop_external_id = ANY(:shops)
                      AND biz_date < :biz_date
                    ORDER BY shop_external_id, creator_key, biz_date DESC
                    """
                ),
                {"shops": shop_ids, "biz_date": biz_date},
            )
        ).mappings().all()
        for pr in prev_rows:
            prev_map[(str(pr["shop_external_id"]), str(pr["creator_key"]))] = dict(pr)

    for row in rows:
        d = dict(row)
        shop_ext = str(d.get("shop_external_id") or "")
        ckey = str(d.get("creator_key") or "")
        prev = prev_map.get((shop_ext, ckey))
        hits = classify_creator_health_pair(d, prev)
        if not hits:
            stats.skipped += 1
            continue
        for hit in hits:
            stats.hit_drop += 1
            dedupe = f"tiktok:{shop_ext}:{ckey}:creator_health_drop"[:200]
            existing = (
                await db.execute(
                    text(
                        """
                        SELECT id::text, current_value FROM tk.fact_tk_anomaly_task
                        WHERE dedupe_key = :dk AND status IN ('open', 'in_progress') LIMIT 1
                        """
                    ),
                    {"dk": dedupe},
                )
            ).mappings().first()
            do_notify = notify_enabled and (
                not existing
                or (
                    _f(hit.get("current_value")) is not None
                    and _f(existing.get("current_value")) is not None
                    and _f(hit["current_value"]) < _f(existing["current_value"]) - 0.01  # type: ignore[operator]
                )
                or not existing
            )
            if existing and _f(hit.get("current_value")) is not None and _f(existing.get("current_value")) is not None:
                do_notify = notify_enabled and (
                    _f(hit["current_value"]) < _f(existing["current_value"]) - 0.01  # type: ignore[operator]
                )
            elif existing:
                do_notify = False
            else:
                do_notify = notify_enabled

            sample = {
                "shop_external_id": shop_ext,
                "creator_key": ckey,
                "anomaly_code": "creator_health_drop",
                "will_notify": do_notify,
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
                    anomaly_code="creator_health_drop",
                    summary=hit["summary"],
                    shop_id=d.get("shop_id"),
                    shop_external_id=shop_ext,
                    shop_name=d.get("shop_name"),
                    object_ref=ckey,
                    object_type="creator",
                    product_name=hit.get("creator_name"),
                    priority=hit["priority"],
                    progress_note=hit["detail"],
                    metric_snapshot=hit["metric_snapshot"],
                    biz_date=biz_date,
                    dedupe_key=dedupe,
                    source_url=d.get("source_url"),
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
                    res = await notify_dual(
                        title=str(hit.get("notify_title")),
                        lines=list(hit.get("notify_lines") or []),
                        settings=cfg,
                    )
                    if res.get("any_sent"):
                        stats.notified += 1
                    else:
                        stats.notify_skipped += 1
                else:
                    stats.notify_skipped += 1
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"{shop_ext}/{ckey}: {exc}")

    # 新违规
    within = float(getattr(cfg, "tk_creator_violation_new_within_hours", 48.0) or 48.0)
    vparams: dict[str, Any] = {
        "since": datetime.now(timezone.utc) - timedelta(hours=max(1.0, within)),
    }
    vclauses = ["first_seen_at >= :since"]
    if shop_external_id:
        vclauses.append("shop_external_id = :shop_external_id")
        vparams["shop_external_id"] = shop_external_id
    vrows = (
        await db.execute(
            text(
                f"""
                SELECT id::text, shop_id::text, shop_external_id, shop_name, creator_key, creator_name,
                       violation_key, violation_type, reason, result_text, status, violation_at,
                       biz_date, source_url
                FROM tk.fact_tiktok_creator_violation
                WHERE {' AND '.join(vclauses)}
                ORDER BY first_seen_at DESC
                LIMIT 200
                """
            ),
            vparams,
        )
    ).mappings().all()

    for vr in vrows:
        shop_ext = str(vr.get("shop_external_id") or "")
        ckey = str(vr.get("creator_key") or "")
        vkey = str(vr.get("violation_key") or "")
        cname = str(vr.get("creator_name") or ckey)
        shop_name = str(vr.get("shop_name") or shop_ext)
        if not shop_ext or not ckey or not vkey:
            continue
        stats.hit_violation += 1
        dedupe = f"tiktok:{shop_ext}:{ckey}:creator_violation:{vkey}"[:200]
        exists = (
            await db.execute(
                text(
                    """
                    SELECT 1 FROM tk.fact_tk_anomaly_task
                    WHERE dedupe_key = :dk AND status IN ('open', 'in_progress') LIMIT 1
                    """
                ),
                {"dk": dedupe},
            )
        ).first()
        do_notify = notify_enabled and not exists
        lines = [
            f"店铺：{shop_name}（{shop_ext}）",
            f"达人：{cname}（{ckey}）",
            f"类型：{vr.get('violation_type') or '-'}",
            f"理由：{str(vr.get('reason') or '-')[:160]}",
            f"结果：{str(vr.get('result_text') or '-')[:120]}",
            f"状态：{vr.get('status') or '-'}",
            f"时间：{vr.get('violation_at') or vr.get('biz_date') or '-'}",
            f"链接：{vr.get('source_url') or '-'}",
        ]
        if dry_run:
            stats.created_or_updated += 1
            if do_notify:
                stats.notified += 1
            else:
                stats.notify_skipped += 1
            continue
        try:
            await tk_anomaly.create_anomaly_task(
                db,
                anomaly_code="creator_violation",
                summary=f"达人新增违规 · {shop_name} · {cname}",
                shop_id=vr.get("shop_id"),
                shop_external_id=shop_ext,
                shop_name=shop_name,
                object_ref=ckey,
                object_type="creator",
                product_name=cname,
                priority="P0",
                progress_note=str(vr.get("reason") or vkey)[:300],
                metric_snapshot=f"violation_key={vkey} type={vr.get('violation_type')}",
                biz_date=vr.get("biz_date") or biz_date,
                dedupe_key=dedupe,
                source_url=vr.get("source_url"),
                project_center_task=project_center_task,
                needs_boss_decision=True,
                description=str(vr.get("reason") or "")[:500],
                next_action="查看达人违规并跟进申诉/整改",
            )
            stats.created_or_updated += 1
            if do_notify:
                res = await notify_dual(
                    title=f"🚨 达人新增违规 · {shop_name} · {cname}",
                    lines=lines,
                    settings=cfg,
                )
                if res.get("any_sent"):
                    stats.notified += 1
                else:
                    stats.notify_skipped += 1
            else:
                stats.notify_skipped += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"v:{shop_ext}/{ckey}/{vkey}: {exc}")

    return {
        **stats.as_dict(),
        "notify_enabled": notify_enabled,
        "dry_run": dry_run,
        "domain": "达人健康",
    }
