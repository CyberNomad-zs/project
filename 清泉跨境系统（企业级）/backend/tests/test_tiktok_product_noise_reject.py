"""tiktok_products 拒收「N 个 SKU 展开」噪声行。"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.infra.db import engine


@pytest.mark.asyncio
async def test_product_reject_sku_expand_noise(client):
    suffix = uuid.uuid4().hex[:8]
    shop_id = "27328767468273"
    body = {
        "items": [
            {
                "platform": "tiktok",
                "shop_id": shop_id,
                "shop_name": "Gardena",
                "idempotency_key": f"test-prod-noise-{suffix}",
                "payload": {
                    "product_id": "name:2 个 SKU展开",
                    "product_name": "2 个 SKU展开",
                    "currency": "GBP",
                },
            }
        ]
    }
    r = await client.post(
        "/api/v1/ingest/tiktok_products",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=body,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("failed", 0) >= 1 or data.get("accepted", 0) == 0

    async with engine.connect() as conn:
        n = (
            await conn.execute(
                text(
                    """
                    SELECT count(*)::int AS c
                    FROM tk.fact_tiktok_product
                    WHERE product_id LIKE 'name:%SKU%'
                       OR coalesce(product_name,'') LIKE '%SKU展开%'
                    """
                )
            )
        ).scalar()
        assert int(n or 0) == 0


@pytest.mark.asyncio
async def test_product_accept_with_seller_skus(client):
    suffix = uuid.uuid4().hex[:8]
    shop_id = "27328767468273"
    pid = f"1729{suffix}{suffix}"[:16]
    body = {
        "items": [
            {
                "platform": "tiktok",
                "shop_id": shop_id,
                "shop_name": "Gardena",
                "idempotency_key": f"test-prod-sku-{suffix}",
                "payload": {
                    "product_id": pid,
                    "product_name": f"Real product {suffix}",
                    "seller_sku": f"SKU-A-{suffix}|SKU-B-{suffix}",
                    "seller_skus": [f"SKU-A-{suffix}", f"SKU-B-{suffix}"],
                    "status": "在售",
                    "stock_qty": 10,
                    "price": 9.99,
                    "currency": "GBP",
                },
            }
        ]
    }
    r = await client.post(
        "/api/v1/ingest/tiktok_products",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=body,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["failed"] == 0

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT seller_sku, raw_extra->>'seller_skus' AS skus
                    FROM tk.fact_tiktok_product
                    WHERE shop_external_id = :shop AND product_id = :pid
                    """
                ),
                {"shop": shop_id, "pid": pid},
            )
        ).mappings().first()
        assert row is not None
        assert suffix in (row["seller_sku"] or "")
