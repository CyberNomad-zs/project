"""TK 违规扣分异常：新出现的违规记录 → 异常任务 + 飞书群。

规则：
  - shop_violation  首次入库且在窗口内（默认 48h）的违规记录

幂等：dedupe = tiktok:{shop_ext}:shop_violation:{violation_key}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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


@dataclass
class ViolationEvalStats:
    scanned: int = 0
    hit: int = 0
    created_or_updated: int = 0
    notified: int = 0
    notify_skipped: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "hit": self.hit,
            "created_or_updated": self.created_or_updated,
            "notified": self.notified,
            "notify_skipped": self.notify_skipped,
            "skipped": self.skipped,
            "errors": self.errors[:20],
            "samples": self.samples[:10],
        }


async def fetch_new_violations(
    db: AsyncSession,
    *,
    within_hours: float,
    shop_external_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "since": datetime.now(timezone.utc) - timedelta(hours=max(1.0, within_hours)),
        "limit": limit,
    }
    clauses = ["first_seen_at >= :since"]
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
                    violation_key,
                    penalty_text,
                    penalty_score,
                    reason,
                    status,
                    violation_at,
                    biz_date,
                    product_id,
                    order_id,
                    source_url,
                    first_seen_at
                FROM tk.fact_tiktok_violation
                WHERE {' AND '.join(clauses)}
                ORDER BY first_seen_at DESC
                LIMIT :limit
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def _open_exists(db: AsyncSession, dedupe_key: str) -> bool:
    row = (
        await db.execute(
            text(
                """
                SELECT 1 FROM tk.fact_tk_anomaly_task
                WHERE dedupe_key = :dk AND status IN ('open', 'in_progress')
                LIMIT 1
                """
            ),
            {"dk": dedupe_key},
        )
    ).first()
    return bool(row)


async def _notify(
    webhook: str,
    title: str,
    lines: list[str],
    *,
    dry_run: bool,
    settings: Settings | None = None,
) -> bool:
    del webhook
    from app.domain.notify_dual import notify_dual

    res = await notify_dual(title=title, lines=lines, settings=settings, dry_run=dry_run)
    return bool(res.get("any_sent"))


async def evaluate_violation_anomalies(
    db: AsyncSession,
    *,
    shop_external_id: str | None = None,
    project_center_task: bool = True,
    dry_run: bool = False,
    notify: bool = True,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    within = float(getattr(cfg, "tk_violation_new_within_hours", 48.0) or 48.0)
    webhook = str(getattr(cfg, "feishu_bot_webhook_tk_health", "") or "").strip()
    notify_enabled = bool(notify) and bool(getattr(cfg, "tk_health_notify_feishu", True))
    stats = ViolationEvalStats()

    rows = await fetch_new_violations(
        db, within_hours=within, shop_external_id=shop_external_id
    )
    stats.scanned = len(rows)

    for row in rows:
        shop_ext = str(row.get("shop_external_id") or "").strip()
        vkey = str(row.get("violation_key") or "").strip()
        if not shop_ext or not vkey:
            stats.skipped += 1
            continue
        shop_name = str(row.get("shop_name") or shop_ext).strip()
        low = shop_name.lower()
        if "schema-tk-smoke" in low or low.startswith("[test]"):
            stats.skipped += 1
            continue

        score = _f(row.get("penalty_score"))
        penalty = str(row.get("penalty_text") or "").strip() or "-"
        reason = str(row.get("reason") or "").strip() or "-"
        status = str(row.get("status") or "").strip() or "-"
        product_id = str(row.get("product_id") or "").strip() or None
        biz = row.get("biz_date")
        # 违规一律 P0；分值/冻结类在文案里体现
        pri = "P0"

        stats.hit += 1
        dedupe = f"tiktok:{shop_ext}:shop_violation:{vkey}"[:200]
        already = await _open_exists(db, dedupe)
        do_notify = notify_enabled and not already

        metric = (
            f"penalty={penalty[:80]} score={score} reason={reason[:80]} "
            f"status={status} product_id={product_id or '-'}"
        )
        detail = f"违规：{penalty}；原因：{reason}；状态：{status}"
        summary = f"店铺违规扣分 · {shop_name}"
        lines = [
            f"店铺：{shop_name}（{shop_ext}）",
            f"处罚：{penalty}",
            f"扣分：{score if score is not None else '-'}",
            f"原因：{reason}",
            f"状态：{status}",
            f"日期：{biz or row.get('violation_at') or '-'}",
            f"商品ID：{product_id or '-'}",
            f"链接：{row.get('source_url') or '-'}",
        ]
        sample = {
            "shop_external_id": shop_ext,
            "violation_key": vkey,
            "priority": pri,
            "will_notify": do_notify,
            "domain": "店铺违规",
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
                anomaly_code="shop_violation",
                summary=summary,
                shop_id=row.get("shop_id"),
                shop_external_id=shop_ext,
                shop_name=shop_name,
                object_ref=vkey,
                object_type="shop",
                product_id=product_id,
                product_name=shop_name,
                priority=pri,
                progress_note=detail,
                metric_snapshot=metric,
                biz_date=biz,
                dedupe_key=dedupe,
                source_url=row.get("source_url"),
                project_center_task=project_center_task,
                current_value=score,
                current_value_label="违规分",
                needs_boss_decision=True,
                description=f"{detail} | {metric}",
            )
            sample["task_id"] = task.get("id")
            sample["task_key"] = task.get("task_key")
            stats.samples.append(sample)
            stats.created_or_updated += 1
            if do_notify:
                try:
                    ok = await _notify(
                        webhook,
                        f"🚨 店铺违规扣分 · {shop_name}",
                        lines,
                        dry_run=False,
                        settings=cfg,
                    )
                    if ok:
                        stats.notified += 1
                    else:
                        stats.notify_skipped += 1
                except Exception as nexc:  # noqa: BLE001
                    stats.notify_skipped += 1
                    stats.errors.append(f"notify {shop_ext}/{vkey}: {nexc}")
            else:
                stats.notify_skipped += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"{shop_ext}/{vkey}: {exc}")

    return {
        **stats.as_dict(),
        "thresholds": {"new_within_hours": within},
        "notify_enabled": notify_enabled,
        "webhook_configured": bool(webhook),
        "dry_run": dry_run,
        "domain": "店铺违规",
    }
