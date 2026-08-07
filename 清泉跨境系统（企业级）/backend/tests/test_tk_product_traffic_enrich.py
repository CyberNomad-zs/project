"""商品卡 traffic：raw_cells / 英文表头回填 impressions·cvr·gmv。"""

from __future__ import annotations

from app.api.ingest import _enrich_traffic_from_raw_cells, _parse_metric_number


def test_parse_metric_number_units_and_pct():
    assert _parse_metric_number("44.62K") == 44620
    assert abs(_parse_metric_number("0.10%") - 0.10) < 1e-9
    assert abs(_parse_metric_number("£480.20") - 480.20) < 1e-9
    assert _parse_metric_number("1.2万") == 12000
    assert _parse_metric_number("-") is None


def test_enrich_from_raw_cells_shape_only():
    m = _enrich_traffic_from_raw_cells(
        impressions=None,
        clicks=None,
        ctr=None,
        orders_cnt=None,
        gmv=None,
        cvr=None,
        customers=None,
        raw_cells=[
            "Deluxe Spray Mop ID: 1729763395058833584",
            "£480.20",
            "0.10%",
            "44.62K",
            "Details",
        ],
    )
    assert abs(m["gmv"] - 480.20) < 1e-9
    assert abs(m["cvr"] - 0.10) < 1e-9
    assert abs(m["impressions"] - 44620) < 1e-9


def test_enrich_from_english_headers():
    m = _enrich_traffic_from_raw_cells(
        impressions=None,
        clicks=None,
        ctr=None,
        orders_cnt=None,
        gmv=None,
        cvr=None,
        customers=None,
        raw_cells=["name", "£12.00", "0.09%", "11.40K", "Details"],
        table_headers=["Product card name", "GMV", "View-to-paid rate", "Viewers", "Action"],
    )
    assert abs(m["gmv"] - 12.0) < 1e-9
    assert abs(m["cvr"] - 0.09) < 1e-9
    assert abs(m["impressions"] - 11400) < 1e-9


def test_enrich_keeps_existing_metrics():
    m = _enrich_traffic_from_raw_cells(
        impressions=100.0,
        clicks=None,
        ctr=None,
        orders_cnt=None,
        gmv=9.0,
        cvr=1.5,
        customers=None,
        raw_cells=["x", "£999.00", "9.99%", "99.9K", "Details"],
    )
    assert m["impressions"] == 100.0
    assert m["gmv"] == 9.0
    assert m["cvr"] == 1.5
