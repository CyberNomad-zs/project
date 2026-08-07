"""tk_health_rules unit tests (no DB)."""

from __future__ import annotations

from app.domain.tk_health_rules import classify_health_pair, _should_notify


def test_drop_any_triggers():
    curr = {
        "shop_external_id": "s1",
        "shop_name": "Deal",
        "biz_date": "2026-08-06",
        "health_score": 260,
        "status_label": "健康",
        "source_url": "https://example/health",
    }
    prev = {
        "shop_external_id": "s1",
        "biz_date": "2026-08-05",
        "health_score": 277,
    }
    hits = classify_health_pair(curr, prev, low_threshold=150)
    codes = {h["anomaly_code"] for h in hits}
    assert codes == {"shop_health_drop"}
    assert hits[0]["change_magnitude"] == 17


def test_low_threshold_triggers_even_without_prev():
    curr = {
        "shop_external_id": "s1",
        "shop_name": "Deal",
        "biz_date": "2026-08-06",
        "health_score": 140,
    }
    hits = classify_health_pair(curr, None, low_threshold=150)
    assert [h["anomaly_code"] for h in hits] == ["shop_health_low"]
    assert hits[0]["priority"] == "P0"


def test_drop_and_low_both():
    curr = {
        "shop_external_id": "s1",
        "shop_name": "Deal",
        "biz_date": "2026-08-06",
        "health_score": 145,
    }
    prev = {"shop_external_id": "s1", "biz_date": "2026-08-05", "health_score": 160}
    hits = classify_health_pair(curr, prev, low_threshold=150)
    codes = {h["anomaly_code"] for h in hits}
    assert codes == {"shop_health_drop", "shop_health_low"}


def test_no_rise_no_hit():
    curr = {
        "shop_external_id": "s1",
        "shop_name": "Deal",
        "biz_date": "2026-08-06",
        "health_score": 280,
    }
    prev = {"shop_external_id": "s1", "biz_date": "2026-08-05", "health_score": 270}
    assert classify_health_pair(curr, prev, low_threshold=150) == []


def test_notify_only_on_worsen():
    hit = {"current_value": 250}
    assert _should_notify(code="shop_health_drop", hit=hit, existing=None) is True
    assert (
        _should_notify(
            code="shop_health_drop",
            hit=hit,
            existing={"current_value": 250},
        )
        is False
    )
    assert (
        _should_notify(
            code="shop_health_drop",
            hit={"current_value": 240},
            existing={"current_value": 250},
        )
        is True
    )
