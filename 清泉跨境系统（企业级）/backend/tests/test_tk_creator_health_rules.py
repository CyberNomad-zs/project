"""达人健康规则单元测试。"""

from __future__ import annotations

from datetime import date

from app.domain.tk_creator_health_rules import classify_creator_health_pair


def test_creator_drop():
    curr = {
        "shop_external_id": "s1",
        "shop_name": "Gardena",
        "creator_key": "Grace",
        "creator_name": "Grace",
        "biz_date": date(2026, 8, 11),
        "health_score": 170,
        "source_url": "https://example.com",
    }
    prev = {"health_score": 200}
    hits = classify_creator_health_pair(curr, prev)
    assert len(hits) == 1
    assert hits[0]["anomaly_code"] == "creator_health_drop"
    assert hits[0]["change_magnitude"] == 30


def test_creator_no_drop():
    curr = {
        "shop_external_id": "s1",
        "creator_key": "Grace",
        "creator_name": "Grace",
        "health_score": 200,
    }
    prev = {"health_score": 170}
    assert classify_creator_health_pair(curr, prev) == []
