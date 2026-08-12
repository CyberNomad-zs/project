"""体验分规则单元测试。"""

from __future__ import annotations

from datetime import date

from app.domain.tk_experience_rules import classify_experience_pair, _is_worse


def test_is_worse_higher_better():
    assert _is_worse("experience_score", 3.8, 3.9) is True
    assert _is_worse("experience_score", 3.9, 3.8) is False


def test_is_worse_lower_better():
    assert _is_worse("cancel_rate", 0.02, 0.01) is True
    assert _is_worse("cancel_rate", 0.01, 0.02) is False


def test_classify_score_drop():
    curr = {
        "shop_external_id": "s1",
        "shop_name": "Demo",
        "biz_date": date(2026, 8, 11),
        "experience_score": 3.8,
        "product_satisfaction": 4.0,
        "fulfillment_score": 4.5,
        "customer_service_score": 2.4,
        "metrics_json": {},
        "source_url": "https://example.com",
    }
    prev = {
        "shop_external_id": "s1",
        "experience_score": 3.9,
        "product_satisfaction": 4.0,
        "fulfillment_score": 4.5,
        "customer_service_score": 2.5,
        "metrics_json": {},
    }
    hits = classify_experience_pair(curr, prev)
    codes = {h["anomaly_code"] for h in hits}
    assert "shop_experience_drop" in codes
    assert "shop_experience_metric_worse" in codes


def test_classify_no_prev_no_drop():
    curr = {
        "shop_external_id": "s1",
        "shop_name": "Demo",
        "biz_date": date(2026, 8, 11),
        "experience_score": 3.8,
        "product_satisfaction": 4.0,
        "fulfillment_score": 4.5,
        "customer_service_score": 2.5,
        "metrics_json": {},
    }
    assert classify_experience_pair(curr, None) == []
