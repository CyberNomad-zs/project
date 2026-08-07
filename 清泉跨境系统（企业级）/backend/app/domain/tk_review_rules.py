"""TK 差评异常：新出现的低星评价 → 异常任务 + 飞书群。

规则：
  - shop_bad_review  rating ≤ 阈值（默认 2）且在新入库窗口内
  - 默认仅未回复差评提醒

幂等：dedupe = tiktok:{shop_ext}:shop_bad_review:{review_key}
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
class ReviewEvalStats:
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


async def fetch_new_bad_reviews(
    db: AsyncSession,
    *,
    within_hours: float,
    max_rating: float,
    only_unreplied: bool,
    shop_external_id: str | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "since": datetime.now(timezone.utc) - timedelta(hours=max(1.0, within_hours)),
        "max_rating": max_rating,
        "limit": limit,
    }
    clauses = [
        "first_seen_at >= :since",
        "rating IS NOT NULL",
        "rating <= :max_rating",
    ]
    if only_unreplied:
        clauses.append("has_reply = FALSE")
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
                    review_key,
                    order_id,
                    product_id,
                    product_name,
                    rating,
                    review_text,
                    review_at,
                    biz_date,
                    buyer_name,
                    has_reply,
                    reply_text,
                    source_url,
                    first_seen_at
                FROM tk.fact_tiktok_review
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


async def _notify(webhook: str, title: str, lines: list[str], *, dry_run: bool) -> bool:
    if dry_run or not webhook:
        return False
    from app.adapters.feishu.bot import send_webhook_post

    await send_webhook_post(webhook, title=title, lines=lines)
    return True


async def evaluate_review_anomalies(
    db: AsyncSession,
    *,
    shop_external_id: str | None = None,
    project_center_task: bool = True,
    dry_run: bool = False,
    notify: bool = True,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    within = float(getattr(cfg, "tk_review_new_within_hours", 72.0) or 72.0)
    max_rating = float(getattr(cfg, "tk_review_bad_max_rating", 2.0) or 2.0)
    only_unreplied = bool(getattr(cfg, "tk_review_only_unreplied", True))
    webhook = str(getattr(cfg, "feishu_bot_webhook_tk_health", "") or "").strip()
    notify_enabled = bool(notify) and bool(getattr(cfg, "tk_health_notify_feishu", True))
    stats = ReviewEvalStats()

    rows = await fetch_new_bad_reviews(
        db,
        within_hours=within,
        max_rating=max_rating,
        only_unreplied=only_unreplied,
        shop_external_id=shop_external_id,
    )
    stats.scanned = len(rows)

    for row in rows:
        shop_ext = str(row.get("shop_external_id") or "").strip()
        rkey = str(row.get("review_key") or "").strip()
        if not shop_ext or not rkey:
            stats.skipped += 1
            continue
        shop_name = str(row.get("shop_name") or shop_ext).strip()
        low = shop_name.lower()
        if "schema-tk-smoke" in low or low.startswith("[test]"):
            stats.skipped += 1
            continue

        rating = _f(row.get("rating"))
        if rating is None:
            stats.skipped += 1
            continue

        product_id = str(row.get("product_id") or "").strip() or None
        product_name = str(row.get("product_name") or "").strip() or None
        order_id = str(row.get("order_id") or "").strip() or None
        text_body = str(row.get("review_text") or "").strip() or "-"
        buyer = str(row.get("buyer_name") or "").strip() or "-"
        pri = "P0" if rating <= 1 else "P1"

        stats.hit += 1
        dedupe = f"tiktok:{shop_ext}:shop_bad_review:{rkey}"[:200]
        already = await _open_exists(db, dedupe)
        do_notify = notify_enabled and not already

        metric = (
            f"rating={rating:.0f} product_id={product_id or '-'} order_id={order_id or '-'} "
            f"has_reply={row.get('has_reply')} buyer={buyer}"
        )
        detail = f"{rating:.0f}星差评 · {product_name or product_id or order_id or rkey}"
        summary = f"商品差评待处理 · {shop_name}"
        stars = "★" * int(rating) + "☆" * max(0, 5 - int(rating))
        lines = [
            f"店铺：{shop_name}（{shop_ext}）",
            f"评分：{stars}（{rating:.0f}）",
            f"商品：{product_name or '-'}",
            f"商品ID：{product_id or '-'}",
            f"订单ID：{order_id or '-'}",
            f"买家：{buyer}",
            f"评价：{text_body[:180]}",
            f"已回复：{'是' if row.get('has_reply') else '否'}",
            f"日期：{row.get('biz_date') or row.get('review_at') or '-'}",
            f"链接：{row.get('source_url') or '-'}",
        ]
        sample = {
            "shop_external_id": shop_ext,
            "review_key": rkey,
            "rating": rating,
            "priority": pri,
            "will_notify": do_notify,
            "domain": "差评处理",
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
                anomaly_code="shop_bad_review",
                summary=summary,
                shop_id=row.get("shop_id"),
                shop_external_id=shop_ext,
                shop_name=shop_name,
                object_ref=product_id or order_id or rkey,
                object_type="product" if product_id else "shop",
                product_id=product_id,
                product_name=product_name,
                priority=pri,
                progress_note=detail,
                metric_snapshot=metric,
                biz_date=row.get("biz_date"),
                dedupe_key=dedupe,
                source_url=row.get("source_url"),
                project_center_task=project_center_task,
                current_value=rating,
                current_value_label="星级",
                needs_boss_decision=pri == "P0",
                description=f"{detail} | {text_body[:120]} | {metric}",
                next_action="尽快回复差评并跟进售后",
            )
            sample["task_id"] = task.get("id")
            sample["task_key"] = task.get("task_key")
            stats.samples.append(sample)
            stats.created_or_updated += 1
            if do_notify:
                try:
                    ok = await _notify(
                        webhook,
                        f"⭐ 差评待处理 · {shop_name} · {rating:.0f}星",
                        lines,
                        dry_run=False,
                    )
                    if ok:
                        stats.notified += 1
                    else:
                        stats.notify_skipped += 1
                except Exception as nexc:  # noqa: BLE001
                    stats.notify_skipped += 1
                    stats.errors.append(f"notify {shop_ext}/{rkey}: {nexc}")
            else:
                stats.notify_skipped += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"{shop_ext}/{rkey}: {exc}")

    return {
        **stats.as_dict(),
        "thresholds": {
            "bad_max_rating": max_rating,
            "new_within_hours": within,
            "only_unreplied": only_unreplied,
        },
        "notify_enabled": notify_enabled,
        "webhook_configured": bool(webhook),
        "dry_run": dry_run,
        "domain": "差评处理",
    }
