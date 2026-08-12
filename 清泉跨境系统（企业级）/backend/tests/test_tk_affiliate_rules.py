"""TK 达人表现异常规则单元测试。"""

from __future__ import annotations

from datetime import date

from app.domain.tk_affiliate_rules import (
    classify_creator_row,
    classify_shop_affiliate_pair,
    _drop_ratio,
)


def test_drop_ratio_basic():
    assert _drop_ratio(70, 100) == 0.3
    assert _drop_ratio(100, 100) is None


def test_classify_invest_no_sale():
    hits = classify_creator_row(
        {
            "shop_external_id": "27501502216807",
            "shop_name": "Deal to deal",
            "biz_date": date(2026, 8, 4),
            "window_label": "近7天",
            "creator_id": "noorder_creator",
            "creator_handle": "noorder_creator",
            "creator_name": "No Sale",
            "gmv": 0,
            "order_units": 0,
            "orders_cnt": 0,
            "est_commission": 5.0,
            "sold_flag": False,
            "currency": "GBP",
        },
        None,
        gmv_drop_ratio=0.3,
        min_gmv_base=5.0,
        min_commission_invest=1.0,
        refund_ratio=0.5,
        min_gmv_for_refund=10.0,
    )
    codes = [h["anomaly_code"] for h in hits]
    assert codes == ["creator_invest_no_sale"]
    assert "有投入无成交" in hits[0]["summary"]


def test_classify_invest_no_sale_skips_without_commission():
    """投流/寄样金额暂不采：无预计佣金不得报有投入无成交。"""
    hits = classify_creator_row(
        {
            "shop_external_id": "s1",
            "shop_name": "X",
            "biz_date": date(2026, 8, 4),
            "creator_id": "c1",
            "gmv": 0,
            "order_units": 0,
            "est_commission": None,
            "samples_shipped": 3,
            "sold_flag": False,
            "currency": "GBP",
        },
        None,
        gmv_drop_ratio=0.3,
        min_gmv_base=5.0,
        min_commission_invest=1.0,
        refund_ratio=0.5,
        min_gmv_for_refund=10.0,
    )
    assert hits == []


def test_classify_gmv_drop():
    hits = classify_creator_row(
        {
            "shop_external_id": "s1",
            "shop_name": "Gardena",
            "biz_date": date(2026, 8, 5),
            "window_label": "近7天",
            "creator_id": "countrylass65",
            "creator_handle": "countrylass65",
            "gmv": 10.0,
            "order_units": 1,
            "est_commission": 0.5,
            "sold_flag": True,
            "currency": "GBP",
        },
        {
            "shop_external_id": "s1",
            "biz_date": date(2026, 8, 4),
            "creator_id": "countrylass65",
            "gmv": 69.1,
            "currency": "GBP",
        },
        gmv_drop_ratio=0.3,
        min_gmv_base=5.0,
        min_commission_invest=1.0,
        refund_ratio=0.5,
        min_gmv_for_refund=10.0,
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "creator_gmv_drop" in codes
    gmv_hit = next(h for h in hits if h["anomaly_code"] == "creator_gmv_drop")
    assert gmv_hit["priority"] == "P0"
    assert "归因GMV骤降" in gmv_hit["summary"]


def test_classify_refund_high():
    hits = classify_creator_row(
        {
            "shop_external_id": "s1",
            "shop_name": "X",
            "biz_date": date(2026, 8, 4),
            "creator_id": "c2",
            "gmv": 100.0,
            "order_units": 5,
            "refund_amount": 60.0,
            "est_commission": 2.0,
            "sold_flag": True,
            "currency": "GBP",
        },
        None,
        gmv_drop_ratio=0.3,
        min_gmv_base=5.0,
        min_commission_invest=1.0,
        refund_ratio=0.5,
        min_gmv_for_refund=10.0,
    )
    codes = [h["anomaly_code"] for h in hits]
    assert "creator_refund_high" in codes


def test_classify_creators_sold_drop():
    hits = classify_shop_affiliate_pair(
        {
            "shop_external_id": "s1",
            "shop_name": "Deal",
            "biz_date": date(2026, 8, 5),
            "window_label": "近7天",
            "creators_sold": 2,
        },
        {
            "shop_external_id": "s1",
            "biz_date": date(2026, 8, 4),
            "window_label": "近7天",
            "creators_sold": 10,
        },
        creators_sold_drop_ratio=0.3,
        min_creators_sold_base=3.0,
    )
    assert len(hits) == 1
    assert hits[0]["anomaly_code"] == "affiliate_creators_sold_drop"
    assert hits[0]["priority"] == "P0"


def test_classify_skip_test_shop():
    hits = classify_creator_row(
        {
            "shop_external_id": "s2",
            "shop_name": "[test] skip",
            "biz_date": date(2026, 8, 4),
            "creator_id": "c",
            "gmv": 0,
            "est_commission": 9.0,
            "sold_flag": False,
        },
        None,
        gmv_drop_ratio=0.3,
        min_gmv_base=5.0,
        min_commission_invest=1.0,
        refund_ratio=0.5,
        min_gmv_for_refund=10.0,
    )
    assert hits == []
