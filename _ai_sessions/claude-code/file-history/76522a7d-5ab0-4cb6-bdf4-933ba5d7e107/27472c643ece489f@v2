"""TK 视频内容异常规则单元测试。"""

from __future__ import annotations

from datetime import date

from app.domain.tk_content_rules import classify_content_pair, _drop_ratio


def test_drop_ratio_basic():
    assert _drop_ratio(70, 100) == 0.3
    assert _drop_ratio(100, 100) is None
    assert _drop_ratio(None, 100) is None


def test_classify_gmv_drop():
    hits = classify_content_pair(
        {
            "shop_external_id": "27328767468273",
            "shop_name": "Gardena",
            "biz_date": date(2026, 8, 5),
            "channel": "short_video",
            "content_id": "7669398982145215766",
            "content_title": "Hot seller video",
            "attributed_gmv": 10.0,
            "attributed_sku_orders": 1,
            "play_count": 4000,
            "impressions": 4100,
            "currency": "GBP",
        },
        {
            "shop_external_id": "27328767468273",
            "biz_date": date(2026, 8, 4),
            "channel": "short_video",
            "content_id": "7669398982145215766",
            "attributed_gmv": 44.95,
            "attributed_sku_orders": 3,
            "play_count": 4800,
            "impressions": 4970,
            "currency": "GBP",
        },
        gmv_drop_ratio=0.3,
        play_drop_ratio=0.3,
        min_gmv_base=5.0,
        min_play_base=50.0,
        min_impressions_for_no_order=200.0,
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "content_gmv_drop" in codes
    gmv_hit = next(h for h in hits if h["anomaly_code"] == "content_gmv_drop")
    assert gmv_hit["priority"] == "P0"  # ~78% drop
    assert "视频归因GMV骤降" in gmv_hit["summary"]


def test_classify_play_drop():
    hits = classify_content_pair(
        {
            "shop_external_id": "s1",
            "shop_name": "X",
            "biz_date": date(2026, 8, 5),
            "channel": "short_video",
            "content_id": "c1",
            "content_title": "t",
            "attributed_gmv": 5.0,
            "attributed_sku_orders": 1,
            "play_count": 100,
            "impressions": 120,
            "currency": "GBP",
        },
        {
            "shop_external_id": "s1",
            "biz_date": date(2026, 8, 4),
            "content_id": "c1",
            "attributed_gmv": 5.0,
            "play_count": 1000,
            "impressions": 1100,
            "currency": "GBP",
        },
        gmv_drop_ratio=0.3,
        play_drop_ratio=0.3,
        min_gmv_base=5.0,
        min_play_base=50.0,
        min_impressions_for_no_order=5000.0,
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "content_play_drop" in codes
    assert "content_gmv_drop" not in codes


def test_classify_imp_no_order():
    hits = classify_content_pair(
        {
            "shop_external_id": "s1",
            "shop_name": "X",
            "biz_date": date(2026, 8, 5),
            "channel": "short_video",
            "content_id": "c2",
            "content_title": "no sale",
            "attributed_gmv": 0,
            "attributed_sku_orders": 0,
            "play_count": 800,
            "impressions": 900,
            "currency": "GBP",
        },
        None,
        gmv_drop_ratio=0.3,
        play_drop_ratio=0.3,
        min_gmv_base=5.0,
        min_play_base=50.0,
        min_impressions_for_no_order=200.0,
    )
    codes = [h["anomaly_code"] for h in hits]
    assert codes == ["content_imp_no_order"]


def test_classify_skip_small_base_and_test_shop():
    hits = classify_content_pair(
        {
            "shop_external_id": "s2",
            "shop_name": "[test] skip",
            "biz_date": date(2026, 8, 5),
            "channel": "short_video",
            "content_id": "c3",
            "attributed_gmv": 0,
            "play_count": 1,
            "impressions": 1,
        },
        {
            "biz_date": date(2026, 8, 4),
            "attributed_gmv": 100,
            "play_count": 1000,
            "impressions": 1000,
        },
        gmv_drop_ratio=0.3,
        play_drop_ratio=0.3,
        min_gmv_base=5.0,
        min_play_base=50.0,
        min_impressions_for_no_order=200.0,
    )
    assert hits == []
