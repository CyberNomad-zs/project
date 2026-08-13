"""飞书 tenant token 与 Bitable 写入（Phase0 MVP）。"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

BASE = "https://open.feishu.cn/open-apis"


class FeishuError(RuntimeError):
    pass


async def get_tenant_access_token() -> str | None:
    settings = get_settings()
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        return None
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuError(f"token failed: {data}")
        return data["tenant_access_token"]


def content_hash(fields: dict[str, Any]) -> str:
    raw = json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def batch_create_records(
    token: str,
    app_token: str,
    table_id: str,
    records: list[dict[str, Any]],
) -> list[str]:
    """返回 record_id 列表。"""
    if not records:
        return []
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            headers={"Authorization": f"Bearer {token}"},
            json={"records": [{"fields": r} for r in records]},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuError(f"batch_create failed: {data}")
        return [item["record_id"] for item in data.get("data", {}).get("records", [])]


async def batch_update_records(
    token: str,
    app_token: str,
    table_id: str,
    items: list[tuple[str, dict[str, Any]]],
) -> None:
    if not items:
        return
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "records": [
                    {"record_id": rid, "fields": fields} for rid, fields in items
                ]
            },
        )
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuError(f"batch_update failed: {data}")


def task_to_fields(task: dict[str, Any]) -> dict[str, Any]:
    """映射到飞书列名（需与多维表一致，可按环境改别名）。"""
    return {
        "平台": task.get("platform") or "",
        "业务ID": task.get("biz_id") or "",
        "异常类型": task.get("anomaly_type") or "",
        "标题": task.get("title") or "",
        "状态": task.get("status") or "",
        "进度": task.get("progress_note") or "",
        "去重键": task.get("dedupe_key") or "",
    }


def _feishu_date(value: Any) -> int | None:
    """多维表日期/日期时间字段：Unix 毫秒。"""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        # 已是 ms 或 s
        v = int(value)
        return v if v > 10_000_000_000 else v * 1000
    if hasattr(value, "timestamp"):
        # date/datetime
        from datetime import date, datetime, timezone

        if isinstance(value, datetime):
            dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        if isinstance(value, date):
            dt = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
    s = str(value).strip()
    if not s:
        return None
    from datetime import date, datetime, timezone

    try:
        if "T" in s or " " in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        d = date.fromisoformat(s[:10])
        dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _omit_none(fields: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None and v != ""}


def amz_shop_daily_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    """fact_amz_shop_daily → 飞书 T1「店铺日经营」列名。"""
    return _omit_none(
        {
            "日期": _feishu_date(row.get("biz_date")),
            "店铺": row.get("shop_name") or "",
            "店铺ID": row.get("shop_external_id") or "",
            "站点": row.get("marketplace") or "",
            "币种": row.get("currency") or "",
            "销售额": _num(row.get("sales_amount")),
            "订单量": _num(row.get("orders_cnt")),
            "销量": _num(row.get("units")),
            "访客数": _num(row.get("sessions")),
            "加购数": _num(row.get("add_to_cart")),
            "客单价": _num(row.get("aov")),
            "退货量": _num(row.get("refund_units")),
            "退货率": _num(row.get("refund_rate")),
            "毛利": _num(row.get("gross_profit")),
            "广告花费": _num(row.get("ad_spend")),
            "广告销售额": _num(row.get("ad_sales")),
            "ACoS": _num(row.get("acos")),
            "广告贡献毛利": _num(row.get("ad_contrib_margin")),
            "净利润": _num(row.get("net_profit")),
            "净利率": _num(row.get("net_margin")),
            "ROI": _num(row.get("roi")),
            "销售额环比": _num(row.get("sales_mom_ratio")),
            "利润环比": _num(row.get("profit_mom_ratio")),
            "销售额同比": _num(row.get("sales_yoy_ratio")),
            "数据状态": row.get("row_status") or "success",
            "抓取时间": _feishu_date(row.get("collected_at")),
            "数据源": row.get("source_url") or "",
            "本地ID": str(row.get("id") or ""),
        }
    )


def amz_link_daily_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    """fact_amz_link_daily → 飞书 T3「链接日指标」列名。"""
    return _omit_none(
        {
            "日期": _feishu_date(row.get("biz_date")),
            "店铺ID": row.get("shop_external_id") or "",
            "ASIN": row.get("asin") or "",
            "SKU": row.get("seller_sku") or "",
            "标题": row.get("title") or "",
            "类目": row.get("category") or "",
            "销量": _num(row.get("units")),
            "销售额": _num(row.get("sales_amount")),
            "币种": row.get("currency") or "",
            "访客数": _num(row.get("sessions")),
            "广告花费": _num(row.get("ad_spend")),
            "ACoS": _num(row.get("acos")),
            "单品净利润": _num(row.get("unit_net_profit")),
            "FBA可售": _num(row.get("fba_fulfillable")),
            "可售天数": _num(row.get("days_of_supply")),
            "退货率": _num(row.get("refund_rate")),
            "销量环比": _num(row.get("units_mom_ratio")),
            "销售额环比": _num(row.get("sales_mom_ratio")),
            "问题标签": row.get("problem_tags") or "",
            "第一负责人": row.get("owner_name") or "",
            "抓取时间": _feishu_date(row.get("collected_at")),
            "本地ID": str(row.get("id") or ""),
        }
    )


_RISK_STATUS_CN = {
    "open": "未处理",
    "in_progress": "处理中",
    "resolved": "已闭环",
    "ignored": "忽略",
}


def amz_risk_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    """fact_amz_risk_alert → 飞书 T6「风险告警」列名。"""
    st = row.get("status") or "open"
    return _omit_none(
        {
            "告警ID": row.get("alert_key") or "",
            "发现日期": _feishu_date(row.get("detected_on")),
            "店铺": row.get("shop_name") or "",
            "店铺ID": row.get("shop_external_id") or "",
            "对象": row.get("object_ref") or "",
            "风险类型": row.get("risk_type") or "",
            "优先级": row.get("priority") or "P1",
            "摘要": row.get("summary") or "",
            "指标快照": row.get("metric_snapshot") or "",
            "状态": _RISK_STATUS_CN.get(str(st), str(st)),
            "第一负责人": row.get("owner_name") or "",
            "关联任务ID": str(row.get("task_id") or "") if row.get("task_id") else "",
            "更新时间": _feishu_date(row.get("updated_at")),
            "本地ID": str(row.get("id") or ""),
        }
    )


_PLAN_STATUS_CN = {
    "on": "投放中",
    "off": "已关闭",
    "unknown": "未知",
    "投放中": "投放中",
    "已关闭": "已关闭",
    "未知": "未知",
}


def _profit_tag(roi: float | None, spend: float | None, revenue: float | None, target_roi: float | None) -> str:
    """高ROI / 正常 / 低效亏损（写入前打标，阈值默认 3 或目标 ROI）。"""
    sp = float(spend or 0)
    rev = float(revenue or 0)
    if sp > 0 and rev <= 0:
        return "低效亏损"
    if roi is None and sp > 0:
        roi = rev / sp if sp else None
    if roi is None:
        return "正常"
    thr = float(target_roi) if target_roi is not None and float(target_roi) > 0 else 3.0
    if float(roi) >= thr:
        return "高ROI"
    if float(roi) > 0:
        return "低效亏损"
    return "低效亏损"


def tk_shop_daily_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    """店日宽表（shop + ads rollup + health/finance）→ 飞书 T1「店铺日经营」。"""
    gmv = _num(row.get("gmv"))
    orders = _num(row.get("orders_cnt"))
    ad_spend = _num(row.get("ad_spend")) or 0.0
    ad_revenue = _num(row.get("ad_revenue")) or 0.0
    ad_orders = _num(row.get("ad_orders")) or 0.0
    aov = None
    if gmv is not None and orders and orders > 0:
        aov = gmv / orders
    ad_roi = None
    if ad_spend and ad_spend > 0:
        ad_roi = ad_revenue / ad_spend
    shop_cur = (row.get("currency") or "").strip()
    ad_cur = (row.get("ad_currency") or "").strip()
    organic_orders = None
    organic_sales = None
    if orders is not None:
        organic_orders = max(orders - ad_orders, 0.0)
    # 自然销售额仅同币种时估算，避免 USD 广告销售与 GBP GMV 相减
    if gmv is not None and shop_cur and ad_cur and shop_cur.upper() == ad_cur.upper():
        organic_sales = max(gmv - ad_revenue, 0.0)

    return _omit_none(
        {
            "日期": _feishu_date(row.get("biz_date")),
            "店铺": row.get("shop_name") or "",
            "店铺ID": row.get("shop_external_id") or "",
            "币种": shop_cur,
            "销售额": gmv,
            "订单量": orders,
            "买家数": _num(row.get("buyers_cnt")),
            "退款金额": _num(row.get("refund_amount")),
            "客单价": aov,
            "广告花费": ad_spend,
            "广告销售额": ad_revenue,
            "广告订单": ad_orders,
            "广告ROI": ad_roi,
            "广告币种": ad_cur or None,
            "自然订单(估)": organic_orders,
            "自然销售额(估)": organic_sales,
            "健康分": _num(row.get("health_score")),
            "健康状态": row.get("health_status") or "",
            "延迟发货率": _num(row.get("late_dispatch_rate")),
            "负面反馈率": _num(row.get("negative_feedback_rate")),
            "结算金额": _num(row.get("settlement_amount")),
            "待结算": _num(row.get("pending_amount")),
            "财务退款": _num(row.get("finance_refund")),
            "财务币种": row.get("finance_currency") or "",
            "销售额环比": _num(row.get("sales_mom_ratio")),
            "广告花费环比": _num(row.get("ad_spend_mom_ratio")),
            "数据状态": row.get("row_status") or "success",
            "抓取时间": _feishu_date(row.get("collected_at")),
            "数据源": row.get("source_url") or "",
            "本地ID": str(row.get("id") or ""),
        }
    )


def tk_ads_campaign_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    """fact_ads_campaign_daily → 飞书 T2「广告活动日明细」。"""
    spend = _num(row.get("spend")) or 0.0
    revenue = _num(row.get("revenue")) or 0.0
    roi = _num(row.get("roi"))
    if roi is None and spend > 0:
        roi = revenue / spend
    budget = _num(row.get("daily_budget"))
    burn = None
    if budget is not None and budget > 0:
        burn = spend / budget
    plan_raw = str(row.get("plan_status") or "").strip().lower() or "unknown"
    plan_cn = _PLAN_STATUS_CN.get(plan_raw) or _PLAN_STATUS_CN.get(str(row.get("plan_status") or "").strip()) or "未知"
    target = _num(row.get("target_roi"))
    tag = _profit_tag(roi, spend, revenue, target)

    return _omit_none(
        {
            "日期": _feishu_date(row.get("biz_date")),
            "店铺": row.get("shop_name") or "",
            "店铺ID": row.get("shop_external_id") or "",
            "品名": row.get("campaign_name") or "",
            "广告花费": spend,
            "销量": _num(row.get("orders")),
            "ROI": roi,
            "销售额": revenue,
            "币种": row.get("currency") or "USD",
            "计划状态": plan_cn,
            "投放状态": row.get("delivery_status") or "",
            "日预算": budget,
            "目标ROI": target,
            "净成本": _num(row.get("net_cost")),
            "平均下单成本": _num(row.get("avg_order_cost")),
            "预算消耗率": burn,
            "盈亏标签": tag,
            "抓取时间": _feishu_date(row.get("collected_at")),
            "数据源URL": row.get("source_url") or "",
            "状态": row.get("row_status") or "success",
            "本地ID": str(row.get("id") or ""),
        }
    )


_TK_TASK_STATUS_CN = {
    "open": "未处理",
    "in_progress": "处理中",
    "resolved": "已闭环",
    "cancelled": "已取消",
    "ignored": "忽略",
}


# 旧码/简称 → 飞书「异常类型」单选（与建表选项对齐）
_TK_ANOMALY_TYPE_CN = {
    "stock_low": "商品库存不足",
    "库存不足": "商品库存不足",
    "stockout": "商品断货",
    "roi_low": "广告ROI过低",
    "ads_roi_low": "广告ROI过低",
    "ads_spend_no_sale": "广告空耗",
    "ads_budget_burn": "广告预算将尽",
    "ads_cpa_high": "广告CPA过高",
    "product_stockout": "商品断货",
    "product_stock_low": "商品库存不足",
    "shop_gmv_drop": "店铺GMV骤降",
    "shop_order_drop": "店铺订单骤降",
    "content_gmv_drop": "视频归因GMV骤降",
    "content_play_drop": "视频播放/曝光崩",
    "content_imp_no_order": "视频有曝无单",
    "视频归因GMV骤降": "视频归因GMV骤降",
    "视频播放/曝光崩": "视频播放/曝光崩",
    "视频有曝无单": "视频有曝无单",
}


_TK_OBJECT_TYPE_CN = {
    "product": "商品",
    "campaign": "广告",
    "shop": "店铺",
    "order": "订单",
    "content": "视频内容",
    "other": "其它",
}


def _tk_level_from_row(row: dict[str, Any]) -> str:
    """P0/P1/P2 或 level_code → 飞书「等级」red/orange/yellow。"""
    raw = str(row.get("level_code") or "").strip().lower()
    if raw in ("red", "orange", "yellow"):
        return raw
    pri = str(row.get("priority") or "P1").strip().upper()
    return {"P0": "red", "P1": "orange", "P2": "yellow"}.get(pri, "orange")


def tk_anomaly_task_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    """tk.fact_tk_anomaly_task → 飞书「异常任务」列名（对齐 AMZ ASIN健康度监控·异常任务）。"""
    st = row.get("status") or "open"
    # 商品 ID 列：飞书 AMZ 用 ASIN；TK 用同一列名兼容，或「商品ID」
    # content 域：object_ref / product_id 可能装 content_id
    product_id = row.get("product_id") or ""
    obj_type = str(row.get("object_type") or "product").strip() or "product"
    object_ref = row.get("object_ref") or product_id or ""
    if obj_type == "content" and not product_id and object_ref:
        product_id = str(object_ref)
    type_raw = (row.get("anomaly_type") or "").strip()
    code = (row.get("anomaly_code") or "").strip()
    type_cn = (
        _TK_ANOMALY_TYPE_CN.get(type_raw)
        or _TK_ANOMALY_TYPE_CN.get(code)
        or type_raw
        or "其它"
    )
    obj_type_cn = _TK_OBJECT_TYPE_CN.get(obj_type, obj_type)
    task_key = row.get("task_key") or ""
    st_cn = _TK_TASK_STATUS_CN.get(str(st), str(st))
    owner = row.get("owner_name") or ""
    metric = row.get("metric_snapshot") or ""
    summary = row.get("summary") or ""
    description = row.get("description") or ""
    if not description:
        parts = [p for p in (summary, row.get("progress_note"), metric) if p]
        description = " | ".join(dict.fromkeys(parts)) if parts else ""
    close_status = row.get("close_status") or (
        "已闭环" if str(st) in ("resolved", "closed") else st_cn
    )
    boss = row.get("needs_boss_decision")
    if boss is None:
        boss = str(row.get("priority") or "").upper() == "P0"
    # 产品列：过滤「订单号+星期时间」噪声，避免飞书展示错乱
    product_name = str(row.get("product_name") or "").strip()
    if obj_type == "content":
        # 内容域对象是视频，标题已在摘要/说明，产品列置空
        product_name = ""
    elif product_name and (
        "件商品" in product_name
        or re.search(r"星期[一二三四五六日天]", product_name)
        or re.match(r"^\d{14,22}(\s|$)", product_name)
        or re.match(r"^\d{14,22}.{0,12}\d{1,2}:\d{2}", product_name)
    ):
        product_name = ""
    product_name_cn = str(row.get("product_name_cn") or "").strip()
    return _omit_none(
        {
            # —— 与 AMZ 同名列（运营对照）——
            "主键": task_key,
            "异常编号": task_key,
            "日期": _feishu_date(row.get("biz_date")),
            "店铺": row.get("shop_name") or "",
            "ASIN": product_id,  # 兼容 AMZ 表头；值=TK product_id 或 content_id
            "产品": product_name,
            "中文名称": product_name_cn,
            "异常类型": type_cn,
            "等级": _tk_level_from_row(row),
            "指标摘要": metric or summary,
            "当前值": _num(row.get("current_value")),
            "当前值含义": row.get("current_value_label") or "",
            "对比值": _num(row.get("compare_value")),
            "对比值含义": row.get("compare_value_label") or "",
            "变化幅度": _num(row.get("change_magnitude")),
            "变化幅度含义": row.get("change_magnitude_label") or "",
            "负责人": owner,
            "第一负责人": owner,  # TK 历史列名，双写
            "审核人": row.get("reviewer_name") or "",
            "状态": st_cn,
            "截止时间": _feishu_date(row.get("due_at")),
            "连续异常次数": _num(row.get("streak_count") if row.get("streak_count") is not None else 1),
            "需要老板决策": bool(boss),
            "说明": description,
            "是否属实": row.get("is_confirmed") or "",
            "判断依据": row.get("judgment_basis") or "",
            "采取动作": row.get("action_taken") or "",
            "执行日期_系统": _feishu_date(row.get("executed_at")),
            "执行人": row.get("executor_name") or "",
            "动作前数据": row.get("data_before") or "",
            "动作后数据": row.get("data_after") or "",
            "是否有效": row.get("is_effective") or "",
            "需审核事项": row.get("review_items") or "",
            "复查日期": _feishu_date(row.get("review_date")),
            "下一步动作": row.get("next_action") or "",
            "闭环状态": close_status,
            # —— TK 扩展（系统/去重）——
            "店铺ID": row.get("shop_external_id") or "",
            "商品ID": product_id,
            "SKU": row.get("seller_sku") or "",
            "对象": object_ref or product_id or "",
            "对象类型": obj_type_cn,
            "异常码": code,
            "优先级": row.get("priority") or "P1",
            "摘要": summary,
            "指标快照": metric,
            "进度": row.get("progress_note") or "",
            "关联任务ID": str(row.get("center_task_id") or "") if row.get("center_task_id") else "",
            "去重键": row.get("dedupe_key") or "",
            "更新时间": _feishu_date(row.get("updated_at")),
            "抓取时间": _feishu_date(row.get("collected_at")),
            "本地ID": str(row.get("id") or ""),
        }
    )


def tk_content_daily_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    """fact_tiktok_content_daily → 飞书 T6「内容日」。

    语义：biz_date=窗口锚点；「窗口」来自 raw_extra.window（近7天等），禁止均摊成日行。
    """
    raw = row.get("raw_extra") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    window = (
        raw.get("window")
        or raw.get("date_window")
        or raw.get("dateRange")
        or row.get("window")
        or ""
    )
    published = (
        raw.get("published_at")
        or raw.get("publish_time")
        or raw.get("publishedAt")
        or row.get("published_at")
        or ""
    )
    channel = str(row.get("channel") or "short_video").strip() or "short_video"
    return _omit_none(
        {
            "日期": _feishu_date(row.get("biz_date")),
            "店铺": row.get("shop_name") or "",
            "店铺ID": row.get("shop_external_id") or "",
            "内容ID": row.get("content_id") or "",
            "视频标题": row.get("content_title") or "",
            "渠道": channel,
            "商品ID": row.get("product_id") or "",
            "归因GMV": _num(row.get("attributed_gmv")),
            "归因SKU订单": _num(row.get("attributed_sku_orders")),
            "归因成交件数": _num(row.get("attributed_units")),
            "播放量": _num(row.get("play_count")),
            "曝光": _num(row.get("impressions")),
            "点击": _num(row.get("clicks")),
            "CTR": _num(row.get("ctr")),
            "CVR": _num(row.get("cvr")),
            "客户数": _num(row.get("customers")),
            "币种": row.get("currency") or "",
            "窗口": str(window) if window is not None else "",
            "发布时间": str(published) if published is not None else "",
            "抓取时间": _feishu_date(row.get("collected_at")),
            "数据源URL": row.get("source_url") or "",
            "本地ID": str(row.get("id") or ""),
        }
    )


def tk_experience_daily_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    """fact_tiktok_experience_daily → 飞书「体验分日」表。"""
    metrics = row.get("metrics_json") or {}
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except Exception:  # noqa: BLE001
            metrics = {}
    metrics_txt = ""
    if isinstance(metrics, dict) and metrics:
        parts = [f"{k}={v}" for k, v in list(metrics.items())[:20]]
        metrics_txt = "; ".join(parts)
    return _omit_none(
        {
            "日期": _feishu_date(row.get("biz_date")),
            "店铺": row.get("shop_name") or "",
            "店铺ID": row.get("shop_external_id") or "",
            "体验总分": _num(row.get("experience_score")),
            "商品满意度": _num(row.get("product_satisfaction")),
            "履约物流": _num(row.get("fulfillment_score")),
            "客户服务": _num(row.get("customer_service_score")),
            "状态": row.get("status_label") or "",
            "子指标摘要": metrics_txt,
            "抓取时间": _feishu_date(row.get("collected_at")),
            "数据源URL": row.get("source_url") or "",
            "本地ID": str(row.get("id") or ""),
        }
    )


def tk_affiliate_creator_daily_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    """fact_tiktok_affiliate_creator_daily → 飞书 T7「达人日」。

    语义：biz_date=窗口锚点；window_label 如近7天；creator_id=handle；禁日均摊。
    投入仅预计佣金；投流/寄样金额不写 0。
    """
    window = (
        row.get("window_label")
        or row.get("window")
        or ""
    )
    sold = row.get("sold_flag")
    if sold is True:
        sold_label = "是"
    elif sold is False:
        sold_label = "否"
    else:
        sold_label = ""
    return _omit_none(
        {
            "日期": _feishu_date(row.get("biz_date")),
            "店铺": row.get("shop_name") or "",
            "店铺ID": row.get("shop_external_id") or "",
            "达人ID": row.get("creator_id") or "",
            "达人昵称": row.get("creator_name") or "",
            "达人Handle": row.get("creator_handle") or row.get("creator_id") or "",
            "窗口": str(window) if window is not None else "",
            "归因GMV": _num(row.get("gmv")),
            "成交件数": _num(row.get("order_units")),
            "归因订单数": _num(row.get("orders_cnt")),
            "退款金额": _num(row.get("refund_amount")),
            "退款件数": _num(row.get("refund_units")),
            "预计佣金": _num(row.get("est_commission")),
            "视频数": _num(row.get("video_cnt")),
            "直播数": _num(row.get("live_cnt")),
            "商品销量": _num(row.get("product_sold")),
            "已发货样品数": _num(row.get("samples_shipped")),
            "视频播放量": _num(row.get("video_views")),
            "CVR": _num(row.get("cvr")),
            "是否出单": sold_label,
            "币种": row.get("currency") or "",
            "抓取时间": _feishu_date(row.get("collected_at")),
            "数据源URL": row.get("source_url") or "",
            "本地ID": str(row.get("id") or ""),
        }
    )
