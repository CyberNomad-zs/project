"""TK 广告异常规则单元 + API 集成测试。"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.tk_ads_rules import classify_ads_row


def _base_kwargs(**over):
    kw = dict(
        min_spend=1.0,
        global_min_roi=3.0,
        target_ratio=1.0,
        target_slack=0.0,
        budget_burn_ratio=0.8,
        budget_min=1.0,
        max_cpa=15.0,
        cpa_aov_ratio=0.4,
    )
    kw.update(over)
    return kw


def test_classify_spend_no_sale():
    hits = classify_ads_row(
        {
            "campaign_name": "测试空耗系列",
            "spend": 12.5,
            "orders": 0,
            "revenue": 0,
            "roi": 0,
            "biz_date": date(2026, 7, 29),
            "currency": "GBP",
        },
        **_base_kwargs(),
    )
    assert len(hits) == 1
    assert hits[0]["anomaly_code"] == "ads_spend_no_sale"


def test_classify_roi_below_target():
    hits = classify_ads_row(
        {
            "campaign_name": "白板7/13",
            "spend": 62.56,
            "orders": 14,
            "revenue": 374.27,
            "roi": 5.98,
            "target_roi": 16.0,
            "biz_date": date(2026, 7, 29),
            "currency": "GBP",
        },
        **_base_kwargs(),
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "ads_roi_low" in codes
    assert hits[0]["priority"] in ("P0", "P1", "P2")


def test_classify_roi_ok_no_hit():
    hits = classify_ads_row(
        {
            "campaign_name": "健康系列",
            "spend": 50,
            "orders": 20,
            "revenue": 600,
            "roi": 12.0,
            "target_roi": 10.0,
            "avg_order_cost": 2.5,
            "daily_budget": 200,
            "biz_date": date(2026, 7, 29),
        },
        **_base_kwargs(),
    )
    assert hits == []


def test_classify_skip_low_spend():
    hits = classify_ads_row(
        {
            "campaign_name": "微量",
            "spend": 0.5,
            "orders": 0,
            "revenue": 0,
            "roi": 0,
        },
        **_base_kwargs(),
    )
    assert hits == []


def test_classify_empty_and_roi_mutex():
    """有花费无单只打空耗，不叠加低 ROI；预算将尽可叠加。"""
    hits = classify_ads_row(
        {
            "campaign_name": "空耗",
            "spend": 10,
            "orders": 0,
            "revenue": 0,
            "roi": 0,
            "target_roi": 8,
            "daily_budget": 12,
        },
        **_base_kwargs(),
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "ads_spend_no_sale" in codes
    assert "ads_roi_low" not in codes
    assert "ads_budget_burn" in codes


def test_classify_budget_burn():
    hits = classify_ads_row(
        {
            "campaign_name": "烧预算",
            "spend": 90,
            "orders": 10,
            "revenue": 400,
            "roi": 4.4,
            "target_roi": 3.0,
            "daily_budget": 100,
            "avg_order_cost": 9,
            "biz_date": date(2026, 7, 29),
            "currency": "GBP",
        },
        **_base_kwargs(),
    )
    codes = [h["anomaly_code"] for h in hits]
    assert codes == ["ads_budget_burn"]
    assert hits[0]["priority"] == "P2"


def test_classify_budget_burn_over_100_is_p0():
    hits = classify_ads_row(
        {
            "campaign_name": "超预算",
            "spend": 120,
            "orders": 5,
            "revenue": 200,
            "roi": 1.67,
            "target_roi": 1.0,
            "daily_budget": 100,
            "avg_order_cost": 5,
            "biz_date": date(2026, 7, 29),
        },
        **_base_kwargs(global_min_roi=0.5),
    )
    burn = [h for h in hits if h["anomaly_code"] == "ads_budget_burn"]
    assert len(burn) == 1
    assert burn[0]["priority"] == "P0"


def test_classify_budget_missing_skip():
    hits = classify_ads_row(
        {
            "campaign_name": "无预算列",
            "spend": 90,
            "orders": 10,
            "revenue": 500,
            "roi": 5.5,
            "target_roi": 3.0,
            "daily_budget": None,
            "avg_order_cost": 5,
        },
        **_base_kwargs(),
    )
    assert all(h["anomaly_code"] != "ads_budget_burn" for h in hits)


def test_classify_cpa_high_abs():
    hits = classify_ads_row(
        {
            "campaign_name": "高CPA",
            "spend": 200,
            "orders": 10,
            "revenue": 800,
            "roi": 4.0,
            "target_roi": 3.0,
            "avg_order_cost": 20.0,
            "daily_budget": 500,
            "biz_date": date(2026, 7, 29),
            "currency": "GBP",
        },
        **_base_kwargs(max_cpa=15.0),
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "ads_cpa_high" in codes


def test_classify_cpa_high_vs_aov():
    """CPA 未达绝对阈，但占客单比过高。"""
    hits = classify_ads_row(
        {
            "campaign_name": "相对高CPA",
            "spend": 40,
            "orders": 10,
            "revenue": 80,  # AOV=8
            "roi": 2.0,
            "target_roi": 1.5,
            "avg_order_cost": 4.0,  # 4/8=0.5 >= 0.4
            "daily_budget": 200,
            "biz_date": date(2026, 7, 29),
        },
        **_base_kwargs(max_cpa=15.0, cpa_aov_ratio=0.4, global_min_roi=1.0),
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "ads_cpa_high" in codes


def test_classify_cpa_skip_on_no_sale():
    """空耗行不评 CPA。"""
    hits = classify_ads_row(
        {
            "campaign_name": "空耗不评CPA",
            "spend": 30,
            "orders": 0,
            "revenue": 0,
            "avg_order_cost": 99,
            "daily_budget": 100,
        },
        **_base_kwargs(),
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "ads_cpa_high" not in codes
    assert "ads_spend_no_sale" in codes


def test_classify_roi_and_cpa_stack():
    hits = classify_ads_row(
        {
            "campaign_name": "双命中",
            "spend": 100,
            "orders": 5,
            "revenue": 150,
            "roi": 1.5,
            "target_roi": 10.0,
            "avg_order_cost": 20,
            "daily_budget": 500,
            "biz_date": date(2026, 7, 29),
        },
        **_base_kwargs(),
    )
    codes = {h["anomaly_code"] for h in hits}
    assert "ads_roi_low" in codes
    assert "ads_cpa_high" in codes


@pytest.mark.asyncio
async def test_ads_eval_api_dry_run(client, auth_headers):
    r = await client.get(
        "/api/v1/tk/ads/anomaly-eval",
        headers=auth_headers,
        params={"biz_date": "2026-07-29", "dry_run": True},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["biz_date"] == "2026-07-29"
    assert data["scanned"] >= 1
    assert data["dry_run"] is True
    # 本机样本：至少应有空耗或低 ROI 之一
    assert data["hit_roi_low"] + data["hit_spend_no_sale"] >= 1
    assert "hit_budget_burn" in data
    assert "hit_cpa_high" in data
    assert "budget_burn_ratio" in (data.get("thresholds") or {})


@pytest.mark.asyncio
async def test_ads_eval_api_write_and_list(client, auth_headers):
    r = await client.post(
        "/api/v1/tk/ads/anomaly-eval",
        headers=auth_headers,
        json={
            "biz_date": "2026-07-29",
            "dry_run": False,
            "project_center_task": True,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created_or_updated"] >= 1
    assert not data.get("errors")

    r = await client.get(
        "/api/v1/tk/anomaly-tasks",
        headers=auth_headers,
        params={"anomaly_code": "ads_roi_low", "open_only": True, "page_size": 50},
    )
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    # 幂等：再跑一次不应爆炸
    r2 = await client.post(
        "/api/v1/tk/ads/anomaly-eval",
        headers=auth_headers,
        json={"biz_date": "2026-07-29", "dry_run": False},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["created_or_updated"] >= 1

    # 列表里应有广告类异常
    r = await client.get(
        "/api/v1/tk/anomaly-tasks",
        headers=auth_headers,
        params={"open_only": True, "page_size": 100},
    )
    codes = {i["anomaly_code"] for i in r.json()["items"]}
    assert "ads_roi_low" in codes or "ads_spend_no_sale" in codes
