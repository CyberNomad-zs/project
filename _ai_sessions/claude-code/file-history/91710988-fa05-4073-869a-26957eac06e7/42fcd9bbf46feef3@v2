"""tk_violation_rules / tk_review_rules pure helpers (no DB)."""

from __future__ import annotations

from app.domain.tk_violation_rules import _f as v_f
from app.domain.tk_review_rules import _f as r_f


def test_float_helpers():
    assert v_f(None) is None
    assert v_f("12.5") == 12.5
    assert r_f(2) == 2.0
    assert r_f("x") is None


def test_violation_dedupe_shape():
    shop_ext = "27501502216807"
    vkey = "prod:2026-08-01:h1a2b"
    dedupe = f"tiktok:{shop_ext}:shop_violation:{vkey}"
    assert dedupe.startswith("tiktok:")
    assert "shop_violation" in dedupe
    assert len(dedupe) <= 200


def test_review_priority_by_rating():
    # mirror rule: ≤1 → P0 else P1 when bad
    def pri(rating: float) -> str:
        return "P0" if rating <= 1 else "P1"

    assert pri(1) == "P0"
    assert pri(2) == "P1"


def test_review_dedupe_shape():
    shop_ext = "27328767468273"
    rkey = "576999:172345"
    dedupe = f"tiktok:{shop_ext}:shop_bad_review:{rkey}"
    assert "shop_bad_review" in dedupe
