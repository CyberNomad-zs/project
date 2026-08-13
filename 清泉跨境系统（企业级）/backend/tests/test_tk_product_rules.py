"""商品库存规则 + 广告列表 API 测试。"""

from __future__ import annotations

import uuid

import pytest

from app.domain.tk_product_rules import classify_product_row


def test_classify_stockout():
    hits = classify_product_row(
        {"product_id": "p1", "product_name": "A", "stock_qty": 0, "status": "active"},
        stockout_qty=0,
        low_qty=10,
    )
    assert len(hits) == 1
    assert hits[0]["anomaly_code"] == "product_stockout"
    assert hits[0]["priority"] == "P0"


def test_classify_stock_low():
    hits = classify_product_row(
        {"product_id": "p2", "product_name": "B", "stock_qty": 5, "status": "在售"},
        stockout_qty=0,
        low_qty=10,
    )
    assert len(hits) == 1
    assert hits[0]["anomaly_code"] == "product_stock_low"


def test_classify_ok_stock():
    hits = classify_product_row(
        {"product_id": "p3", "product_name": "C", "stock_qty": 50},
        stockout_qty=0,
        low_qty=10,
    )
    assert hits == []


def test_classify_skip_null_and_deleted():
    assert (
        classify_product_row(
            {"product_id": "p4", "stock_qty": None},
            stockout_qty=0,
            low_qty=10,
        )
        == []
    )


def test_classify_skip_orderlike_product_name():
    """订单号+时间 误入商品表时不应再生成断货任务。"""
    assert (
        classify_product_row(
            {
                "product_id": "576931007608887771",
                "product_name": "576931007608887771星期五 22:26:25",
                "stock_qty": 0,
                "status": "1 件商品",
            },
            stockout_qty=0,
            low_qty=10,
        )
        == []
    )
    assert (
        classify_product_row(
            {"product_id": "p5", "stock_qty": 0, "status": "deleted"},
            stockout_qty=0,
            low_qty=10,
        )
        == []
    )


@pytest.mark.asyncio
async def test_product_eval_with_seeded_rows(client, auth_headers):
    # 经 ingest 写入两条商品（会触发 auto eval）
    suffix = uuid.uuid4().hex[:6]
    body = {
        "items": [
            {
                "platform": "tiktok",
                "shop_id": "27501502216807",
                "shop_name": "Deal to deal",
                "idempotency_key": f"test-prod-out-{suffix}",
                "payload": {
                    "product_id": f"PID-OUT-{suffix}",
                    "product_name": f"断货测 {suffix}",
                    "status": "active",
                    "stock_qty": 0,
                    "price": 9.9,
                    "currency": "GBP",
                },
            },
            {
                "platform": "tiktok",
                "shop_id": "27501502216807",
                "shop_name": "Deal to deal",
                "idempotency_key": f"test-prod-low-{suffix}",
                "payload": {
                    "product_id": f"PID-LOW-{suffix}",
                    "product_name": f"低库存测 {suffix}",
                    "status": "active",
                    "stock_qty": 3,
                    "price": 12.0,
                    "currency": "GBP",
                },
            },
            {
                "platform": "tiktok",
                "shop_id": "27501502216807",
                "shop_name": "Deal to deal",
                "idempotency_key": f"test-prod-ok-{suffix}",
                "payload": {
                    "product_id": f"PID-OK-{suffix}",
                    "product_name": f"充足 {suffix}",
                    "status": "active",
                    "stock_qty": 80,
                },
            },
        ]
    }
    r = await client.post(
        "/api/v1/ingest/tiktok_products",
        headers={**auth_headers, "X-Api-Key": "dev-ingest-key"},
        json=body,
    )
    # ingest 用 api key，不要混 JWT 也行
    if r.status_code == 401:
        r = await client.post(
            "/api/v1/ingest/tiktok_products",
            headers={"X-Api-Key": "dev-ingest-key"},
            json=body,
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["failed"] == 0
    auto = data.get("auto_anomaly_eval") or {}
    # 自动规则应命中至少断货+低库存
    assert auto.get("kind") == "products"
    assert auto.get("hit_stockout", 0) + auto.get("hit_stock_low", 0) >= 2

    r = await client.get(
        "/api/v1/tk/anomaly-tasks",
        headers=auth_headers,
        params={"q": suffix, "open_only": True, "page_size": 50},
    )
    assert r.status_code == 200, r.text
    codes = {i["anomaly_code"] for i in r.json()["items"]}
    assert "product_stockout" in codes
    assert "product_stock_low" in codes


@pytest.mark.asyncio
async def test_ads_campaigns_list(client, auth_headers):
    r = await client.get(
        "/api/v1/tk/ads/campaigns",
        headers=auth_headers,
        params={"biz_date": "2026-07-29", "page_size": 20},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["biz_date"] == "2026-07-29"
    assert data["total"] >= 1
    assert "summary" in data
    assert isinstance(data["items"], list)
    # 扫描过规则后，部分系列应带异常标记
    if data["items"]:
        assert "has_open_anomaly" in data["items"][0]
        assert "campaign_name" in data["items"][0]
