"""tiktok_order_lines ingest → tk.fact_tiktok_order_line + 回填订单头 SKU。"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.infra.db import engine


@pytest.mark.asyncio
async def test_order_line_ingest_and_header_backfill(client):
    suffix = uuid.uuid4().hex[:8]
    shop_id = "27328767468273"
    order_id = f"57{suffix}{suffix[:6]}"[:18].ljust(18, "0")
    # 先写订单头（无 SKU）
    head = {
        "items": [
            {
                "platform": "tiktok",
                "shop_id": shop_id,
                "shop_name": "Gardena",
                "biz_date": "2026-08-05",
                "idempotency_key": f"test-order-head-{suffix}",
                "payload": {
                    "order_id": order_id,
                    "order_status": "已发货",
                    "product_name": "1 件商品",
                    "quantity": 1,
                    "pay_amount": 12.34,
                    "currency": "GBP",
                },
            }
        ]
    }
    r0 = await client.post(
        "/api/v1/ingest/tiktok_orders",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=head,
    )
    assert r0.status_code == 200, r0.text

    line_body = {
        "items": [
            {
                "platform": "tiktok",
                "shop_id": shop_id,
                "shop_name": "Gardena",
                "biz_date": "2026-08-05",
                "idempotency_key": f"test-order-line-{suffix}",
                "payload": {
                    "order_id": order_id,
                    "line_no": 1,
                    "line_key": f"sku:JMCAT-{suffix}",
                    "product_id": f"1729{suffix}"[:16],
                    "product_name": f"Test Product {suffix}",
                    "seller_sku": f"JMCAT-{suffix}",
                    "sku_id": f"8800{suffix}"[:14],
                    "quantity": 2,
                    "unit_price": 6.17,
                    "currency": "GBP",
                },
            }
        ]
    }
    r = await client.post(
        "/api/v1/ingest/tiktok_order_lines",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=line_body,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["failed"] == 0
    assert data.get("accepted", 0) + data.get("duplicated", 0) >= 1

    async with engine.connect() as conn:
        line = (
            await conn.execute(
                text(
                    """
                    SELECT seller_sku, sku_id, quantity::float, product_name
                    FROM tk.fact_tiktok_order_line
                    WHERE shop_external_id = :shop AND order_id = :oid
                    """
                ),
                {"shop": shop_id, "oid": order_id},
            )
        ).mappings().first()
        assert line is not None
        assert line["seller_sku"] == f"JMCAT-{suffix}"
        assert float(line["quantity"]) == 2.0

        head_row = (
            await conn.execute(
                text(
                    """
                    SELECT seller_sku, sku_id, product_name
                    FROM tk.fact_tiktok_order
                    WHERE shop_external_id = :shop AND order_id = :oid
                    """
                ),
                {"shop": shop_id, "oid": order_id},
            )
        ).mappings().first()
        assert head_row is not None
        assert head_row["seller_sku"] == f"JMCAT-{suffix}"
        assert head_row["sku_id"] == f"8800{suffix}"[:14]
        assert "Test Product" in (head_row["product_name"] or "")
