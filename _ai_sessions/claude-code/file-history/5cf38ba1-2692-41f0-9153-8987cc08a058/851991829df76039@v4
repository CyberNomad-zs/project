"""Unit tests for TikTok order time / biz_date helpers (no DB)."""

from __future__ import annotations

from datetime import date, datetime

from app.api.ingest import _parse_optional_dt, _safe_biz_date


def test_parse_rejects_delivery_deadline():
    assert _parse_optional_dt("送达截止日期：2026/8/3 23:59:59") is None
    assert _parse_optional_dt("delivery by 2026/08/05") is None


def test_parse_weekday_cn():
    # 2026-07-31 is Friday
    ref = datetime(2026, 7, 31, 12, 0, 0)
    dt = _parse_optional_dt("星期一 23:32:30", ref=ref)
    assert dt is not None
    assert dt.date() == date(2026, 7, 27)  # last Monday on/before Fri
    assert dt.hour == 23 and dt.minute == 32


def test_parse_glued_order_id_relative():
    ref = datetime(2026, 7, 31, 15, 0, 0)
    # 18 位订单号 + 「28 分钟前」粘连（无分隔）
    dt = _parse_optional_dt("57693060796603472428 分钟前", ref=ref)
    assert dt is not None
    assert dt == datetime(2026, 7, 31, 14, 32, 0)
    dt2 = _parse_optional_dt("57693060513795891545 分钟前", ref=ref)
    assert dt2 == datetime(2026, 7, 31, 14, 15, 0)
    assert _parse_optional_dt("28 分钟前", ref=ref) == datetime(2026, 7, 31, 14, 32, 0)


def test_parse_glued_order_id_weekday():
    ref = datetime(2026, 7, 31, 12, 0, 0)  # Friday
    dt = _parse_optional_dt("576928076120365530星期六 15:29:41", ref=ref)
    assert dt is not None
    assert dt.date() == date(2026, 7, 25)
    assert dt.hour == 15 and dt.minute == 29



def test_safe_biz_date_drops_future():
    collected = datetime(2026, 7, 31, 10, 0, 0)
    future = datetime(2026, 8, 5, 12, 0, 0)
    assert (
        _safe_biz_date(
            explicit=None,
            pay_time=None,
            create_time=future,
            collected_at=collected,
        )
        is None
    )
    ok = datetime(2026, 7, 29, 8, 0, 0)
    assert (
        _safe_biz_date(
            explicit=None,
            pay_time=None,
            create_time=ok,
            collected_at=collected,
        )
        == date(2026, 7, 29)
    )


def test_safe_biz_date_prefers_explicit_if_sane():
    collected = datetime(2026, 7, 31, 10, 0, 0)
    assert (
        _safe_biz_date(
            explicit=date(2026, 7, 28),
            pay_time=None,
            create_time=None,
            collected_at=collected,
        )
        == date(2026, 7, 28)
    )
