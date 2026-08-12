"""P2.1b 视频内容 ingest → tk.fact_tiktok_content_daily。"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.infra.db import engine


@pytest.mark.asyncio
async def test_content_ingest_create_and_refresh(client):
    suffix = uuid.uuid4().hex[:8]
    shop_id = "27501502216807"
    content_id = f"7667{suffix.zfill(12)}"[:19]
    biz_date = "2026-08-04"
    biz_date_d = date(2026, 8, 4)
    idem = f"test-content-{suffix}"

    body = {
        "items": [
            {
                "platform": "tiktok",
                "shop_id": shop_id,
                "shop_name": "Deal to deal",
                "biz_date": biz_date,
                "idempotency_key": idem,
                "payload": {
                    "content_id": content_id,
                    "content_title": f"视频测 {suffix}",
                    "channel": "short_video",
                    "play_count": 1200,
                    "attributed_gmv": 12.5,
                    "attributed_sku_orders": 2,
                    "impressions": 500,
                    "cvr": 0.4,
                    "currency": "GBP",
                    "window": "最近 7 天",
                    "published_at": "2026年7月29日 10:21 15s",
                    "source_url": (
                        "https://seller-uk.tiktok.com/compass/video-analytics/"
                        f"video-detail-item?id={content_id}&shop_region=GB"
                    ),
                },
                "evidence": {
                    "source_url": (
                        "https://seller-uk.tiktok.com/compass/video-analytics/"
                        f"video-detail-item?id={content_id}&shop_region=GB"
                    )
                },
            }
        ]
    }

    r = await client.post(
        "/api/v1/ingest/tiktok_content",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=body,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["failed"] == 0
    assert data.get("accepted", 0) + data.get("duplicated", 0) >= 1

    body["items"][0]["payload"]["attributed_gmv"] = 88.8
    body["items"][0]["payload"]["play_count"] = 3400
    r2 = await client.post(
        "/api/v1/ingest/tiktok_content",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=body,
    )
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert data2["failed"] == 0
    assert data2.get("duplicated", 0) >= 1 or data2.get("accepted", 0) >= 1

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT attributed_gmv::float, play_count::float,
                           raw_extra->>'window' AS win,
                           raw_extra->>'published_at' AS pub
                    FROM tk.fact_tiktok_content_daily
                    WHERE shop_external_id = :shop
                      AND content_id = :cid
                      AND biz_date = :d
                      AND channel = 'short_video'
                    """
                ),
                {"shop": shop_id, "cid": content_id, "d": biz_date_d},
            )
        ).first()
    assert row is not None, "row missing — apply migration 013_tk_content_daily.sql"
    assert abs(float(row[0]) - 88.8) < 0.01
    assert abs(float(row[1]) - 3400) < 0.01
    assert row[2] == "最近 7 天"
    assert row[3] and "2026" in str(row[3])

    bad = {
        "items": [
            {
                "platform": "tiktok",
                "shop_id": shop_id,
                "biz_date": biz_date,
                "idempotency_key": f"test-content-bad-{suffix}",
                "payload": {"attributed_gmv": 1.0, "channel": "short_video"},
            }
        ]
    }
    r3 = await client.post(
        "/api/v1/ingest/tiktok_content",
        headers={"X-Api-Key": "dev-ingest-key"},
        json=bad,
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["failed"] >= 1
