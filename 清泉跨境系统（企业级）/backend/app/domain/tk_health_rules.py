"""TK 账号健康分异常：从 fact_tiktok_health_daily 生成 anomaly + 飞书群提醒。

规则：
  - shop_health_drop  健康分较上次快照下降（任意下降即提醒）
  - shop_health_low   健康分 ≤ 红线（默认 150）

幂等：dedupe = tiktok:{shop_ext}:{code}
飞书：自定义群机器人 webhook（FEISHU_BOT_WEBHOOK_TK_HEALTH）
"""

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


def classify_health_pair(
    curr: dict[str, Any],
    prev: dict[str, Any] | None,
    *,
    low_threshold: float = 150.0,
) -> list[dict[str, Any]]:
    """对比当日与上次健康快照，返回命中异常列表。"""
    shop_ext = str(curr.get("shop_external_id") or "").strip()
    if not shop_ext:
        return []
    shop_name = str(curr.get("shop_name") or shop_ext).strip()
    low = shop_name.lower()
    if "schema-tk-smoke" in low or low.startswith("[test]"):
        return []

    curr_score = _f(curr.get("health_score"))
    if curr_score is None:
        return []

    hits: list[dict[str, Any]] = []
    biz = curr.get("biz_date")
    status = str(curr.get("status_label") or "").strip() or None
    source_url = curr.get("source_url")

    prev_score = _f(prev.get("health_score")) if prev else None
    prev_biz = prev.get("biz_date") if prev else None

    # 1) 任意下降
    if prev_score is not None and curr_score < prev_score:
        drop = prev_score - curr_score
        pri = "P0" if curr_score <= low_threshold or drop >= 20 else "P1"
        metric = (
            f"health_score={curr_score:.0f} prev={prev_score:.0f} drop={drop:.0f} "
            f"prev_date={prev_biz} status={status or '-'}"
        )
        detail = (
            f"{biz} 健康分 {curr_score:.0f} 较上次 {prev_biz} 的 {prev_score:.0f} "
            f"下降 {drop:.0f} 分"
        )
        hits.append(
            {
                "anomaly_code": "shop_health_drop",
                "priority": pri,
                "summary": f"店铺健康分下降 · {shop_name}",
                "metric_snapshot": metric,
                "detail": detail,
                "current_value": curr_score,
                "current_value_label": "当前健康分",
                "compare_value": prev_score,
                "compare_value_label": "上次健康分",
                "change_magnitude": drop,
                "change_magnitude_label": "下降分",
                "needs_boss_decision": pri == "P0",
                "description": f"{detail} | {metric}",
                "notify_title": f"⚠️ 健康分下降 · {shop_name}",
                "notify_lines": [
                    f"店铺：{shop_name}（{shop_ext}）",
                    f"业务日：{biz}",
                    f"当前健康分：{curr_score:.0f}",
                    f"上次健康分：{prev_score:.0f}（{prev_biz}）",
                    f"下降：{drop:.0f} 分",
                    f"状态：{status or '-'}",
                    f"链接：{source_url or '-'}",
                ],
            }
        )

    # 2) 低于/等于红线（默认 150）
    if curr_score <= low_threshold:
        # 若同时下降，仍单独出一条「健康分低」，便于红线盯盘
        already_low_open_ok = True
        pri = "P0" if curr_score < low_threshold * 0.8 else "P0"
        metric = (
            f"health_score={curr_score:.0f} threshold={low_threshold:.0f} "
            f"status={status or '-'} prev={prev_score}"
        )
        detail = (
            f"{biz} 健康分 {curr_score:.0f} ≤ 红线 {low_threshold:.0f}"
            + (f"（上次 {prev_score:.0f}）" if prev_score is not None else "")
        )
        hits.append(
            {
                "anomaly_code": "shop_health_low",
                "priority": pri,
                "summary": f"店铺健康分过低 · {shop_name}",
                "metric_snapshot": metric,
                "detail": detail,
                "current_value": curr_score,
                "current_value_label": "当前健康分",
                "compare_value": low_threshold,
                "compare_value_label": "红线",
                "change_magnitude": (prev_score - curr_score) if prev_score is not None else None,
                "change_magnitude_label": "较上次下降分" if prev_score is not None else None,
                "needs_boss_decision": True,
                "description": f"{detail} | {metric}",
                "notify_title": f"🚨 健康分≤{low_threshold:.0f} · {shop_name}",
                "notify_lines": [
                    f"店铺：{shop_name}（{shop_ext}）",
                    f"业务日：{biz}",
                    f"当前健康分：{curr_score:.0f}",
                    f"红线：{low_threshold:.0f}",
                    f"上次：{prev_score if prev_score is not None else '-'}（{prev_biz or '-'}）",
                    f"状态：{status or '-'}",
                    f"链接：{source_url or '-'}",
                ],
                # 仅用于是否推送的辅助标记（低分首次或继续恶化）
                "_low_threshold": low_threshold,
                "_already_low_open_ok": already_low_open_ok,
            }
        )

    return hits


@dataclass
class HealthEvalStats:
    biz_date: str
    scanned: int = 0
    hit_drop: int = 0
    hit_low: int = 0
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
            "hit_low": self.hit_low,
            "created_or_updated": self.created_or_updated,
            "notified": self.notified,
            "notify_skipped": self.notify_skipped,
            "skipped": self.skipped,
            "missing_prev": self.missing_prev,
            "errors": self.errors[:20],
            "samples": self.samples[:10],
        }


async def resolve_health_biz_date(db: AsyncSession, biz_date: date | None) -> date:
    if biz_date:
        return biz_date
    row = (
        await db.execute(text("SELECT MAX(biz_date) FROM tk.fact_tiktok_health_daily"))
    ).first()
    if row and row[0]:
        return row[0]
    return datetime.now(timezone.utc).date()


async def fetch_health_daily_rows(
    db: AsyncSession,
    *,
    biz_date: date,
    shop_external_id: str | None = None,
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
                SELECT
                    id::text,
                    shop_id::text,
                    shop_external_id,
                    shop_name,
                    biz_date,
                    health_score,
                    late_dispatch_rate,
                    negative_feedback_rate,
                    status_label,
                    source_url
                FROM tk.fact_tiktok_health_daily
                WHERE {' AND '.join(clauses)}
                ORDER BY shop_external_id
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_prev_health_map(
    db: AsyncSession,
    *,
    biz_date: date,
    shop_external_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not shop_external_ids:
        return {}
    rows = (
        await db.execute(
            text(
                """
                SELECT DISTINCT ON (shop_external_id)
                    id::text,
                    shop_id::text,
                    shop_external_id,
                    shop_name,
                    biz_date,
                    health_score,
                    late_dispatch_rate,
                    negative_feedback_rate,
                    status_label,
                    source_url
                FROM tk.fact_tiktok_health_daily
                WHERE shop_external_id = ANY(:shops)
                  AND biz_date < :biz_date
                  AND health_score IS NOT NULL
                ORDER BY shop_external_id, biz_date DESC
                """
            ),
            {"shops": shop_external_ids, "biz_date": biz_date},
        )
    ).mappings().all()
    return {str(r["shop_external_id"]): dict(r) for r in rows}


async def _open_task_snapshot(
    db: AsyncSession, *, dedupe_key: str
) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text(
                """
                SELECT id::text, current_value, streak_count, metric_snapshot, updated_at
                FROM tk.fact_tk_anomaly_task
                WHERE dedupe_key = :dk AND status IN ('open', 'in_progress')
                LIMIT 1
                """
            ),
            {"dk": dedupe_key},
        )
    ).mappings().first()
    return dict(row) if row else None


def _should_notify(
    *,
    code: str,
    hit: dict[str, Any],
    existing: dict[str, Any] | None,
) -> bool:
    """新开单必推；已开单仅当分数继续恶化再推，避免日更重复刷屏。"""
    if not existing:
        return True
    curr = _f(hit.get("current_value"))
    prev_on_task = _f(existing.get("current_value"))
    if curr is None:
        return False
    if prev_on_task is None:
        return True
    # 下降类：当前分更低才再推
    if code == "shop_health_drop":
        return curr < prev_on_task - 0.01
    # 低分类：继续掉分再推
    if code == "shop_health_low":
        return curr < prev_on_task - 0.01
    return False


async def _notify_feishu(
    *,
    webhook: str,
    hit: dict[str, Any],
    dry_run: bool,
) -> bool:
    if dry_run or not webhook:
        return False
    from app.adapters.feishu.bot import send_webhook_post

    title = str(hit.get("notify_title") or hit.get("summary") or "店铺健康提醒")
    lines = list(hit.get("notify_lines") or [hit.get("detail") or hit.get("summary") or ""])
    await send_webhook_post(webhook, title=title, lines=lines)
    return True


async def evaluate_health_anomalies(
    db: AsyncSession,
    *,
    biz_date: date | None = None,
    shop_external_id: str | None = None,
    project_center_task: bool = True,
    dry_run: bool = False,
    notify: bool = True,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """扫描健康日事实 → 异常任务 + 可选飞书群提醒。"""
    cfg = settings or get_settings()
    day = await resolve_health_biz_date(db, biz_date)
    stats = HealthEvalStats(biz_date=day.isoformat())
    rows = await fetch_health_daily_rows(
        db, biz_date=day, shop_external_id=shop_external_id
    )
    stats.scanned = len(rows)

    low_threshold = float(getattr(cfg, "tk_health_low_threshold", 150.0) or 150.0)
    webhook = str(getattr(cfg, "feishu_bot_webhook_tk_health", "") or "").strip()
    notify_enabled = bool(notify) and bool(getattr(cfg, "tk_health_notify_feishu", True))

    shop_ids = [
        str(r.get("shop_external_id") or "").strip()
        for r in rows
        if r.get("shop_external_id")
    ]
    prev_map = await fetch_prev_health_map(db, biz_date=day, shop_external_ids=shop_ids)

    for row in rows:
        shop_ext = str(row.get("shop_external_id") or "").strip()
        if not shop_ext:
            stats.skipped += 1
            continue
        prev = prev_map.get(shop_ext)
        if not prev:
            stats.missing_prev += 1
            # 无历史仍可评低分
        hits = classify_health_pair(row, prev, low_threshold=low_threshold)
        if not hits:
            stats.skipped += 1
            continue

        for hit in hits:
            code = hit["anomaly_code"]
            if code == "shop_health_drop":
                stats.hit_drop += 1
            elif code == "shop_health_low":
                stats.hit_low += 1

            dedupe = f"tiktok:{shop_ext}:{code}"
            existing = await _open_task_snapshot(db, dedupe_key=dedupe)
            do_notify = notify_enabled and _should_notify(
                code=code, hit=hit, existing=existing
            )

            sample = {
                "shop_external_id": shop_ext,
                "shop_name": row.get("shop_name"),
                "anomaly_code": code,
                "priority": hit["priority"],
                "metric_snapshot": hit["metric_snapshot"],
                "will_notify": do_notify,
                "domain": "账号健康",
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
                sample["task_key"] = task.get("task_key")
                sample["status"] = task.get("status")
                stats.samples.append(sample)
                stats.created_or_updated += 1

                if do_notify:
                    try:
                        ok = await _notify_feishu(
                            webhook=webhook, hit=hit, dry_run=False
                        )
                        if ok:
                            stats.notified += 1
                        else:
                            stats.notify_skipped += 1
                            if not webhook:
                                sample["notify_error"] = "webhook empty"
                    except Exception as nexc:  # noqa: BLE001
                        stats.notify_skipped += 1
                        stats.errors.append(f"notify {shop_ext}/{code}: {nexc}")
                        logger.warning("health feishu notify failed: %s", nexc)
                else:
                    stats.notify_skipped += 1
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"{shop_ext}/{code}: {exc}")

    return {
        **stats.as_dict(),
        "thresholds": {
            "low_threshold": low_threshold,
            "drop_any": True,
        },
        "notify_enabled": notify_enabled,
        "webhook_configured": bool(webhook),
        "dry_run": dry_run,
        "domain": "账号健康",
    }
