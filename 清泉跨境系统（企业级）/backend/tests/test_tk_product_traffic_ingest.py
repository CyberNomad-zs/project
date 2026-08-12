"""P2.1a 商品卡流量 ingest → tk.fact_tiktok_product_traffic_daily。"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.infra.db import engine


@pytest.mark.asyncio
async def test_product_traffic_ingest_create_and_refresh(client):
    suffix = uuid.uuid4().hex[:8]
    shop_id = "27501502216807"
    product_id = f"PID-TRAFFIC-{suffix}"
    biz_date = "2026-08-03"
    biz_date_d = date(2026, 8, 3)
    idem = f"test-traffic-{suffix}"

    body = {
        "items": [
            {
                "platform": "tiktok",
                "shop_id": shop_id,
                "shop_name": "Deal to deal",
                "biz_date": biz_date,
                "idempotency_key": idem,
                "payload": {
                    "product_id": product_id,
                    "product_name": f"流量测 {suffix}",
                    "channel": "product_card",
                    "impressions": 11400,
                    "gmv": 112.18,
                    "cvr": 0.09,
                    "currency": "GBP",
                    "window": "最近 7 天",
                    "source_url": "https://seller-uk.tiktok.com/compass/product-card-analytics?shop_region=GB",
                },
                "evidence": {
                    "source_url": "https://seller-uk.tiktok.com/compass/product-card-analytics?shop_region=GB"
                },
            }
        ]
    }

    r = await client.post(
        "/api/v1/ingest/tiktok_product_traffic",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=body,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["failed"] == 0
    assert data.get("accepted", 0) + data.get("duplicated", 0) >= 1

    # 同幂等键再报：duplicated + 指标刷新
    body["items"][0]["payload"]["gmv"] = 199.99
    body["items"][0]["payload"]["impressions"] = 12000
    r2 = await client.post(
        "/api/v1/ingest/tiktok_product_traffic",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=body,
    )
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert data2["failed"] == 0
    assert data2.get("duplicated", 0) >= 1 or data2.get("accepted", 0) >= 1

    # DB 校验：window 进 raw_extra；刷新后 gmv
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT gmv::float, impressions::float, raw_extra->>'window' AS win
                    FROM tk.fact_tiktok_product_traffic_daily
                    WHERE shop_external_id = :shop
                      AND product_id = :pid
                      AND biz_date = :d
                      AND channel = 'product_card'
                    """
                ),
                {"shop": shop_id, "pid": product_id, "d": biz_date_d},
            )
        ).first()
    assert row is not None, "row missing — apply migration 012_tk_product_traffic_daily.sql"
    assert abs(float(row[0]) - 199.99) < 0.01
    assert abs(float(row[1]) - 12000) < 0.01
    assert row[2] == "最近 7 天"

    # 缺 product_id → failed
    bad = {
        "items": [
            {
                "platform": "tiktok",
                "shop_id": shop_id,
                "biz_date": biz_date,
                "idempotency_key": f"test-traffic-bad-{suffix}",
                "payload": {"gmv": 1.0, "channel": "product_card"},
            }
        ]
    }
    r3 = await client.post(
        "/api/v1/ingest/tiktok_product_traffic",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=bad,
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["failed"] >= 1
