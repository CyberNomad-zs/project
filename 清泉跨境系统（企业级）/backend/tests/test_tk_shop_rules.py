"""TK 店铺分析异常规则单元测试。"""

from __future__ import annotations

from datetime import date

from app.domain.tk_shop_rules import classify_shop_pair, _drop_ratio


def test_drop_ratio_basic():
    assert _drop_ratio(70, 100) == 0.3
    assert _drop_ratio(100, 100) is None
    assert _drop_ratio(120, 100) is None
    assert _drop_ratio(50, 0) is None
    assert _drop_ratio(None, 100) is None


def test_classify_gmv_drop():
    hits = classify_shop_pair(
        {
            "shop_external_id": "27501502216807",
            "shop_name": "Deal to deal",
            "biz_date": date(2026, 8, 3),
            "gmv": 300.0,
            "orders_cnt": 20,
            "currency": "GBP",
        },
        {
            "shop_external_id": "27501502216807",
            "biz_date": date(2026, 8, 2),
            "gmv": 1000.0,
            "orders_cnt": 20,
            "currency": "GBP",
        },
        gmv_drop_ratio=0.3,
        order_drop_ratio=0.3,
        min_gmv_base=50.0,
        min_orders_base=3.0,
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "shop_gmv_drop" in codes
    gmv_hit = next(h for h in hits if h["anomaly_code"] == "shop_gmv_drop")
    assert gmv_hit["priority"] == "P0"  # 70% drop
    assert "店铺GMV骤降" in gmv_hit["summary"]


def test_classify_order_drop():
    hits = classify_shop_pair(
        {
            "shop_external_id": "27328767468273",
            "shop_name": "Gardena",
            "biz_date": date(2026, 8, 3),
            "gmv": 900.0,
            "orders_cnt": 5,
            "currency": "GBP",
        },
        {
            "shop_external_id": "27328767468273",
            "biz_date": date(2026, 8, 2),
            "gmv": 1000.0,
            "orders_cnt": 20,
            "currency": "GBP",
        },
        gmv_drop_ratio=0.3,
        order_drop_ratio=0.3,
        min_gmv_base=50.0,
        min_orders_base=3.0,
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "shop_order_drop" in codes
    assert "shop_gmv_drop" not in codes  # 10% only


def test_classify_both_hits():
    hits = classify_shop_pair(
        {
            "shop_external_id": "s1",
            "shop_name": "X",
            "biz_date": date(2026, 8, 3),
            "gmv": 200.0,
            "orders_cnt": 4,
            "currency": "GBP",
        },
        {
            "shop_external_id": "s1",
            "biz_date": date(2026, 8, 2),
            "gmv": 1000.0,
            "orders_cnt": 20,
            "currency": "GBP",
        },
        gmv_drop_ratio=0.3,
        order_drop_ratio=0.3,
        min_gmv_base=50.0,
        min_orders_base=3.0,
    )
    codes = {h["anomaly_code"] for h in hits}
    assert codes == {"shop_gmv_drop", "shop_order_drop"}


def test_classify_skip_small_base():
    hits = classify_shop_pair(
        {
            "shop_external_id": "s2",
            "shop_name": "Tiny",
            "biz_date": date(2026, 8, 3),
            "gmv": 1.0,
            "orders_cnt": 0,
            "currency": "GBP",
        },
        {
            "shop_external_id": "s2",
            "biz_date": date(2026, 8, 2),
            "gmv": 10.0,  # below min_gmv_base=50
            "orders_cnt": 1,  # below min_orders_base=3
            "currency": "GBP",
        },
        gmv_drop_ratio=0.3,
        order_drop_ratio=0.3,
        min_gmv_base=50.0,
        min_orders_base=3.0,
    )
    assert hits == []


def test_classify_no_drop():
    hits = classify_shop_pair(
        {
            "shop_external_id": "s3",
            "shop_name": "OK",
            "biz_date": date(2026, 8, 3),
            "gmv": 1100.0,
            "orders_cnt": 22,
            "currency": "GBP",
        },
        {
            "shop_external_id": "s3",
            "biz_date": date(2026, 8, 2),
            "gmv": 1000.0,
            "orders_cnt": 20,
            "currency": "GBP",
        },
        gmv_drop_ratio=0.3,
        order_drop_ratio=0.3,
        min_gmv_base=50.0,
        min_orders_base=3.0,
    )
    assert hits == []


def test_classify_missing_prev():
    hits = classify_shop_pair(
        {
            "shop_external_id": "s4",
            "shop_name": "New",
            "biz_date": date(2026, 8, 3),
            "gmv": 100.0,
            "orders_cnt": 5,
        },
        None,
        gmv_drop_ratio=0.3,
        order_drop_ratio=0.3,
        min_gmv_base=50.0,
        min_orders_base=3.0,
    )
    assert hits == []


def test_classify_skip_test_shop():
    hits = classify_shop_pair(
        {
            "shop_external_id": "s5",
            "shop_name": "[test] smoke",
            "biz_date": date(2026, 8, 3),
            "gmv": 10.0,
            "orders_cnt": 1,
        },
        {
            "shop_external_id": "s5",
            "biz_date": date(2026, 8, 2),
            "gmv": 1000.0,
            "orders_cnt": 50,
        },
        gmv_drop_ratio=0.3,
        order_drop_ratio=0.3,
        min_gmv_base=50.0,
        min_orders_base=3.0,
    )
    assert hits == []
