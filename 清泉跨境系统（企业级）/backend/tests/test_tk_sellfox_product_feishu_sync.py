"""TK产品表 赛狐→PG→飞书同步 单测。

覆盖（对照 ACCEPTANCE F2-H1/F3-H1/E9-E12 + PLAN 验证计划）：
  - mapper 6 列输出正确（货源/品名/SKUID/上架状态/售价含VAT/采购GBP）
  - 13 公式列不在 fields（白名单是唯一防线，见 FINDINGS）
  - 采购成本 abs() 口径（负数 → 正数）
  - seller_sku 拆分匹配（profit_sku.sku_key ↔ seller_sku_part）
  - 缺数据告警格式（只含 SKU 列表，无金额）

纯函数单测，不连 DB / 不连飞书（不引 client/auth_headers fixture）。
"""
from __future__ import annotations

from app.adapters.feishu.bitable import tk_product_to_fields

# job 模块（测 seller_sku 拆分逻辑用 _PRODUCT_SELECT 字符串 + 缺数据告警）
from app.jobs.tk_sellfox_product_feishu_sync import _PRODUCT_SELECT, _notify_missing

# 飞书表 28 列名（从 EXPLORE §3 摘录；13 公式列清单）
_FORMULA_COLUMNS = {
    "平台价格",
    "售价（不含VAT）",
    "平台佣金",
    "头程GBP",
    "商品总成本GBP",
    "毛利润",
    "毛利润率",
    "退款率",
    "达人佣金",
    "广告费",
    "利润",
    "利润率",
    "保本单量",
}

# 不灌的手填/无数据列
_OMITTED_MANUAL = {
    "采购CNY",
    "头程CNY",
    "黑猫RM附加费",
    "亚马逊同款售价1",
    "亚马逊同款售价2",
    "服务费GBP",
    "操作费GBP",
    "配送费GBP",
    "SKU",
}

# mapper 应输出的 6 可写列
_EXPECTED_WRITABLE = {
    "货源",
    "品名",
    "SKUID",
    "上架状态",
    "售价（含VAT）（平台活动价）",
    "采购 GBP",
}


# ---------- mapper 6 列输出 ----------


def test_mapper_outputs_exactly_six_writable_columns():
    row = {
        "product_id": "100001",
        "product_name": "园艺剪 A",
        "seller_sku": "SKU-A-001",
        "status": "在售",
        "price_include_vat": "12.99",
        "purchase_fee_gbp": 5.20,
    }
    fields = tk_product_to_fields(row)
    assert set(fields.keys()) == _EXPECTED_WRITABLE


def test_mapper_values_basic():
    row = {
        "product_id": "100002",
        "product_name": "水管 50m",
        "seller_sku": "SKU-B-002",
        "status": "active",
        "price_include_vat": "29.5",
        "purchase_fee_gbp": 11.0,
    }
    fields = tk_product_to_fields(row)
    assert fields["货源"] == "100002"
    assert fields["品名"] == "水管 50m"
    assert fields["SKUID"] == "SKU-B-002"
    assert fields["上架状态"] == "已上架"
    assert fields["售价（含VAT）（平台活动价）"] == 29.5
    assert fields["采购 GBP"] == 11.0


# ---------- 13 公式列不在 fields（唯一防线）----------


def test_mapper_omits_all_13_formula_columns():
    """F3-H1 / E9：Formula 列 API 写不进，filter 不挡，mapper 必须自己 omit。"""
    row = {
        "product_id": "P1",
        "product_name": "X",
        "seller_sku": "S1",
        "status": "在售",
        "price_include_vat": "1.0",
        "purchase_fee_gbp": 0.5,
    }
    fields = tk_product_to_fields(row)
    leaked = _FORMULA_COLUMNS & set(fields.keys())
    assert not leaked, f"mapper 泄漏了公式列: {leaked}"


def test_mapper_omits_manual_columns():
    """手填/无数据列不灌（CNY/亚马逊/黑马/服务费/操作费/配送费/SKU）。"""
    row = {
        "product_id": "P2",
        "product_name": "Y",
        "seller_sku": "S2",
        "status": "在售",
        "price_include_vat": "1.0",
        "purchase_fee_gbp": 0.5,
    }
    fields = tk_product_to_fields(row)
    leaked = _OMITTED_MANUAL & set(fields.keys())
    assert not leaked, f"mapper 灌了不该灌的手填列: {leaked}"


# ---------- abs() 口径（负数成本 → 正数）----------


def test_mapper_purchase_fee_abs_positive():
    """E10：profit_sku purchaseFee 为负（利润扣除口径），飞书列要正数。"""
    # job 在 SQL 层已 abs()；这里验证 mapper 接到正数直接透传
    row = {
        "product_id": "P3",
        "product_name": "Z",
        "seller_sku": "S3",
        "status": "在售",
        "price_include_vat": "1.0",
        "purchase_fee_gbp": 7.3,  # 已 abs 的正数
    }
    fields = tk_product_to_fields(row)
    assert fields["采购 GBP"] == 7.3
    assert fields["采购 GBP"] > 0


def test_product_select_sql_uses_abs():
    """SQL 层对 purchaseFee 取 abs —— 口径双保险。"""
    assert "abs(CAST(raw_extra->>'purchaseFee' AS numeric))" in _PRODUCT_SELECT


# ---------- seller_sku 拆分匹配（| 拼接多规格）----------


def test_product_select_sql_splits_seller_sku_on_pipe():
    """E11：seller_sku 可能是 'A|B|C' 多规格拼接，profit_sku 按 sku_key 精确匹配任一。"""
    # LATERAL 子查询：sku_key = p.seller_sku OR sku_key = ANY(string_to_array(p.seller_sku, '|'))
    assert "string_to_array(p.seller_sku, '|')" in _PRODUCT_SELECT
    assert "s.sku_key = p.seller_sku" in _PRODUCT_SELECT


def test_product_select_takes_max_period_end():
    """D5：profit_sku 是区间聚合，取 period_end 最大一期。"""
    assert "ORDER BY s.period_end DESC" in _PRODUCT_SELECT
    assert "LIMIT 1" in _PRODUCT_SELECT


def test_product_select_filters_in_sell():
    """在售过滤：status ∈ (在售/active/在线)。"""
    assert "p.status = ANY(:statuses)" in _PRODUCT_SELECT


# ---------- 缺数据告警格式（无金额）----------


async def test_notify_missing_no_amounts_when_webhook(monkeypatch):
    """F5 / E12：缺数据告警只含 SKU 列表，不含任何金额。

    即便 webhook 配置了，告警消息也不能出现 purchase_fee / price / 金额数字。
    """
    captured = {}

    class _FakeResp:
        def json(self):
            return {"code": 0}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            captured["url"] = url
            captured["payload"] = json
            return _FakeResp()

    import app.jobs.tk_sellfox_product_feishu_sync as mod

    monkeypatch.setattr(mod.httpx, "AsyncClient", _FakeClient)

    stats = {"created": 5, "updated": 0, "skipped_no_sellfox": 3, "failed": 0}
    missing = ["SKU-NO-1", "SKU-NO-2", "SKU-NO-3"]

    await _notify_missing("https://example.com/webhook", missing, stats)

    assert captured["url"] == "https://example.com/webhook"
    text = captured["payload"]["content"]["text"]
    # SKU 列表在告警里
    for sku in missing:
        assert sku in text
    # 缺数据数量在告警里
    assert "3" in text
    # 绝不含金额字段名
    assert "采购" not in text
    assert "purchase" not in text.lower()
    assert "fee" not in text.lower()
    assert "price" not in text.lower()
    assert "金额" not in text


async def test_notify_missing_log_only_when_no_webhook(monkeypatch, caplog):
    """webhook 空 → 只落日志，不发请求。"""
    import logging

    import app.jobs.tk_sellfox_product_feishu_sync as mod

    called = {"post": False}

    class _FakeClient:
        def __init__(self, *a, **kw):
            called["instantiated"] = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            called["post"] = True

    monkeypatch.setattr(mod.httpx, "AsyncClient", _FakeClient)

    with caplog.at_level(logging.WARNING, logger="qingquan.tk_sellfox_product_feishu_sync"):
        await _notify_missing("", ["SKU-X"], {"created": 0, "failed": 0})

    # 空 webhook 不应实例化 client / 不应 post
    assert not called.get("post")
    assert any("webhook 未配置" in r.message for r in caplog.records)


async def test_notify_missing_noop_when_no_missing_skus(monkeypatch):
    """无缺数据 SKU → 直接返回，不发请求。"""
    instantiated = {"v": False}

    class _FakeClient:
        def __init__(self, *a, **kw):
            instantiated["v"] = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    import app.jobs.tk_sellfox_product_feishu_sync as mod

    monkeypatch.setattr(mod.httpx, "AsyncClient", _FakeClient)
    await _notify_missing("https://example.com/webhook", [], {})
    assert not instantiated["v"]


# ---------- mapper 边界 ----------


def test_mapper_omit_none_when_fields_empty():
    """缺采购成本（None）→ 采购 GBP 列被 omit（不灌空）。"""
    row = {
        "product_id": "P4",
        "product_name": "W",
        "seller_sku": "S4",
        "status": "在售",
        "price_include_vat": None,
        "purchase_fee_gbp": None,
    }
    fields = tk_product_to_fields(row)
    assert "采购 GBP" not in fields
    assert "售价（含VAT）（平台活动价）" not in fields
    # 主数据仍在
    assert fields["货源"] == "P4"
    assert fields["品名"] == "W"
    assert fields["SKUID"] == "S4"
    assert fields["上架状态"] == "已上架"


def test_mapper_status_map_variants():
    """状态枚举映射：在售/active/在线 → 已上架；已下架/inactive → 已下架；草稿/draft → 未上架。"""
    base = {"product_id": "P", "product_name": "N", "seller_sku": "S",
            "price_include_vat": "1", "purchase_fee_gbp": 0.1}
    assert tk_product_to_fields({**base, "status": "在售"})["上架状态"] == "已上架"
    assert tk_product_to_fields({**base, "status": "active"})["上架状态"] == "已上架"
    assert tk_product_to_fields({**base, "status": "在线"})["上架状态"] == "已上架"
    assert tk_product_to_fields({**base, "status": "已下架"})["上架状态"] == "已下架"
    assert tk_product_to_fields({**base, "status": "inactive"})["上架状态"] == "已下架"
    assert tk_product_to_fields({**base, "status": "草稿"})["上架状态"] == "未上架"
    assert tk_product_to_fields({**base, "status": "draft"})["上架状态"] == "未上架"


def test_mapper_status_unknown_falls_back_to_raw():
    """未知状态：原样透传（不强行映射），由飞书表侧展示。"""
    base = {"product_id": "P", "product_name": "N", "seller_sku": "S",
            "price_include_vat": "1", "purchase_fee_gbp": 0.1}
    fields = tk_product_to_fields({**base, "status": "审核中"})
    assert fields["上架状态"] == "审核中"
