"""TK 商品库存异常：从 fact_tiktok_product 生成 anomaly task。

规则：
  - product_stockout  断货：stock_qty <= stockout_qty（默认 0）
  - product_stock_low 库存不足：stockout_qty < stock_qty < low_qty（默认 10）

跳过：stock_qty IS NULL；明显下架/删除状态不报库存（可选）。
幂等：dedupe = tiktok:{shop}|{product_id}:{code}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.domain import tk_anomaly

_SKIP_STATUS = {
    "deleted",
    "删除",
    "已删除",
    "draft",
    "草稿",
}


def _f(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def classify_product_row(
    row: dict[str, Any],
    *,
    stockout_qty: float,
    low_qty: float,
) -> list[dict[str, Any]]:
    stock = _f(row.get("stock_qty"))
    if stock is None:
        return []

    status = str(row.get("status") or "").strip().lower()
    if status in _SKIP_STATUS:
        return []

    name = str(row.get("product_name") or row.get("product_id") or "").strip()
    pid = str(row.get("product_id") or "").strip()
    if not pid:
        return []

    hits: list[dict[str, Any]] = []
    currency = row.get("currency") or ""
    price = _f(row.get("price"))
    sales = _f(row.get("sales_qty"))

    def metric(extra: str = "") -> str:
        parts = [f"stock={stock:.0f}", f"status={row.get('status') or '-'}"]
        if price is not None:
            parts.append(f"price={price:.2f}{currency}")
        if sales is not None:
            parts.append(f"sales_qty={sales:.0f}")
        if extra:
            parts.append(extra)
        return " ".join(parts)

    if stock <= stockout_qty:
        detail = f"可售库存 {stock:.0f} ≤ 断货阈值 {stockout_qty:.0f}"
        hits.append(
            {
                "anomaly_code": "product_stockout",
                "priority": "P0",
                "summary": f"商品断货 · {name}",
                "metric_snapshot": metric("reason=stockout"),
                "detail": detail,
                "current_value": stock,
                "current_value_label": "可售库存",
                "compare_value": stockout_qty,
                "compare_value_label": "断货阈值",
                "change_magnitude": stock - stockout_qty,
                "change_magnitude_label": "低于/等于断货线",
                "needs_boss_decision": True,
                "description": f"{detail} | {metric('reason=stockout')}",
            }
        )
        return hits

    if stock < low_qty:
        # 越接近 0 越高优
        pri = "P0" if stock <= max(low_qty * 0.3, stockout_qty + 1) else "P1"
        detail = f"可售库存 {stock:.0f} < 补货阈值 {low_qty:.0f}"
        hits.append(
            {
                "anomaly_code": "product_stock_low",
                "priority": pri,
                "summary": f"商品库存不足 · {name}",
                "metric_snapshot": metric(f"low_qty={low_qty:.0f}"),
                "detail": detail,
                "current_value": stock,
                "current_value_label": "可售库存",
                "compare_value": low_qty,
                "compare_value_label": "补货阈值",
                "change_magnitude": stock - low_qty,
                "change_magnitude_label": "低于补货线",
                "needs_boss_decision": pri == "P0",
                "description": f"{detail} | {metric(f'low_qty={low_qty:.0f}')}",
            }
        )
    return hits


@dataclass
class ProductEvalStats:
    scanned: int = 0
    hit_stockout: int = 0
    hit_stock_low: int = 0
    created_or_updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "hit_stockout": self.hit_stockout,
            "hit_stock_low": self.hit_stock_low,
            "created_or_updated": self.created_or_updated,
            "skipped": self.skipped,
            "errors": self.errors[:20],
            "samples": self.samples[:10],
        }


async def fetch_product_rows(
    db: AsyncSession,
    *,
    shop_external_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}
    if shop_external_id:
        clauses.append("shop_external_id = :shop_external_id")
        params["shop_external_id"] = shop_external_id
    rows = (
        await db.execute(
            text(
                f"""
                SELECT
                    id::text, shop_id::text, shop_external_id, shop_name,
                    product_id, product_name, seller_sku, status,
                    stock_qty, price, currency, sales_qty, source_url, updated_at
                FROM tk.fact_tiktok_product
                WHERE {' AND '.join(clauses)}
                ORDER BY stock_qty ASC NULLS LAST, product_name
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def evaluate_product_anomalies(
    db: AsyncSession,
    *,
    shop_external_id: str | None = None,
    project_center_task: bool = True,
    dry_run: bool = False,
    settings: Settings | None = None,
    biz_date: date | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    day = biz_date or datetime.now(timezone.utc).date()
    stats = ProductEvalStats()
    rows = await fetch_product_rows(db, shop_external_id=shop_external_id)
    stats.scanned = len(rows)

    stockout_qty = float(cfg.tk_product_stockout_qty)
    low_qty = float(cfg.tk_product_stock_low_qty)

    for row in rows:
        hits = classify_product_row(row, stockout_qty=stockout_qty, low_qty=low_qty)
        if not hits:
            stats.skipped += 1
            continue

        shop_ext = row.get("shop_external_id")
        pid = str(row.get("product_id") or "").strip()
        object_ref = f"{shop_ext}|{pid}" if shop_ext else pid

        for hit in hits:
            code = hit["anomaly_code"]
            if code == "product_stockout":
                stats.hit_stockout += 1
            else:
                stats.hit_stock_low += 1

            sample = {
                "product_id": pid,
                "product_name": row.get("product_name"),
                "shop_external_id": shop_ext,
                "anomaly_code": code,
                "priority": hit["priority"],
                "metric_snapshot": hit["metric_snapshot"],
            }
            if dry_run:
                stats.samples.append(sample)
                stats.created_or_updated += 1
                continue

            try:
                task = await tk_anomaly.create_anomaly_task(
                    db,
                    anomaly_code=code,
                    summary=hit["summary"],
                    shop_id=row.get("shop_id"),
                    shop_external_id=shop_ext,
                    shop_name=row.get("shop_name"),
                    product_id=pid,
                    seller_sku=row.get("seller_sku"),
                    product_name=row.get("product_name"),
                    object_ref=object_ref,
                    object_type="product",
                    priority=hit["priority"],
                    progress_note=hit["detail"],
                    metric_snapshot=hit["metric_snapshot"],
                    biz_date=day,
                    dedupe_key=f"tiktok:{object_ref}:{code}",
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
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"{pid}/{code}: {exc}")

    return {
        **stats.as_dict(),
        "biz_date": day.isoformat(),
        "thresholds": {
            "stockout_qty": stockout_qty,
            "stock_low_qty": low_qty,
        },
        "dry_run": dry_run,
    }
