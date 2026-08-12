"""采集上报：幂等写入 ingest_raw，并按 source 分发到事实表。"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.infra.security import require_ingest_key

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


class Evidence(BaseModel):
    screenshot_url: str | None = None
    source_url: str | None = None
    raw_ref: str | None = None


class IngestEnvelope(BaseModel):
    platform: str | None = None
    shop_id: str | None = Field(default=None, description="外部店铺 ID")
    shop_name: str | None = None
    biz_date: date | None = None
    collected_at: datetime | None = None
    idempotency_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: Evidence | None = None


class IngestBatch(BaseModel):
    items: list[IngestEnvelope] = Field(min_length=1, max_length=500)


async def _resolve_shop_uuid(db: AsyncSession, platform: str | None, external_id: str | None) -> str | None:
    if not external_id:
        return None
    if platform:
        row = (
            await db.execute(
                text(
                    """
                    SELECT id::text FROM shop
                    WHERE external_shop_id = :eid AND platform = :platform
                    LIMIT 1
                    """
                ),
                {"eid": external_id, "platform": platform},
            )
        ).first()
        if row:
            return row[0]
    row = (
        await db.execute(
            text("SELECT id::text FROM shop WHERE external_shop_id = :eid LIMIT 1"),
            {"eid": external_id},
        )
    ).first()
    return row[0] if row else None


async def _process_tiktok_ads(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    p = env.payload
    campaign = str(p.get("campaign_name") or p.get("campaign") or "").strip()
    if not campaign or not env.biz_date or not env.shop_id:
        raise ValueError("tiktok_ads 需要 shop_id, biz_date, payload.campaign_name")

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_ads_campaign_daily (
                id, shop_id, shop_external_id, shop_name, biz_date, campaign_name,
                spend, orders, roi, revenue, currency, row_status, source_url,
                plan_status, delivery_status, daily_budget, target_roi, net_cost, avg_order_cost,
                collected_at, ingest_id, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date, :campaign_name,
                :spend, :orders, :roi, :revenue, :currency, :row_status, :source_url,
                :plan_status, :delivery_status, :daily_budget, :target_roi, :net_cost, :avg_order_cost,
                :collected_at, :ingest_id, now(), now()
            )
            ON CONFLICT (shop_external_id, campaign_name, biz_date) DO UPDATE SET
                spend = EXCLUDED.spend,
                orders = EXCLUDED.orders,
                roi = EXCLUDED.roi,
                revenue = EXCLUDED.revenue,
                currency = EXCLUDED.currency,
                row_status = EXCLUDED.row_status,
                source_url = EXCLUDED.source_url,
                plan_status = COALESCE(EXCLUDED.plan_status, tk.fact_ads_campaign_daily.plan_status),
                delivery_status = COALESCE(EXCLUDED.delivery_status, tk.fact_ads_campaign_daily.delivery_status),
                daily_budget = COALESCE(EXCLUDED.daily_budget, tk.fact_ads_campaign_daily.daily_budget),
                target_roi = COALESCE(EXCLUDED.target_roi, tk.fact_ads_campaign_daily.target_roi),
                net_cost = COALESCE(EXCLUDED.net_cost, tk.fact_ads_campaign_daily.net_cost),
                avg_order_cost = COALESCE(EXCLUDED.avg_order_cost, tk.fact_ads_campaign_daily.avg_order_cost),
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_ads_campaign_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_ads_campaign_daily.shop_name),
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "campaign_name": campaign,
            "spend": float(p.get("spend") or 0),
            "orders": float(p.get("orders") or 0),
            "roi": float(p["roi"]) if p.get("roi") is not None else None,
            "revenue": float(p.get("revenue") or 0),
            "currency": p.get("currency") or "GBP",
            "row_status": p.get("row_status") or "success",
            "source_url": (env.evidence.source_url if env.evidence else None) or p.get("source_url"),
            "plan_status": (str(p.get("plan_status") or p.get("planStatus") or "").strip() or None),
            "delivery_status": (
                str(p.get("delivery_status") or p.get("deliveryStatus") or "").strip() or None
            ),
            "daily_budget": _opt_float(p.get("daily_budget") if p.get("daily_budget") is not None else p.get("dailyBudget")),
            "target_roi": _opt_float(p.get("target_roi") if p.get("target_roi") is not None else p.get("targetRoi")),
            "net_cost": _opt_float(p.get("net_cost") if p.get("net_cost") is not None else p.get("netCost")),
            "avg_order_cost": _opt_float(
                p.get("avg_order_cost") if p.get("avg_order_cost") is not None else p.get("avgOrderCost")
            ),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


def _opt_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_metric_number(value: Any) -> float | None:
    """解析后台文案数字：£480.20 / 0.10% / 44.62K / 1.2万。"""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = str(value).strip()
    if not s or s in {"-", "—", "–"}:
        return None
    pct = re.match(r"^(-?[\d,]+(?:\.\d+)?)\s*%$", s)
    if pct:
        return _opt_float(pct.group(1).replace(",", ""))
    km = re.search(
        r"-?\s*[¥$€£￥]?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*([KkMm万亿])",
        s,
    )
    if km:
        base = _opt_float(km.group(1).replace(",", ""))
        if base is None:
            return None
        u = km.group(2)
        if u in {"K", "k"}:
            return base * 1000
        if u in {"M", "m"}:
            return base * 1_000_000
        if u == "万":
            return base * 10_000
        if u == "亿":
            return base * 100_000_000
        return base
    m = re.search(r"-?\s*[¥$€£￥]?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)", s)
    if m:
        return _opt_float(m.group(1).replace(",", ""))
    return None


def _enrich_traffic_from_raw_cells(
    *,
    impressions: float | None,
    clicks: float | None,
    ctr: float | None,
    orders_cnt: float | None,
    gmv: float | None,
    cvr: float | None,
    customers: float | None,
    raw_cells: Any,
    table_headers: Any = None,
) -> dict[str, float | None]:
    """
    商品卡表英文站表头（View-to-paid rate / Viewers）曾漏映射时，
    用 raw_cells（+ 可选 table_headers）回填 impressions/cvr/gmv。
    经典列序：名称 | GMV | CVR% | Viewers | Action
    """
    out: dict[str, float | None] = {
        "impressions": impressions,
        "clicks": clicks,
        "ctr": ctr,
        "orders_cnt": orders_cnt,
        "gmv": gmv,
        "cvr": cvr,
        "customers": customers,
    }
    cells: list[str] = []
    if isinstance(raw_cells, list):
        cells = [str(c).strip() for c in raw_cells if c is not None and str(c).strip()]
    if not cells:
        return out

    headers: list[str] = []
    if isinstance(table_headers, list):
        headers = [str(h).strip() for h in table_headers]

    def _hdr_field(h: str) -> str | None:
        t = h.lower()
        if not t or re.search(r"^action$|^操作$|^详情$|^details?$", t):
            return None
        if re.search(
            r"曝光\s*到\s*成交|曝光.*转化|\bcvr\b|转化率|conversion\s*rate|"
            r"view[\s\-]*to[\s\-]*paid|paid\s*rate",
            t,
            re.I,
        ):
            return "cvr"
        if re.search(
            r"曝光\s*用户|曝光数|impression|viewers?\b|unique\s*viewers?|product\s*views?\b",
            t,
            re.I,
        ) and not re.search(r"paid|转化|rate|ctr|cvr", t):
            return "impressions"
        if re.search(r"点击|clicks?", t) and not re.search(r"率|rate|ctr", t):
            return "clicks"
        if re.search(r"\bctr\b|点击率|click-?through", t):
            return "ctr"
        if re.search(r"订单|orders?|销量|units?", t):
            return "orders_cnt"
        if re.search(r"\bgmv\b|销售额|成交额|revenue", t):
            return "gmv"
        if re.search(r"日\s*客户|客户数|customers?", t):
            return "customers"
        return None

    if headers and len(headers) == len(cells):
        for h, cell in zip(headers, cells):
            field = _hdr_field(h)
            if not field or out.get(field) is not None:
                continue
            num = _parse_metric_number(cell)
            if num is not None:
                out[field] = num

    # 形态回填：货币→gmv，百分号→cvr，K/大数→impressions（排除商品 ID 超长纯数字）
    money = None
    pct = None
    big = None
    for cell in cells:
        if re.search(r"details?|详情|操作", cell, re.I):
            continue
        # 含 ID: 的长标题单元格不当指标
        if re.search(r"\bID:\s*\d{6,}", cell, re.I) and len(cell) > 24:
            continue
        if re.search(r"[£$€¥￥]", cell):
            n = _parse_metric_number(cell)
            if n is not None and money is None:
                money = n
            continue
        if re.search(r"%\s*$", cell) or re.match(r"^\d+(\.\d+)?\s*%$", cell):
            n = _parse_metric_number(cell)
            if n is not None and pct is None:
                pct = n
            continue
        # 优先带 K/M/万 的曝光；纯数字须在合理曝光区间（避免 18 位 product_id）
        if re.search(r"[KkMm万亿]", cell):
            n = _parse_metric_number(cell)
            if n is not None and (big is None or n > big):
                big = n
            continue
        if re.match(r"^\d[\d,]*(\.\d+)?$", cell):
            n = _parse_metric_number(cell)
            # 曝光合理上界：< 1e9；且 ≥100；排除 10 位以上像商品 ID 的整数
            digits = re.sub(r"[^\d]", "", cell)
            if (
                n is not None
                and 100 <= n < 1_000_000_000
                and len(digits) <= 9
                and (big is None or n > big)
            ):
                big = n
    if out["gmv"] is None and money is not None:
        out["gmv"] = money
    if out["cvr"] is None and pct is not None:
        out["cvr"] = pct
    if out["impressions"] is None and big is not None:
        out["impressions"] = big
    return out


async def _process_amz_link_daily(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """Amazon 链接日指标 → fact_amz_link_daily（只写事实，不建任务）。"""
    p = env.payload or {}
    asin = str(p.get("asin") or "").strip() or None
    seller_sku = str(p.get("seller_sku") or p.get("sku") or "").strip() or None
    if not env.biz_date or not env.shop_id:
        raise ValueError("amz_link_daily 需要 shop_id, biz_date")
    if not asin and not seller_sku:
        raise ValueError("amz_link_daily 需要 payload.asin 或 payload.seller_sku")

    known = {
        "asin",
        "seller_sku",
        "sku",
        "parent_asin",
        "title",
        "units",
        "sales_amount",
        "currency",
        "sessions",
        "conversion_rate",
        "fba_fulfillable",
        "source_url",
        "category",
        "ad_spend",
        "acos",
        "unit_net_profit",
        "days_of_supply",
        "refund_rate",
        "units_mom_ratio",
        "sales_mom_ratio",
        "problem_tags",
        "owner_name",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    tags = p.get("problem_tags")
    if isinstance(tags, (list, tuple)):
        tags_s = ",".join(str(x) for x in tags if x is not None and str(x).strip())
    else:
        tags_s = str(tags).strip() if tags is not None and str(tags).strip() else None

    await db.execute(
        text(
            """
            INSERT INTO fact_amz_link_daily (
                id, shop_id, shop_external_id, biz_date, asin, seller_sku, parent_asin,
                title, units, sales_amount, currency, sessions, conversion_rate,
                fba_fulfillable, category, ad_spend, acos, unit_net_profit, days_of_supply,
                refund_rate, units_mom_ratio, sales_mom_ratio, problem_tags, owner_name,
                raw_extra, ingest_id, collected_at, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :biz_date, :asin, :seller_sku, :parent_asin,
                :title, :units, :sales_amount, :currency, :sessions, :conversion_rate,
                :fba_fulfillable, :category, :ad_spend, :acos, :unit_net_profit, :days_of_supply,
                :refund_rate, :units_mom_ratio, :sales_mom_ratio, :problem_tags, :owner_name,
                CAST(:raw_extra AS jsonb), :ingest_id, :collected_at, now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date, biz_key) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, fact_amz_link_daily.shop_id),
                asin = COALESCE(EXCLUDED.asin, fact_amz_link_daily.asin),
                seller_sku = COALESCE(EXCLUDED.seller_sku, fact_amz_link_daily.seller_sku),
                parent_asin = COALESCE(EXCLUDED.parent_asin, fact_amz_link_daily.parent_asin),
                title = COALESCE(EXCLUDED.title, fact_amz_link_daily.title),
                units = EXCLUDED.units,
                sales_amount = EXCLUDED.sales_amount,
                currency = EXCLUDED.currency,
                sessions = COALESCE(EXCLUDED.sessions, fact_amz_link_daily.sessions),
                conversion_rate = COALESCE(EXCLUDED.conversion_rate, fact_amz_link_daily.conversion_rate),
                fba_fulfillable = COALESCE(EXCLUDED.fba_fulfillable, fact_amz_link_daily.fba_fulfillable),
                category = COALESCE(EXCLUDED.category, fact_amz_link_daily.category),
                ad_spend = COALESCE(EXCLUDED.ad_spend, fact_amz_link_daily.ad_spend),
                acos = COALESCE(EXCLUDED.acos, fact_amz_link_daily.acos),
                unit_net_profit = COALESCE(EXCLUDED.unit_net_profit, fact_amz_link_daily.unit_net_profit),
                days_of_supply = COALESCE(EXCLUDED.days_of_supply, fact_amz_link_daily.days_of_supply),
                refund_rate = COALESCE(EXCLUDED.refund_rate, fact_amz_link_daily.refund_rate),
                units_mom_ratio = COALESCE(EXCLUDED.units_mom_ratio, fact_amz_link_daily.units_mom_ratio),
                sales_mom_ratio = COALESCE(EXCLUDED.sales_mom_ratio, fact_amz_link_daily.sales_mom_ratio),
                problem_tags = COALESCE(EXCLUDED.problem_tags, fact_amz_link_daily.problem_tags),
                owner_name = COALESCE(EXCLUDED.owner_name, fact_amz_link_daily.owner_name),
                raw_extra = EXCLUDED.raw_extra,
                ingest_id = EXCLUDED.ingest_id,
                collected_at = EXCLUDED.collected_at,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "biz_date": env.biz_date,
            "asin": asin,
            "seller_sku": seller_sku,
            "parent_asin": str(p.get("parent_asin") or "").strip() or None,
            "title": str(p.get("title") or "").strip() or None,
            "units": float(p.get("units") or 0),
            "sales_amount": float(p.get("sales_amount") or 0),
            "currency": p.get("currency") or "GBP",
            "sessions": _opt_float(p.get("sessions")),
            "conversion_rate": _opt_float(p.get("conversion_rate")),
            "fba_fulfillable": _opt_float(p.get("fba_fulfillable")),
            "category": str(p.get("category") or "").strip() or None,
            "ad_spend": _opt_float(p.get("ad_spend")),
            "acos": _opt_float(p.get("acos")),
            "unit_net_profit": _opt_float(p.get("unit_net_profit")),
            "days_of_supply": _opt_float(p.get("days_of_supply")),
            "refund_rate": _opt_float(p.get("refund_rate")),
            "units_mom_ratio": _opt_float(p.get("units_mom_ratio")),
            "sales_mom_ratio": _opt_float(p.get("sales_mom_ratio")),
            "problem_tags": tags_s,
            "owner_name": str(p.get("owner_name") or "").strip() or None,
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "ingest_id": ingest_id,
            "collected_at": env.collected_at,
        },
    )


async def _process_amz_shop_daily(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """Amazon 店铺日经营 → fact_amz_shop_daily（飞书 T1 源）。"""
    p = env.payload or {}
    if not env.biz_date or not env.shop_id:
        raise ValueError("amz_shop_daily 需要 shop_id, biz_date")

    known = {
        "marketplace",
        "market",
        "currency",
        "sales_amount",
        "sales",
        "orders_cnt",
        "orders",
        "units",
        "sessions",
        "add_to_cart",
        "aov",
        "refund_units",
        "refund_rate",
        "gross_profit",
        "ad_spend",
        "ad_sales",
        "acos",
        "ad_contrib_margin",
        "net_profit",
        "net_margin",
        "roi",
        "organic_sales",
        "ad_orders",
        "organic_orders",
        "cogs",
        "fba_fees",
        "platform_fees",
        "sales_mom_ratio",
        "profit_mom_ratio",
        "sales_yoy_ratio",
        "row_status",
        "source_url",
        "sourceUrl",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    sales = _opt_float(p.get("sales_amount") if p.get("sales_amount") is not None else p.get("sales")) or 0.0
    orders = _opt_float(p.get("orders_cnt") if p.get("orders_cnt") is not None else p.get("orders")) or 0.0
    aov = _opt_float(p.get("aov"))
    if aov is None and orders:
        aov = sales / orders if orders else None

    await db.execute(
        text(
            """
            INSERT INTO fact_amz_shop_daily (
                id, shop_id, shop_external_id, shop_name, biz_date, marketplace, currency,
                sales_amount, orders_cnt, units, sessions, add_to_cart, aov,
                refund_units, refund_rate, gross_profit, ad_spend, ad_sales, acos,
                ad_contrib_margin, net_profit, net_margin, roi,
                organic_sales, ad_orders, organic_orders, cogs, fba_fees, platform_fees,
                sales_mom_ratio, profit_mom_ratio, sales_yoy_ratio, row_status, source_url,
                raw_extra, ingest_id, collected_at, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date, :marketplace, :currency,
                :sales_amount, :orders_cnt, :units, :sessions, :add_to_cart, :aov,
                :refund_units, :refund_rate, :gross_profit, :ad_spend, :ad_sales, :acos,
                :ad_contrib_margin, :net_profit, :net_margin, :roi,
                :organic_sales, :ad_orders, :organic_orders, :cogs, :fba_fees, :platform_fees,
                :sales_mom_ratio, :profit_mom_ratio, :sales_yoy_ratio, :row_status, :source_url,
                CAST(:raw_extra AS jsonb), :ingest_id, :collected_at, now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, fact_amz_shop_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, fact_amz_shop_daily.shop_name),
                marketplace = COALESCE(EXCLUDED.marketplace, fact_amz_shop_daily.marketplace),
                currency = EXCLUDED.currency,
                sales_amount = EXCLUDED.sales_amount,
                orders_cnt = EXCLUDED.orders_cnt,
                units = EXCLUDED.units,
                sessions = COALESCE(EXCLUDED.sessions, fact_amz_shop_daily.sessions),
                add_to_cart = COALESCE(EXCLUDED.add_to_cart, fact_amz_shop_daily.add_to_cart),
                aov = COALESCE(EXCLUDED.aov, fact_amz_shop_daily.aov),
                refund_units = COALESCE(EXCLUDED.refund_units, fact_amz_shop_daily.refund_units),
                refund_rate = COALESCE(EXCLUDED.refund_rate, fact_amz_shop_daily.refund_rate),
                gross_profit = COALESCE(EXCLUDED.gross_profit, fact_amz_shop_daily.gross_profit),
                ad_spend = EXCLUDED.ad_spend,
                ad_sales = EXCLUDED.ad_sales,
                acos = COALESCE(EXCLUDED.acos, fact_amz_shop_daily.acos),
                ad_contrib_margin = COALESCE(EXCLUDED.ad_contrib_margin, fact_amz_shop_daily.ad_contrib_margin),
                net_profit = COALESCE(EXCLUDED.net_profit, fact_amz_shop_daily.net_profit),
                net_margin = COALESCE(EXCLUDED.net_margin, fact_amz_shop_daily.net_margin),
                roi = COALESCE(EXCLUDED.roi, fact_amz_shop_daily.roi),
                organic_sales = COALESCE(EXCLUDED.organic_sales, fact_amz_shop_daily.organic_sales),
                ad_orders = COALESCE(EXCLUDED.ad_orders, fact_amz_shop_daily.ad_orders),
                organic_orders = COALESCE(EXCLUDED.organic_orders, fact_amz_shop_daily.organic_orders),
                cogs = COALESCE(EXCLUDED.cogs, fact_amz_shop_daily.cogs),
                fba_fees = COALESCE(EXCLUDED.fba_fees, fact_amz_shop_daily.fba_fees),
                platform_fees = COALESCE(EXCLUDED.platform_fees, fact_amz_shop_daily.platform_fees),
                sales_mom_ratio = COALESCE(EXCLUDED.sales_mom_ratio, fact_amz_shop_daily.sales_mom_ratio),
                profit_mom_ratio = COALESCE(EXCLUDED.profit_mom_ratio, fact_amz_shop_daily.profit_mom_ratio),
                sales_yoy_ratio = COALESCE(EXCLUDED.sales_yoy_ratio, fact_amz_shop_daily.sales_yoy_ratio),
                row_status = EXCLUDED.row_status,
                source_url = COALESCE(EXCLUDED.source_url, fact_amz_shop_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                ingest_id = EXCLUDED.ingest_id,
                collected_at = EXCLUDED.collected_at,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "marketplace": str(p.get("marketplace") or p.get("market") or "").strip() or None,
            "currency": p.get("currency") or "GBP",
            "sales_amount": sales,
            "orders_cnt": orders,
            "units": float(p.get("units") or 0),
            "sessions": _opt_float(p.get("sessions")),
            "add_to_cart": _opt_float(p.get("add_to_cart")),
            "aov": aov,
            "refund_units": _opt_float(p.get("refund_units")),
            "refund_rate": _opt_float(p.get("refund_rate")),
            "gross_profit": _opt_float(p.get("gross_profit")),
            "ad_spend": float(p.get("ad_spend") or 0),
            "ad_sales": float(p.get("ad_sales") or 0),
            "acos": _opt_float(p.get("acos")),
            "ad_contrib_margin": _opt_float(p.get("ad_contrib_margin")),
            "net_profit": _opt_float(p.get("net_profit")),
            "net_margin": _opt_float(p.get("net_margin")),
            "roi": _opt_float(p.get("roi")),
            "organic_sales": _opt_float(p.get("organic_sales")),
            "ad_orders": _opt_float(p.get("ad_orders")),
            "organic_orders": _opt_float(p.get("organic_orders")),
            "cogs": _opt_float(p.get("cogs")),
            "fba_fees": _opt_float(p.get("fba_fees")),
            "platform_fees": _opt_float(p.get("platform_fees")),
            "sales_mom_ratio": _opt_float(p.get("sales_mom_ratio")),
            "profit_mom_ratio": _opt_float(p.get("profit_mom_ratio")),
            "sales_yoy_ratio": _opt_float(p.get("sales_yoy_ratio")),
            "row_status": str(p.get("row_status") or "success").strip() or "success",
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "ingest_id": ingest_id,
            "collected_at": env.collected_at,
        },
    )


async def _process_amz_risk_alert(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """Amazon 风险告警 → fact_amz_risk_alert（飞书 T6 源）。"""
    p = env.payload or {}
    alert_key = str(p.get("alert_key") or p.get("dedupe_key") or env.idempotency_key or "").strip()
    risk_type = str(p.get("risk_type") or p.get("anomaly_type") or "").strip()
    if not alert_key:
        raise ValueError("amz_risk_alert 需要 payload.alert_key 或 idempotency_key")
    if not risk_type:
        raise ValueError("amz_risk_alert 需要 payload.risk_type")

    priority = str(p.get("priority") or "P1").strip().upper()
    if priority not in ("P0", "P1", "P2"):
        priority = "P1"
    status_raw = str(p.get("status") or "open").strip().lower()
    status_map = {
        "open": "open",
        "未处理": "open",
        "in_progress": "in_progress",
        "处理中": "in_progress",
        "resolved": "resolved",
        "已闭环": "resolved",
        "ignored": "ignored",
        "忽略": "ignored",
    }
    status = status_map.get(status_raw, "open")
    detected = env.biz_date
    if p.get("detected_on"):
        try:
            detected = date.fromisoformat(str(p.get("detected_on"))[:10])
        except ValueError:
            pass
    if detected is None:
        detected = date.today()

    known = {
        "alert_key",
        "dedupe_key",
        "detected_on",
        "object_ref",
        "object",
        "risk_type",
        "anomaly_type",
        "priority",
        "summary",
        "title",
        "metric_snapshot",
        "status",
        "owner_name",
        "task_id",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    task_id = str(p.get("task_id") or "").strip() or None

    await db.execute(
        text(
            """
            INSERT INTO fact_amz_risk_alert (
                id, alert_key, detected_on, shop_id, shop_external_id, shop_name,
                object_ref, risk_type, priority, summary, metric_snapshot, status,
                owner_name, task_id, raw_extra, ingest_id, collected_at, created_at, updated_at
            ) VALUES (
                :id, :alert_key, :detected_on, :shop_id, :shop_external_id, :shop_name,
                :object_ref, :risk_type, :priority, :summary, :metric_snapshot, :status,
                :owner_name, CAST(:task_id AS uuid), CAST(:raw_extra AS jsonb),
                :ingest_id, :collected_at, now(), now()
            )
            ON CONFLICT (alert_key) DO UPDATE SET
                detected_on = EXCLUDED.detected_on,
                shop_id = COALESCE(EXCLUDED.shop_id, fact_amz_risk_alert.shop_id),
                shop_external_id = COALESCE(EXCLUDED.shop_external_id, fact_amz_risk_alert.shop_external_id),
                shop_name = COALESCE(EXCLUDED.shop_name, fact_amz_risk_alert.shop_name),
                object_ref = COALESCE(EXCLUDED.object_ref, fact_amz_risk_alert.object_ref),
                risk_type = EXCLUDED.risk_type,
                priority = EXCLUDED.priority,
                summary = EXCLUDED.summary,
                metric_snapshot = COALESCE(EXCLUDED.metric_snapshot, fact_amz_risk_alert.metric_snapshot),
                status = EXCLUDED.status,
                owner_name = COALESCE(EXCLUDED.owner_name, fact_amz_risk_alert.owner_name),
                task_id = COALESCE(EXCLUDED.task_id, fact_amz_risk_alert.task_id),
                raw_extra = EXCLUDED.raw_extra,
                ingest_id = EXCLUDED.ingest_id,
                collected_at = EXCLUDED.collected_at,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "alert_key": alert_key,
            "detected_on": detected,
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "object_ref": str(p.get("object_ref") or p.get("object") or "").strip() or None,
            "risk_type": risk_type,
            "priority": priority,
            "summary": str(p.get("summary") or p.get("title") or risk_type).strip(),
            "metric_snapshot": str(p.get("metric_snapshot") or "").strip() or None,
            "status": status,
            "owner_name": str(p.get("owner_name") or "").strip() or None,
            "task_id": task_id,
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "ingest_id": ingest_id,
            "collected_at": env.collected_at,
        },
    )


# TK 专用异常类型（011）：中文名 / 旧别名 → code
# 权威字典：tk.dim_tk_anomaly_type；此处为 Ingest 快路径，避免每条查库
_TK_ANOMALY_CN_TO_CODE = {
    # —— 广告 ——
    "广告ROI过低": "ads_roi_low",
    "ROI过低": "ads_roi_low",
    "ROI异常": "ads_roi_low",
    "ACOS异常": "ads_roi_low",  # AMZ 口径别名，映射到 TK ROI
    "广告空耗": "ads_spend_no_sale",
    "广告低效": "ads_spend_no_sale",
    "广告预算将尽": "ads_budget_burn",
    "预算将尽": "ads_budget_burn",
    "广告下单成本高": "ads_cpa_high",
    "CPA过高": "ads_cpa_high",
    "广告计划异常": "ads_plan_anomaly",
    # —— 商品 ——
    "商品断货": "product_stockout",
    "断货": "product_stockout",
    "商品库存不足": "product_stock_low",
    "库存不足": "product_stock_low",
    "商品库存积压": "product_overstock",
    "库存过高": "product_overstock",
    "库存积压": "product_overstock",
    "商品销量骤降": "product_sales_drop",
    "销量骤降": "product_sales_drop",
    "商品持续零销": "product_zero_sales",
    "零销": "product_zero_sales",
    "持续零销": "product_zero_sales",
    "商品下架异常": "product_delist",
    "下架异常": "product_delist",
    "商品价格异常": "product_price_anomaly",
    "价格异常": "product_price_anomaly",
    # —— 店铺经营 ——
    "店铺GMV骤降": "shop_gmv_drop",
    "GMV骤降": "shop_gmv_drop",
    "店铺订单骤降": "shop_order_drop",
    "订单骤降": "shop_order_drop",
    "店铺退款异常": "shop_refund_spike",
    "退款异常": "shop_refund_spike",
    # —— 健康 ——
    "店铺健康分低": "shop_health_low",
    "健康分异常": "shop_health_low",
    "健康分低": "shop_health_low",
    "延迟发货率高": "shop_late_dispatch",
    "延迟发货": "shop_late_dispatch",
    "负面反馈率高": "shop_neg_feedback",
    "负面反馈": "shop_neg_feedback",
    "评价异常": "shop_neg_feedback",
    # —— 财务 ——
    "待结算积压": "finance_pending_high",
    "财务退款偏高": "finance_refund_high",
    # —— 兜底 ——
    "其它": "other",
    "其他": "other",
}
# code → 规范中文名（飞书选项）
_TK_ANOMALY_CODE_TO_CN = {
    "ads_roi_low": "广告ROI过低",
    "ads_spend_no_sale": "广告空耗",
    "ads_budget_burn": "广告预算将尽",
    "ads_cpa_high": "广告下单成本高",
    "ads_plan_anomaly": "广告计划异常",
    "product_stockout": "商品断货",
    "product_stock_low": "商品库存不足",
    "product_overstock": "商品库存积压",
    "product_sales_drop": "商品销量骤降",
    "product_zero_sales": "商品持续零销",
    "product_delist": "商品下架异常",
    "product_price_anomaly": "商品价格异常",
    "shop_gmv_drop": "店铺GMV骤降",
    "shop_order_drop": "店铺订单骤降",
    "shop_refund_spike": "店铺退款异常",
    "shop_health_low": "店铺健康分低",
    "shop_late_dispatch": "延迟发货率高",
    "shop_neg_feedback": "负面反馈率高",
    "finance_pending_high": "待结算积压",
    "finance_refund_high": "财务退款偏高",
    "other": "其它",
    # 旧码兼容（010 种子）
    "stock_low": "商品库存不足",
    "stock_high": "商品库存积压",
    "sales_drop": "商品销量骤降",
    "zero_sales": "商品持续零销",
    "roi_low": "广告ROI过低",
    "ads_waste": "广告空耗",
    "review_risk": "负面反馈率高",
    "health_risk": "店铺健康分低",
    "price_anomaly": "商品价格异常",
}
# 旧 code → 新 code（写入 fact 时规范化）
_TK_ANOMALY_CODE_ALIASES = {
    "stock_low": "product_stock_low",
    "stock_high": "product_overstock",
    "sales_drop": "product_sales_drop",
    "zero_sales": "product_zero_sales",
    "roi_low": "ads_roi_low",
    "ads_waste": "ads_spend_no_sale",
    "review_risk": "shop_neg_feedback",
    "health_risk": "shop_health_low",
    "price_anomaly": "product_price_anomaly",
}


def _tk_anomaly_status(raw: Any) -> str:
    s = str(raw or "open").strip().lower()
    return {
        "open": "open",
        "未处理": "open",
        "待处理": "open",
        "in_progress": "in_progress",
        "处理中": "in_progress",
        "resolved": "resolved",
        "已闭环": "resolved",
        "已完成": "resolved",
        "cancelled": "cancelled",
        "已取消": "cancelled",
        "ignored": "ignored",
        "忽略": "ignored",
    }.get(s, "open")


def _tk_make_task_key(*, biz_date: date, shop: str, obj: str, code: str) -> str:
    """生成飞书风格主键 TYYYYMMDD-xxxxxxxx。"""
    import hashlib

    raw = f"{biz_date.isoformat()}|{shop}|{obj}|{code}"
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"T{biz_date.strftime('%Y%m%d')}-{h}"


async def _process_tiktok_anomaly_task(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TK 异常任务 → tk.fact_tk_anomaly_task（对齐飞书 AMZ「异常任务」）。"""
    p = env.payload or {}

    # 异常类型：中文名或 code（011 TK 专用；旧码自动归一）
    type_raw = str(
        p.get("anomaly_type") or p.get("risk_type") or p.get("type") or p.get("异常类型") or ""
    ).strip()
    code_raw = str(p.get("anomaly_code") or p.get("code") or "").strip().lower()
    if code_raw:
        anomaly_code = _TK_ANOMALY_CODE_ALIASES.get(code_raw, code_raw)
        anomaly_type = (
            str(p.get("anomaly_type") or "").strip()
            or _TK_ANOMALY_CODE_TO_CN.get(anomaly_code)
            or anomaly_code
        )
    elif type_raw in _TK_ANOMALY_CN_TO_CODE:
        anomaly_code = _TK_ANOMALY_CN_TO_CODE[type_raw]
        anomaly_type = _TK_ANOMALY_CODE_TO_CN.get(anomaly_code, type_raw)
    elif type_raw:
        if re.match(r"^[a-z][a-z0-9_]+$", type_raw):
            anomaly_code = _TK_ANOMALY_CODE_ALIASES.get(type_raw, type_raw)
            anomaly_type = _TK_ANOMALY_CODE_TO_CN.get(anomaly_code, type_raw)
        else:
            anomaly_code = _TK_ANOMALY_CN_TO_CODE.get(type_raw, "other")
            anomaly_type = _TK_ANOMALY_CODE_TO_CN.get(anomaly_code, type_raw)
    else:
        raise ValueError("tiktok_anomaly_task 需要 payload.anomaly_type 或 anomaly_code")

    product_id = str(p.get("product_id") or p.get("asin") or p.get("productId") or "").strip() or None
    seller_sku = str(p.get("seller_sku") or p.get("sku") or p.get("sellerSku") or "").strip() or None
    product_name = str(p.get("product_name") or p.get("title") or p.get("产品") or "").strip() or None
    product_name_cn = (
        str(p.get("product_name_cn") or p.get("name_cn") or p.get("中文名称") or "").strip() or None
    )
    campaign_name = str(p.get("campaign_name") or p.get("品名") or p.get("广告系列") or "").strip() or None
    object_ref = (
        str(
            p.get("object_ref")
            or p.get("object")
            or product_id
            or seller_sku
            or campaign_name
            or ""
        ).strip()
        or None
    )
    object_type = str(p.get("object_type") or "").strip().lower()
    if object_type not in ("product", "campaign", "shop", "order", "other"):
        if anomaly_code.startswith("ads_"):
            object_type = "campaign"
        elif anomaly_code.startswith("shop_") or anomaly_code.startswith("finance_"):
            object_type = "shop"
        elif anomaly_code.startswith("product_"):
            object_type = "product"
        else:
            object_type = "product"
    # 活动级：无 object_ref 时用品名
    if object_type == "campaign" and not object_ref and campaign_name:
        object_ref = campaign_name

    biz_date = env.biz_date
    if p.get("biz_date") or p.get("日期") or p.get("detected_on"):
        try:
            biz_date = date.fromisoformat(
                str(p.get("biz_date") or p.get("日期") or p.get("detected_on"))[:10]
            )
        except ValueError:
            pass
    if biz_date is None:
        biz_date = date.today()

    shop_ext = env.shop_id or str(p.get("shop_external_id") or "").strip() or None
    shop_name = await _shop_display_name(db, shop_uuid, env.shop_name or p.get("shop_name") or p.get("店铺"))

    obj_for_key = object_ref or product_id or seller_sku or shop_ext or "unknown"
    task_key = str(p.get("task_key") or p.get("主键") or p.get("alert_key") or "").strip()
    if not task_key:
        task_key = _tk_make_task_key(
            biz_date=biz_date,
            shop=str(shop_ext or ""),
            obj=str(obj_for_key),
            code=anomaly_code,
        )

    dedupe_key = str(p.get("dedupe_key") or "").strip() or None
    if not dedupe_key:
        dedupe_key = f"tiktok:{obj_for_key}:{anomaly_code}"

    priority = str(p.get("priority") or "P1").strip().upper()
    if priority not in ("P0", "P1", "P2"):
        priority = "P1"
    status = _tk_anomaly_status(p.get("status") or p.get("状态"))

    summary = str(p.get("summary") or p.get("title") or p.get("摘要") or anomaly_type).strip()
    metric_snapshot = str(p.get("metric_snapshot") or p.get("指标快照") or "").strip() or None
    progress_note = str(p.get("progress_note") or p.get("进度") or "").strip() or None
    owner_name = str(p.get("owner_name") or p.get("第一负责人") or p.get("负责人") or "").strip() or None
    center_task_id = str(p.get("center_task_id") or p.get("task_id") or "").strip() or None
    anomaly_event_id = str(p.get("anomaly_event_id") or "").strip() or None

    due_at = None
    if p.get("due_at") or p.get("截止时间"):
        due_at = _parse_optional_dt(p.get("due_at") or p.get("截止时间"))

    known = {
        "task_key",
        "主键",
        "alert_key",
        "dedupe_key",
        "biz_date",
        "日期",
        "detected_on",
        "product_id",
        "asin",
        "productId",
        "seller_sku",
        "sku",
        "sellerSku",
        "product_name",
        "title",
        "产品",
        "product_name_cn",
        "name_cn",
        "中文名称",
        "object_ref",
        "object",
        "object_type",
        "anomaly_type",
        "anomaly_code",
        "risk_type",
        "type",
        "异常类型",
        "code",
        "priority",
        "status",
        "状态",
        "summary",
        "title",
        "摘要",
        "metric_snapshot",
        "指标快照",
        "progress_note",
        "进度",
        "owner_name",
        "第一负责人",
        "负责人",
        "center_task_id",
        "task_id",
        "anomaly_event_id",
        "due_at",
        "截止时间",
        "shop_external_id",
        "shop_name",
        "店铺",
        "source_url",
        "sourceUrl",
        "row_status",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    source_url = (
        (env.evidence.source_url if env.evidence else None)
        or p.get("source_url")
        or p.get("sourceUrl")
    )
    resolved_at = None
    if status in ("resolved", "cancelled", "ignored"):
        resolved_at = env.collected_at or datetime.utcnow()

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tk_anomaly_task (
                id, task_key, biz_date, shop_id, shop_external_id, shop_name,
                product_id, seller_sku, product_name, product_name_cn,
                object_ref, object_type, anomaly_type, anomaly_code,
                priority, status, owner_name, due_at, progress_note,
                summary, metric_snapshot, center_task_id, anomaly_event_id,
                dedupe_key, raw_extra, source_url, row_status,
                ingest_id, collected_at, created_at, updated_at, resolved_at
            ) VALUES (
                :id, :task_key, :biz_date, :shop_id, :shop_external_id, :shop_name,
                :product_id, :seller_sku, :product_name, :product_name_cn,
                :object_ref, :object_type, :anomaly_type, :anomaly_code,
                :priority, :status, :owner_name, :due_at, :progress_note,
                :summary, :metric_snapshot, CAST(:center_task_id AS uuid),
                CAST(:anomaly_event_id AS uuid),
                :dedupe_key, CAST(:raw_extra AS jsonb), :source_url, :row_status,
                :ingest_id, :collected_at, now(), now(), :resolved_at
            )
            ON CONFLICT (task_key) DO UPDATE SET
                biz_date = EXCLUDED.biz_date,
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tk_anomaly_task.shop_id),
                shop_external_id = COALESCE(EXCLUDED.shop_external_id, tk.fact_tk_anomaly_task.shop_external_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tk_anomaly_task.shop_name),
                product_id = COALESCE(EXCLUDED.product_id, tk.fact_tk_anomaly_task.product_id),
                seller_sku = COALESCE(EXCLUDED.seller_sku, tk.fact_tk_anomaly_task.seller_sku),
                product_name = COALESCE(EXCLUDED.product_name, tk.fact_tk_anomaly_task.product_name),
                product_name_cn = COALESCE(EXCLUDED.product_name_cn, tk.fact_tk_anomaly_task.product_name_cn),
                object_ref = COALESCE(EXCLUDED.object_ref, tk.fact_tk_anomaly_task.object_ref),
                object_type = EXCLUDED.object_type,
                anomaly_type = EXCLUDED.anomaly_type,
                anomaly_code = EXCLUDED.anomaly_code,
                priority = EXCLUDED.priority,
                status = EXCLUDED.status,
                owner_name = COALESCE(EXCLUDED.owner_name, tk.fact_tk_anomaly_task.owner_name),
                due_at = COALESCE(EXCLUDED.due_at, tk.fact_tk_anomaly_task.due_at),
                progress_note = COALESCE(EXCLUDED.progress_note, tk.fact_tk_anomaly_task.progress_note),
                summary = EXCLUDED.summary,
                metric_snapshot = COALESCE(EXCLUDED.metric_snapshot, tk.fact_tk_anomaly_task.metric_snapshot),
                center_task_id = COALESCE(EXCLUDED.center_task_id, tk.fact_tk_anomaly_task.center_task_id),
                anomaly_event_id = COALESCE(EXCLUDED.anomaly_event_id, tk.fact_tk_anomaly_task.anomaly_event_id),
                dedupe_key = COALESCE(EXCLUDED.dedupe_key, tk.fact_tk_anomaly_task.dedupe_key),
                raw_extra = EXCLUDED.raw_extra,
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tk_anomaly_task.source_url),
                row_status = EXCLUDED.row_status,
                ingest_id = EXCLUDED.ingest_id,
                collected_at = EXCLUDED.collected_at,
                resolved_at = COALESCE(EXCLUDED.resolved_at, tk.fact_tk_anomaly_task.resolved_at),
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "task_key": task_key,
            "biz_date": biz_date,
            "shop_id": shop_uuid,
            "shop_external_id": shop_ext,
            "shop_name": shop_name,
            "product_id": product_id,
            "seller_sku": seller_sku,
            "product_name": product_name,
            "product_name_cn": product_name_cn,
            "object_ref": object_ref,
            "object_type": object_type,
            "anomaly_type": anomaly_type,
            "anomaly_code": anomaly_code,
            "priority": priority,
            "status": status,
            "owner_name": owner_name,
            "due_at": due_at,
            "progress_note": progress_note,
            "summary": summary,
            "metric_snapshot": metric_snapshot,
            "center_task_id": center_task_id,
            "anomaly_event_id": anomaly_event_id,
            "dedupe_key": dedupe_key,
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "source_url": source_url,
            "row_status": str(p.get("row_status") or "success").strip() or "success",
            "ingest_id": ingest_id,
            "collected_at": env.collected_at,
            "resolved_at": resolved_at,
        },
    )


_WEEKDAY_CN = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}


def _parse_optional_dt(v: Any, *, ref: datetime | None = None) -> datetime | None:
    """解析订单时间。支持相对中文与「星期一 23:32」；ref 默认 now(UTC-naive 按字面)。"""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    if not s:
        return None

    # 送达截止类文案：直接拒绝（曾污染 biz_date 到未来）
    if re.search(r"截止|送达日期|delivery\s*by", s, re.I) and not re.search(
        r"分钟前|小时前|天前|今天|昨天|星期|周", s
    ):
        return None

    base = ref or datetime.utcnow()
    if base.tzinfo is not None:
        base = base.replace(tzinfo=None)

    # 先剥 TK 订单号（常与相对时间粘连：5769…724 + 28 分钟前）
    s2 = re.sub(r"57\d{16}", " ", s)  # 18 位 57…
    s2 = re.sub(r"\b\d{15,20}\b", " ", s2)
    s2 = re.sub(r"\s+", " ", s2).strip()

    # 相对：只取 1~4 位
    m = re.search(r"(\d{1,4})\s*分钟前", s2)
    if m:
        return base - timedelta(minutes=int(m.group(1)))
    m = re.search(r"(\d{1,4})\s*小时前", s2)
    if m:
        return base - timedelta(hours=int(m.group(1)))
    m = re.search(r"(\d{1,4})\s*天前", s2)
    if m:
        return base - timedelta(days=int(m.group(1)))


    # 今天/昨天 + 时分
    m = re.search(r"(今天|昨天)\s*(\d{1,2}):(\d{2})(?::(\d{2}))?", s2)
    if m:
        day = base.date() if m.group(1) == "今天" else (base.date() - timedelta(days=1))
        sec = int(m.group(4) or 0)
        return datetime(day.year, day.month, day.day, int(m.group(2)), int(m.group(3)), sec)

    # 星期X / 周X + 时分 → 不晚于 base 的最近该星期
    m = re.search(r"(?:星期|周)([一二三四五六日天])\s*(\d{1,2}):(\d{2})(?::(\d{2}))?", s2)
    if m:
        target_wd = _WEEKDAY_CN.get(m.group(1))
        if target_wd is not None:
            delta = (base.weekday() - target_wd) % 7
            day = base.date() - timedelta(days=delta)
            sec = int(m.group(4) or 0)
            return datetime(day.year, day.month, day.day, int(m.group(2)), int(m.group(3)), sec)

    # 常见：2026-07-29 12:30:00 / ISO / 斜杠
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(s2.replace("Z", "+0000"), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s2.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_biz_date(
    *,
    explicit: date | None,
    pay_time: datetime | None,
    create_time: datetime | None,
    collected_at: datetime | None,
) -> date | None:
    """推导业务日；丢弃明显未来日（多半是物流截止误解析）。"""
    candidates: list[date] = []
    if explicit is not None:
        candidates.append(explicit if not isinstance(explicit, datetime) else explicit.date())
    for dt in (pay_time, create_time):
        if dt is None:
            continue
        candidates.append(dt.date() if isinstance(dt, datetime) else dt)
    if not candidates:
        return None
    ref = collected_at or datetime.utcnow()
    ref_day = ref.date() if isinstance(ref, datetime) else ref
    # 允许时区误差：最多比采集日晚 1 天
    for d in candidates:
        if d <= ref_day + timedelta(days=1):
            return d
    return None


async def _shop_display_name(
    db: AsyncSession,
    shop_uuid: str | None,
    fallback: str | None,
    cache: dict[str, str | None] | None = None,
) -> str | None:
    """优先 public.shop.name，避免 storeNameMap 与主数据漂移（如 SHOP INOUT vs Gardena）。"""
    if shop_uuid and cache is not None and shop_uuid in cache:
        return cache[shop_uuid] if cache[shop_uuid] is not None else ((fallback or "").strip() or None)
    name: str | None = None
    if shop_uuid:
        row = (
            await db.execute(text("SELECT name FROM shop WHERE id = CAST(:id AS uuid) LIMIT 1"), {"id": shop_uuid})
        ).first()
        if row and row[0]:
            name = str(row[0])
    if cache is not None and shop_uuid:
        cache[shop_uuid] = name
    if name:
        return name
    return (fallback or "").strip() or None


async def _process_tiktok_orders(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 订单头 → fact_tiktok_order（P2a）。"""
    p = env.payload or {}
    order_id = str(p.get("order_id") or p.get("orderId") or "").strip()
    if not order_id or not env.shop_id:
        raise ValueError("tiktok_orders 需要 shop_id 与 payload.order_id")

    ref = env.collected_at
    pay_time = _parse_optional_dt(p.get("pay_time") or p.get("payTime"), ref=ref)
    create_time = _parse_optional_dt(
        p.get("create_time")
        or p.get("createTime")
        or p.get("create_time_raw")
        or p.get("createTimeRaw"),
        ref=ref,
    )
    biz_date = _safe_biz_date(
        explicit=env.biz_date,
        pay_time=pay_time,
        create_time=create_time,
        collected_at=ref,
    )
    shop_name = await _shop_display_name(db, shop_uuid, env.shop_name, cache={})

    known = {
        "order_id",
        "orderId",
        "order_status",
        "orderStatus",
        "pay_time",
        "payTime",
        "create_time",
        "createTime",
        "createTimeRaw",
        "create_time_raw",
        "product_name",
        "productName",
        "seller_sku",
        "sellerSku",
        "sku_id",
        "skuId",
        "quantity",
        "pay_amount",
        "payAmount",
        "currency",
        "shipping_status",
        "shippingStatus",
        "buyer_region",
        "buyerRegion",
        "source_url",
        "sourceUrl",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    if p.get("createTimeRaw") or p.get("create_time_raw"):
        extra["create_time_raw"] = p.get("createTimeRaw") or p.get("create_time_raw")
    if env.shop_name and shop_name and env.shop_name != shop_name:
        extra["scrape_shop_name"] = env.shop_name

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_order (
                id, shop_id, shop_external_id, shop_name, order_id, order_status,
                pay_time, create_time, biz_date, product_name, seller_sku, sku_id,
                quantity, pay_amount, currency, shipping_status, buyer_region,
                source_url, raw_extra, collected_at, ingest_id, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :order_id, :order_status,
                :pay_time, :create_time, :biz_date, :product_name, :seller_sku, :sku_id,
                :quantity, :pay_amount, :currency, :shipping_status, :buyer_region,
                :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id, now(), now()
            )
            ON CONFLICT (shop_external_id, order_id) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_order.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_order.shop_name),
                order_status = COALESCE(EXCLUDED.order_status, tk.fact_tiktok_order.order_status),
                pay_time = COALESCE(EXCLUDED.pay_time, tk.fact_tiktok_order.pay_time),
                create_time = CASE
                    WHEN EXCLUDED.create_time IS NOT NULL THEN EXCLUDED.create_time
                    ELSE tk.fact_tiktok_order.create_time
                END,
                biz_date = CASE
                    WHEN EXCLUDED.biz_date IS NOT NULL THEN EXCLUDED.biz_date
                    ELSE tk.fact_tiktok_order.biz_date
                END,
                product_name = COALESCE(EXCLUDED.product_name, tk.fact_tiktok_order.product_name),
                seller_sku = COALESCE(EXCLUDED.seller_sku, tk.fact_tiktok_order.seller_sku),
                sku_id = COALESCE(EXCLUDED.sku_id, tk.fact_tiktok_order.sku_id),
                quantity = EXCLUDED.quantity,
                pay_amount = EXCLUDED.pay_amount,
                currency = COALESCE(EXCLUDED.currency, tk.fact_tiktok_order.currency),
                shipping_status = COALESCE(EXCLUDED.shipping_status, tk.fact_tiktok_order.shipping_status),
                buyer_region = COALESCE(EXCLUDED.buyer_region, tk.fact_tiktok_order.buyer_region),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_order.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": shop_name,
            "order_id": order_id,
            "order_status": str(p.get("order_status") or p.get("orderStatus") or "").strip() or None,
            "pay_time": pay_time,
            "create_time": create_time,
            "biz_date": biz_date,
            "product_name": str(p.get("product_name") or p.get("productName") or "").strip() or None,
            "seller_sku": str(p.get("seller_sku") or p.get("sellerSku") or "").strip() or None,
            "sku_id": str(p.get("sku_id") or p.get("skuId") or "").strip() or None,
            "quantity": float(p.get("quantity") or 0),
            "pay_amount": float(p.get("pay_amount") if p.get("pay_amount") is not None else p.get("payAmount") or 0),
            "currency": p.get("currency") or "USD",
            "shipping_status": str(p.get("shipping_status") or p.get("shippingStatus") or "").strip() or None,
            "buyer_region": str(p.get("buyer_region") or p.get("buyerRegion") or "").strip() or None,
            "source_url": (env.evidence.source_url if env.evidence else None) or p.get("source_url") or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_order_lines(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 订单明细行 → fact_tiktok_order_line（SKU 粒度）。"""
    p = env.payload or {}
    order_id = str(p.get("order_id") or p.get("orderId") or "").strip()
    if not order_id or not env.shop_id:
        raise ValueError("tiktok_order_lines 需要 shop_id 与 payload.order_id")

    seller_sku = str(p.get("seller_sku") or p.get("sellerSku") or "").strip() or None
    sku_id = str(p.get("sku_id") or p.get("skuId") or "").strip() or None
    product_id = str(p.get("product_id") or p.get("productId") or "").strip() or None
    product_name = str(p.get("product_name") or p.get("productName") or "").strip() or None
    line_no_raw = p.get("line_no") if p.get("line_no") is not None else p.get("lineNo")
    try:
        line_no = int(line_no_raw) if line_no_raw is not None and str(line_no_raw).strip() != "" else 1
    except (TypeError, ValueError):
        line_no = 1
    if line_no <= 0:
        line_no = 1

    line_key = str(p.get("line_key") or p.get("lineKey") or "").strip()
    if not line_key:
        if sku_id:
            line_key = f"sid:{sku_id}"
        elif seller_sku:
            line_key = f"sku:{seller_sku}"
        elif product_id:
            line_key = f"pid:{product_id}:n{line_no}"
        else:
            line_key = f"n:{line_no}:{ (product_name or '')[:40] }"
    if not line_key:
        raise ValueError("tiktok_order_lines 需要 line_key 或 sku/seller_sku/product")

    biz_date = env.biz_date
    if not biz_date:
        # 允许从 payload 带业务日
        raw_bd = p.get("biz_date") or p.get("bizDate")
        if raw_bd:
            try:
                if isinstance(raw_bd, date) and not isinstance(raw_bd, datetime):
                    biz_date = raw_bd
                else:
                    biz_date = date.fromisoformat(str(raw_bd)[:10])
            except ValueError:
                biz_date = None
    if not biz_date:
        # 明细行常不带日期：从 payload 时间或订单头继承，避免 biz_date 全空
        ref = env.collected_at
        pay_time = _parse_optional_dt(p.get("pay_time") or p.get("payTime"), ref=ref)
        create_time = _parse_optional_dt(p.get("create_time") or p.get("createTime"), ref=ref)
        biz_date = _safe_biz_date(
            explicit=None,
            pay_time=pay_time,
            create_time=create_time,
            collected_at=ref,
        )
    if not biz_date:
        row = (
            await db.execute(
                text(
                    """
                    SELECT biz_date,
                           (pay_time AT TIME ZONE 'UTC')::date AS pay_d,
                           (create_time AT TIME ZONE 'UTC')::date AS create_d
                      FROM tk.fact_tiktok_order
                     WHERE shop_external_id = :shop_external_id
                       AND order_id = :order_id
                     LIMIT 1
                    """
                ),
                {"shop_external_id": env.shop_id, "order_id": order_id},
            )
        ).mappings().first()
        if row:
            for cand in (row.get("biz_date"), row.get("pay_d"), row.get("create_d")):
                if cand is None:
                    continue
                if isinstance(cand, datetime):
                    biz_date = cand.date()
                elif isinstance(cand, date):
                    biz_date = cand
                else:
                    try:
                        biz_date = date.fromisoformat(str(cand)[:10])
                    except ValueError:
                        biz_date = None
                if biz_date:
                    break

    shop_name = await _shop_display_name(db, shop_uuid, env.shop_name, cache={})

    known = {
        "order_id",
        "orderId",
        "line_no",
        "lineNo",
        "line_key",
        "lineKey",
        "product_id",
        "productId",
        "product_name",
        "productName",
        "seller_sku",
        "sellerSku",
        "sku_id",
        "skuId",
        "quantity",
        "pay_amount",
        "payAmount",
        "unit_price",
        "unitPrice",
        "currency",
        "biz_date",
        "bizDate",
        "source_url",
        "sourceUrl",
    }
    extra = {k: v for k, v in p.items() if k not in known}

    qty = float(p.get("quantity") or 0)
    pay_amount = _opt_float(p.get("pay_amount") if p.get("pay_amount") is not None else p.get("payAmount"))
    unit_price = _opt_float(p.get("unit_price") if p.get("unit_price") is not None else p.get("unitPrice"))

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_order_line (
                id, shop_id, shop_external_id, shop_name, order_id, line_no, line_key,
                product_id, product_name, seller_sku, sku_id, quantity, pay_amount, unit_price,
                currency, biz_date, source_url, raw_extra, collected_at, ingest_id,
                created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :order_id, :line_no, :line_key,
                :product_id, :product_name, :seller_sku, :sku_id, :quantity, :pay_amount, :unit_price,
                :currency, :biz_date, :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id,
                now(), now()
            )
            ON CONFLICT (shop_external_id, order_id, line_key) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_order_line.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_order_line.shop_name),
                line_no = EXCLUDED.line_no,
                product_id = COALESCE(EXCLUDED.product_id, tk.fact_tiktok_order_line.product_id),
                product_name = COALESCE(EXCLUDED.product_name, tk.fact_tiktok_order_line.product_name),
                seller_sku = COALESCE(EXCLUDED.seller_sku, tk.fact_tiktok_order_line.seller_sku),
                sku_id = COALESCE(EXCLUDED.sku_id, tk.fact_tiktok_order_line.sku_id),
                quantity = EXCLUDED.quantity,
                pay_amount = COALESCE(EXCLUDED.pay_amount, tk.fact_tiktok_order_line.pay_amount),
                unit_price = COALESCE(EXCLUDED.unit_price, tk.fact_tiktok_order_line.unit_price),
                currency = COALESCE(EXCLUDED.currency, tk.fact_tiktok_order_line.currency),
                biz_date = COALESCE(EXCLUDED.biz_date, tk.fact_tiktok_order_line.biz_date),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_order_line.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": shop_name,
            "order_id": order_id,
            "line_no": line_no,
            "line_key": line_key,
            "product_id": product_id,
            "product_name": product_name,
            "seller_sku": seller_sku,
            "sku_id": sku_id,
            "quantity": qty,
            "pay_amount": pay_amount,
            "unit_price": unit_price,
            "currency": p.get("currency") or "GBP",
            "biz_date": biz_date,
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )

    # 若订单头 seller_sku/sku_id 仍空，用首行明细回填（不覆盖已有值）
    if seller_sku or sku_id or product_name:
        await db.execute(
            text(
                """
                UPDATE tk.fact_tiktok_order
                SET
                    seller_sku = COALESCE(seller_sku, :seller_sku),
                    sku_id = COALESCE(sku_id, :sku_id),
                    product_name = CASE
                        WHEN product_name IS NULL OR product_name ~ '件商品'
                            THEN COALESCE(:product_name, product_name)
                        ELSE product_name
                    END,
                    updated_at = now()
                WHERE shop_external_id = :shop_external_id
                  AND order_id = :order_id
                """
            ),
            {
                "seller_sku": seller_sku,
                "sku_id": sku_id,
                "product_name": product_name,
                "shop_external_id": env.shop_id,
                "order_id": order_id,
            },
        )


_SKU_EXPAND_NOISE_RE = re.compile(
    r"(?i)(\d+\s*个\s*SKU|SKU\s*展开|展开全部|展开\s*SKU|expand\s+\d+\s*sku|批量操作)"
)


def _is_sku_expand_noise(*parts: str | None) -> bool:
    blob = " ".join(str(p or "") for p in parts)
    return bool(blob and _SKU_EXPAND_NOISE_RE.search(blob))


async def _process_tiktok_products(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 商品列表 → fact_tiktok_product（P2b）。"""
    p = env.payload or {}
    product_id = str(p.get("product_id") or p.get("productId") or "").strip()
    seller_sku = str(p.get("seller_sku") or p.get("sellerSku") or "").strip() or None
    product_name = str(p.get("product_name") or p.get("productName") or "").strip() or None
    seller_skus_raw = p.get("seller_skus") or p.get("sellerSkus") or []
    seller_skus: list[str] = []
    if isinstance(seller_skus_raw, str):
        seller_skus = [x.strip() for x in re.split(r"[|,;/]+", seller_skus_raw) if x and x.strip()]
    elif isinstance(seller_skus_raw, (list, tuple)):
        seller_skus = [str(x).strip() for x in seller_skus_raw if str(x).strip()]
    if seller_sku and "|" in seller_sku and not seller_skus:
        seller_skus = [x.strip() for x in seller_sku.split("|") if x.strip()]
    if not seller_sku and seller_skus:
        seller_sku = seller_skus[0] if len(seller_skus) == 1 else "|".join(seller_skus)

    # 拒收列表页「N 个 SKU 展开」UI 噪声
    if _is_sku_expand_noise(product_id, product_name, seller_sku):
        raise ValueError(f"tiktok_products 拒绝 SKU展开 噪声行: {product_id or product_name}")
    if product_id.startswith("name:") and re.search(r"(?i)SKU|展开|expand", product_id):
        raise ValueError(f"tiktok_products 拒绝 name: 噪声 product_id: {product_id}")

    if not product_id:
        if seller_sku and not _is_sku_expand_noise(seller_sku):
            product_id = f"sku:{seller_sku}"
        elif product_name and not _is_sku_expand_noise(product_name):
            product_id = f"name:{product_name[:80]}"
    if not product_id or not env.shop_id:
        raise ValueError("tiktok_products 需要 shop_id 与 product_id/seller_sku/product_name")

    known = {
        "product_id",
        "productId",
        "product_name",
        "productName",
        "seller_sku",
        "sellerSku",
        "seller_skus",
        "sellerSkus",
        "status",
        "stock_qty",
        "stockQty",
        "price",
        "sales_qty",
        "salesQty",
        "currency",
        "source_url",
        "sourceUrl",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    if seller_skus:
        extra["seller_skus"] = seller_skus

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_product (
                id, shop_id, shop_external_id, shop_name, product_id, product_name,
                seller_sku, status, stock_qty, price, currency, sales_qty,
                source_url, raw_extra, collected_at, ingest_id, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :product_id, :product_name,
                :seller_sku, :status, :stock_qty, :price, :currency, :sales_qty,
                :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id, now(), now()
            )
            ON CONFLICT (shop_external_id, product_id) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_product.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_product.shop_name),
                product_name = COALESCE(EXCLUDED.product_name, tk.fact_tiktok_product.product_name),
                seller_sku = COALESCE(EXCLUDED.seller_sku, tk.fact_tiktok_product.seller_sku),
                status = COALESCE(EXCLUDED.status, tk.fact_tiktok_product.status),
                stock_qty = COALESCE(EXCLUDED.stock_qty, tk.fact_tiktok_product.stock_qty),
                price = COALESCE(EXCLUDED.price, tk.fact_tiktok_product.price),
                currency = COALESCE(EXCLUDED.currency, tk.fact_tiktok_product.currency),
                sales_qty = COALESCE(EXCLUDED.sales_qty, tk.fact_tiktok_product.sales_qty),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_product.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "product_id": product_id,
            "product_name": product_name,
            "seller_sku": seller_sku,
            "status": str(p.get("status") or "").strip() or None,
            "stock_qty": _opt_float(p.get("stock_qty") if p.get("stock_qty") is not None else p.get("stockQty")),
            "price": _opt_float(p.get("price")),
            "currency": p.get("currency") or "GBP",
            "sales_qty": _opt_float(p.get("sales_qty") if p.get("sales_qty") is not None else p.get("salesQty")),
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_product_traffic(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 商品卡流量 → fact_tiktok_product_traffic_daily（P2.1a 窗口快照）。"""
    p = env.payload or {}
    product_id = str(p.get("product_id") or p.get("productId") or "").strip()
    product_name = (
        str(p.get("product_name") or p.get("productName") or p.get("title") or "").strip() or None
    )
    channel = str(p.get("channel") or p.get("channelDefault") or "product_card").strip() or "product_card"
    if not product_id or not env.shop_id or not env.biz_date:
        raise ValueError("tiktok_product_traffic 需要 shop_id, biz_date, product_id")

    known = {
        "product_id",
        "productId",
        "product_name",
        "productName",
        "title",
        "channel",
        "channelDefault",
        "impressions",
        "clicks",
        "ctr",
        "orders_cnt",
        "ordersCnt",
        "orders",
        "gmv",
        "cvr",
        "customers",
        "currency",
        "source_url",
        "sourceUrl",
        # 仍写入 raw_extra 供回填/排障（下面 extra 会再并入）
    }
    # raw_cells / table_headers / window / page_kpis 进 raw_extra
    extra = {k: v for k, v in p.items() if k not in known}

    metrics = _enrich_traffic_from_raw_cells(
        impressions=_opt_float(p.get("impressions")),
        clicks=_opt_float(p.get("clicks")),
        ctr=_opt_float(p.get("ctr")),
        orders_cnt=_opt_float(
            p.get("orders_cnt")
            if p.get("orders_cnt") is not None
            else p.get("ordersCnt")
            if p.get("ordersCnt") is not None
            else p.get("orders")
        ),
        gmv=_opt_float(p.get("gmv")),
        cvr=_opt_float(p.get("cvr")),
        customers=_opt_float(p.get("customers")),
        raw_cells=p.get("raw_cells") or p.get("rawCells") or extra.get("raw_cells"),
        table_headers=p.get("table_headers")
        or p.get("tableHeaders")
        or extra.get("table_headers"),
    )

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_product_traffic_daily (
                id, shop_id, shop_external_id, shop_name, biz_date,
                product_id, product_name, channel,
                impressions, clicks, ctr, orders_cnt, gmv, cvr, customers,
                currency, source_url, raw_extra, collected_at, ingest_id,
                created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date,
                :product_id, :product_name, :channel,
                :impressions, :clicks, :ctr, :orders_cnt, :gmv, :cvr, :customers,
                :currency, :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id,
                now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date, product_id, channel) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_product_traffic_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_product_traffic_daily.shop_name),
                product_name = COALESCE(EXCLUDED.product_name, tk.fact_tiktok_product_traffic_daily.product_name),
                impressions = COALESCE(EXCLUDED.impressions, tk.fact_tiktok_product_traffic_daily.impressions),
                clicks = COALESCE(EXCLUDED.clicks, tk.fact_tiktok_product_traffic_daily.clicks),
                ctr = COALESCE(EXCLUDED.ctr, tk.fact_tiktok_product_traffic_daily.ctr),
                orders_cnt = COALESCE(EXCLUDED.orders_cnt, tk.fact_tiktok_product_traffic_daily.orders_cnt),
                gmv = COALESCE(EXCLUDED.gmv, tk.fact_tiktok_product_traffic_daily.gmv),
                cvr = COALESCE(EXCLUDED.cvr, tk.fact_tiktok_product_traffic_daily.cvr),
                customers = COALESCE(EXCLUDED.customers, tk.fact_tiktok_product_traffic_daily.customers),
                currency = COALESCE(EXCLUDED.currency, tk.fact_tiktok_product_traffic_daily.currency),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_product_traffic_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "product_id": product_id,
            "product_name": product_name,
            "channel": channel,
            "impressions": metrics["impressions"],
            "clicks": metrics["clicks"],
            "ctr": metrics["ctr"],
            "orders_cnt": metrics["orders_cnt"],
            "gmv": metrics["gmv"],
            "cvr": metrics["cvr"],
            "customers": metrics["customers"],
            "currency": p.get("currency") or "GBP",
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_content(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 视频内容行 → fact_tiktok_content_daily（P2.1b 窗口快照）。"""
    p = env.payload or {}
    content_id = str(
        p.get("content_id")
        or p.get("contentId")
        or p.get("video_id")
        or p.get("videoId")
        or ""
    ).strip()
    content_title = (
        str(
            p.get("content_title")
            or p.get("contentTitle")
            or p.get("title")
            or p.get("video_title")
            or ""
        ).strip()
        or None
    )
    channel = str(p.get("channel") or p.get("channelDefault") or "short_video").strip() or "short_video"
    product_id = str(p.get("product_id") or p.get("productId") or "").strip() or None
    if not content_id or not env.shop_id or not env.biz_date:
        raise ValueError("tiktok_content 需要 shop_id, biz_date, content_id")

    known = {
        "content_id",
        "contentId",
        "video_id",
        "videoId",
        "content_title",
        "contentTitle",
        "title",
        "video_title",
        "channel",
        "channelDefault",
        "product_id",
        "productId",
        "attributed_gmv",
        "attributedGmv",
        "attributed_sku_orders",
        "attributedSkuOrders",
        "attributed_units",
        "attributedUnits",
        "play_count",
        "playCount",
        "impressions",
        "clicks",
        "ctr",
        "cvr",
        "customers",
        "currency",
        "source_url",
        "sourceUrl",
    }
    extra = {k: v for k, v in p.items() if k not in known}

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_content_daily (
                id, shop_id, shop_external_id, shop_name, biz_date,
                channel, content_id, content_title, product_id,
                attributed_gmv, attributed_sku_orders, attributed_units,
                play_count, impressions, clicks, ctr, cvr, customers,
                currency, source_url, raw_extra, collected_at, ingest_id,
                created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date,
                :channel, :content_id, :content_title, :product_id,
                :attributed_gmv, :attributed_sku_orders, :attributed_units,
                :play_count, :impressions, :clicks, :ctr, :cvr, :customers,
                :currency, :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id,
                now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date, channel, content_id) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_content_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_content_daily.shop_name),
                content_title = COALESCE(EXCLUDED.content_title, tk.fact_tiktok_content_daily.content_title),
                product_id = COALESCE(EXCLUDED.product_id, tk.fact_tiktok_content_daily.product_id),
                attributed_gmv = COALESCE(EXCLUDED.attributed_gmv, tk.fact_tiktok_content_daily.attributed_gmv),
                attributed_sku_orders = COALESCE(EXCLUDED.attributed_sku_orders, tk.fact_tiktok_content_daily.attributed_sku_orders),
                attributed_units = COALESCE(EXCLUDED.attributed_units, tk.fact_tiktok_content_daily.attributed_units),
                play_count = COALESCE(EXCLUDED.play_count, tk.fact_tiktok_content_daily.play_count),
                impressions = COALESCE(EXCLUDED.impressions, tk.fact_tiktok_content_daily.impressions),
                clicks = COALESCE(EXCLUDED.clicks, tk.fact_tiktok_content_daily.clicks),
                ctr = COALESCE(EXCLUDED.ctr, tk.fact_tiktok_content_daily.ctr),
                cvr = COALESCE(EXCLUDED.cvr, tk.fact_tiktok_content_daily.cvr),
                customers = COALESCE(EXCLUDED.customers, tk.fact_tiktok_content_daily.customers),
                currency = COALESCE(EXCLUDED.currency, tk.fact_tiktok_content_daily.currency),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_content_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "channel": channel,
            "content_id": content_id,
            "content_title": content_title,
            "product_id": product_id,
            "attributed_gmv": _opt_float(
                p.get("attributed_gmv")
                if p.get("attributed_gmv") is not None
                else p.get("attributedGmv")
            ),
            "attributed_sku_orders": _opt_float(
                p.get("attributed_sku_orders")
                if p.get("attributed_sku_orders") is not None
                else p.get("attributedSkuOrders")
            ),
            "attributed_units": _opt_float(
                p.get("attributed_units")
                if p.get("attributed_units") is not None
                else p.get("attributedUnits")
            ),
            "play_count": _opt_float(
                p.get("play_count") if p.get("play_count") is not None else p.get("playCount")
            ),
            "impressions": _opt_float(p.get("impressions")),
            "clicks": _opt_float(p.get("clicks")),
            "ctr": _opt_float(p.get("ctr")),
            "cvr": _opt_float(p.get("cvr")),
            "customers": _opt_float(p.get("customers")),
            "currency": p.get("currency") or "GBP",
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_shop_daily(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    p = env.payload or {}
    if not env.shop_id or not env.biz_date:
        raise ValueError("tiktok_shop_daily 需要 shop_id, biz_date")
    known = {
        "gmv",
        "orders_cnt",
        "ordersCnt",
        "buyers_cnt",
        "buyersCnt",
        "refund_amount",
        "refundAmount",
        "currency",
        "source_url",
        "sourceUrl",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_shop_daily (
                id, shop_id, shop_external_id, shop_name, biz_date,
                gmv, orders_cnt, buyers_cnt, refund_amount, currency,
                source_url, raw_extra, collected_at, ingest_id, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date,
                :gmv, :orders_cnt, :buyers_cnt, :refund_amount, :currency,
                :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id, now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_shop_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_shop_daily.shop_name),
                gmv = COALESCE(EXCLUDED.gmv, tk.fact_tiktok_shop_daily.gmv),
                orders_cnt = COALESCE(EXCLUDED.orders_cnt, tk.fact_tiktok_shop_daily.orders_cnt),
                buyers_cnt = COALESCE(EXCLUDED.buyers_cnt, tk.fact_tiktok_shop_daily.buyers_cnt),
                refund_amount = COALESCE(EXCLUDED.refund_amount, tk.fact_tiktok_shop_daily.refund_amount),
                currency = COALESCE(EXCLUDED.currency, tk.fact_tiktok_shop_daily.currency),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_shop_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "gmv": _opt_float(p.get("gmv")),
            "orders_cnt": _opt_float(p.get("orders_cnt") if p.get("orders_cnt") is not None else p.get("ordersCnt")),
            "buyers_cnt": _opt_float(p.get("buyers_cnt") if p.get("buyers_cnt") is not None else p.get("buyersCnt")),
            "refund_amount": _opt_float(
                p.get("refund_amount") if p.get("refund_amount") is not None else p.get("refundAmount")
            ),
            "currency": p.get("currency") or "GBP",
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_health_daily(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    p = env.payload or {}
    if not env.shop_id or not env.biz_date:
        raise ValueError("tiktok_health_daily 需要 shop_id, biz_date")
    known = {
        "health_score",
        "healthScore",
        "late_dispatch_rate",
        "lateDispatchRate",
        "negative_feedback_rate",
        "negativeFeedbackRate",
        "status_label",
        "statusLabel",
        "source_url",
        "sourceUrl",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_health_daily (
                id, shop_id, shop_external_id, shop_name, biz_date,
                health_score, late_dispatch_rate, negative_feedback_rate, status_label,
                source_url, raw_extra, collected_at, ingest_id, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date,
                :health_score, :late_dispatch_rate, :negative_feedback_rate, :status_label,
                :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id, now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_health_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_health_daily.shop_name),
                health_score = COALESCE(EXCLUDED.health_score, tk.fact_tiktok_health_daily.health_score),
                late_dispatch_rate = COALESCE(EXCLUDED.late_dispatch_rate, tk.fact_tiktok_health_daily.late_dispatch_rate),
                negative_feedback_rate = COALESCE(EXCLUDED.negative_feedback_rate, tk.fact_tiktok_health_daily.negative_feedback_rate),
                status_label = COALESCE(EXCLUDED.status_label, tk.fact_tiktok_health_daily.status_label),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_health_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "health_score": _opt_float(p.get("health_score") if p.get("health_score") is not None else p.get("healthScore")),
            "late_dispatch_rate": _opt_float(
                p.get("late_dispatch_rate") if p.get("late_dispatch_rate") is not None else p.get("lateDispatchRate")
            ),
            "negative_feedback_rate": _opt_float(
                p.get("negative_feedback_rate")
                if p.get("negative_feedback_rate") is not None
                else p.get("negativeFeedbackRate")
            ),
            "status_label": str(p.get("status_label") or p.get("statusLabel") or "").strip() or None,
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_experience_daily(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 店铺体验分日快照。"""
    p = env.payload or {}
    if not env.shop_id or not env.biz_date:
        raise ValueError("tiktok_experience_daily 需要 shop_id, biz_date")
    metrics = p.get("metrics_json") or p.get("metrics") or p.get("modules") or {}
    if not isinstance(metrics, dict):
        metrics = {"raw": metrics}
    known = {
        "experience_score",
        "experienceScore",
        "product_satisfaction",
        "productSatisfaction",
        "fulfillment_score",
        "fulfillmentScore",
        "customer_service_score",
        "customerServiceScore",
        "status_label",
        "statusLabel",
        "metrics_json",
        "metrics",
        "modules",
        "source_url",
        "sourceUrl",
        "scrape_raw",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    if p.get("scrape_raw") is not None:
        extra["scrape_raw"] = p.get("scrape_raw")
    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_experience_daily (
                id, shop_id, shop_external_id, shop_name, biz_date,
                experience_score, product_satisfaction, fulfillment_score, customer_service_score,
                status_label, metrics_json, source_url, raw_extra, collected_at, ingest_id,
                created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date,
                :experience_score, :product_satisfaction, :fulfillment_score, :customer_service_score,
                :status_label, CAST(:metrics_json AS jsonb), :source_url, CAST(:raw_extra AS jsonb),
                :collected_at, :ingest_id, now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_experience_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_experience_daily.shop_name),
                experience_score = COALESCE(EXCLUDED.experience_score, tk.fact_tiktok_experience_daily.experience_score),
                product_satisfaction = COALESCE(EXCLUDED.product_satisfaction, tk.fact_tiktok_experience_daily.product_satisfaction),
                fulfillment_score = COALESCE(EXCLUDED.fulfillment_score, tk.fact_tiktok_experience_daily.fulfillment_score),
                customer_service_score = COALESCE(EXCLUDED.customer_service_score, tk.fact_tiktok_experience_daily.customer_service_score),
                status_label = COALESCE(EXCLUDED.status_label, tk.fact_tiktok_experience_daily.status_label),
                metrics_json = EXCLUDED.metrics_json,
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_experience_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "experience_score": _opt_float(
                p.get("experience_score") if p.get("experience_score") is not None else p.get("experienceScore")
            ),
            "product_satisfaction": _opt_float(
                p.get("product_satisfaction")
                if p.get("product_satisfaction") is not None
                else p.get("productSatisfaction")
            ),
            "fulfillment_score": _opt_float(
                p.get("fulfillment_score") if p.get("fulfillment_score") is not None else p.get("fulfillmentScore")
            ),
            "customer_service_score": _opt_float(
                p.get("customer_service_score")
                if p.get("customer_service_score") is not None
                else p.get("customerServiceScore")
            ),
            "status_label": str(p.get("status_label") or p.get("statusLabel") or "").strip() or None,
            "metrics_json": json.dumps(metrics, ensure_ascii=False, default=str),
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_creator_health_daily(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 达人健康评分日快照。"""
    p = env.payload or {}
    if not env.shop_id or not env.biz_date:
        raise ValueError("tiktok_creator_health_daily 需要 shop_id, biz_date")
    ckey = str(p.get("creator_key") or p.get("creatorKey") or p.get("creator_id") or "").strip()
    if not ckey:
        raise ValueError("tiktok_creator_health_daily 需要 creator_key")
    known = {
        "creator_key",
        "creatorKey",
        "creator_id",
        "creator_name",
        "creatorName",
        "creator_role",
        "creatorRole",
        "health_score",
        "healthScore",
        "status_label",
        "statusLabel",
        "violation_count",
        "violationCount",
        "source_url",
        "sourceUrl",
        "scrape_raw",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    if p.get("scrape_raw") is not None:
        extra["scrape_raw"] = p.get("scrape_raw")
    vc = p.get("violation_count") if p.get("violation_count") is not None else p.get("violationCount")
    try:
        violation_count = int(vc) if vc is not None and str(vc).strip() != "" else None
    except (TypeError, ValueError):
        violation_count = None
    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_creator_health_daily (
                id, shop_id, shop_external_id, shop_name, creator_key, creator_name, creator_role,
                biz_date, health_score, status_label, violation_count, source_url, raw_extra,
                collected_at, ingest_id, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :creator_key, :creator_name, :creator_role,
                :biz_date, :health_score, :status_label, :violation_count, :source_url, CAST(:raw_extra AS jsonb),
                :collected_at, :ingest_id, now(), now()
            )
            ON CONFLICT (shop_external_id, creator_key, biz_date) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_creator_health_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_creator_health_daily.shop_name),
                creator_name = COALESCE(EXCLUDED.creator_name, tk.fact_tiktok_creator_health_daily.creator_name),
                creator_role = COALESCE(EXCLUDED.creator_role, tk.fact_tiktok_creator_health_daily.creator_role),
                health_score = COALESCE(EXCLUDED.health_score, tk.fact_tiktok_creator_health_daily.health_score),
                status_label = COALESCE(EXCLUDED.status_label, tk.fact_tiktok_creator_health_daily.status_label),
                violation_count = COALESCE(EXCLUDED.violation_count, tk.fact_tiktok_creator_health_daily.violation_count),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_creator_health_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "creator_key": ckey[:200],
            "creator_name": str(p.get("creator_name") or p.get("creatorName") or "").strip() or None,
            "creator_role": str(p.get("creator_role") or p.get("creatorRole") or "").strip() or None,
            "biz_date": env.biz_date,
            "health_score": _opt_float(
                p.get("health_score") if p.get("health_score") is not None else p.get("healthScore")
            ),
            "status_label": str(p.get("status_label") or p.get("statusLabel") or "").strip() or None,
            "violation_count": violation_count,
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_creator_violation(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 达人违规明细。"""
    p = env.payload or {}
    if not env.shop_id:
        raise ValueError("tiktok_creator_violation 需要 shop_id")
    ckey = str(p.get("creator_key") or p.get("creatorKey") or "").strip()
    vkey = str(p.get("violation_key") or p.get("violationKey") or "").strip()
    if not ckey:
        raise ValueError("tiktok_creator_violation 需要 creator_key")
    if not vkey:
        # fingerprint from type+reason+time
        import hashlib

        raw = "|".join(
            [
                str(p.get("violation_type") or p.get("type") or ""),
                str(p.get("reason") or ""),
                str(p.get("violation_at") or p.get("date") or ""),
                str(p.get("result_text") or p.get("result") or ""),
            ]
        )
        vkey = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:40]
    known = {
        "creator_key",
        "creatorKey",
        "creator_name",
        "creatorName",
        "violation_key",
        "violationKey",
        "violation_type",
        "type",
        "reason",
        "result_text",
        "result",
        "status",
        "violation_at",
        "date",
        "source_url",
        "sourceUrl",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_creator_violation (
                id, shop_id, shop_external_id, shop_name, creator_key, creator_name,
                violation_key, violation_type, reason, result_text, status, violation_at, biz_date,
                source_url, raw_extra, collected_at, ingest_id, first_seen_at, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :creator_key, :creator_name,
                :violation_key, :violation_type, :reason, :result_text, :status, :violation_at, :biz_date,
                :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id, now(), now(), now()
            )
            ON CONFLICT (shop_external_id, creator_key, violation_key) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_creator_violation.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_creator_violation.shop_name),
                creator_name = COALESCE(EXCLUDED.creator_name, tk.fact_tiktok_creator_violation.creator_name),
                violation_type = COALESCE(EXCLUDED.violation_type, tk.fact_tiktok_creator_violation.violation_type),
                reason = COALESCE(EXCLUDED.reason, tk.fact_tiktok_creator_violation.reason),
                result_text = COALESCE(EXCLUDED.result_text, tk.fact_tiktok_creator_violation.result_text),
                status = COALESCE(EXCLUDED.status, tk.fact_tiktok_creator_violation.status),
                violation_at = COALESCE(EXCLUDED.violation_at, tk.fact_tiktok_creator_violation.violation_at),
                biz_date = COALESCE(EXCLUDED.biz_date, tk.fact_tiktok_creator_violation.biz_date),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_creator_violation.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "creator_key": ckey[:200],
            "creator_name": str(p.get("creator_name") or p.get("creatorName") or "").strip() or None,
            "violation_key": vkey[:200],
            "violation_type": str(p.get("violation_type") or p.get("type") or "").strip() or None,
            "reason": str(p.get("reason") or "").strip() or None,
            "result_text": str(p.get("result_text") or p.get("result") or "").strip() or None,
            "status": str(p.get("status") or "").strip() or None,
            "violation_at": p.get("violation_at") or p.get("date"),
            "biz_date": env.biz_date,
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_violation(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 违规记录 → fact_tiktok_violation。"""
    p = env.payload or {}
    if not env.shop_id:
        raise ValueError("tiktok_violation 需要 shop_id")
    violation_key = str(
        p.get("violation_key") or p.get("violationKey") or p.get("id") or ""
    ).strip()
    penalty_text = str(p.get("penalty_text") or p.get("penaltyText") or "").strip() or None
    reason = str(p.get("reason") or "").strip() or None
    if not violation_key:
        # 内容指纹
        seed = "|".join(
            [
                penalty_text or "",
                reason or "",
                str(p.get("status") or ""),
                str(p.get("product_id") or p.get("productId") or ""),
                str(p.get("biz_date") or p.get("bizDate") or env.biz_date or ""),
            ]
        )
        if not seed.strip("|"):
            raise ValueError("tiktok_violation 需要 violation_key 或 penalty/reason")
        violation_key = f"h{abs(hash(seed)) % (10**12)}"

    biz_date = env.biz_date
    if not biz_date:
        raw_bd = p.get("biz_date") or p.get("bizDate")
        if raw_bd:
            try:
                biz_date = (
                    raw_bd
                    if isinstance(raw_bd, date) and not isinstance(raw_bd, datetime)
                    else date.fromisoformat(str(raw_bd)[:10])
                )
            except ValueError:
                biz_date = None
    violation_at = _parse_optional_dt(
        p.get("violation_at") or p.get("violationAt") or p.get("date"),
        ref=env.collected_at,
    )
    if not biz_date and violation_at:
        biz_date = violation_at.date() if isinstance(violation_at, datetime) else violation_at

    known = {
        "violation_key",
        "violationKey",
        "penalty_text",
        "penaltyText",
        "penalty_score",
        "penaltyScore",
        "reason",
        "status",
        "violation_at",
        "violationAt",
        "date",
        "biz_date",
        "bizDate",
        "product_id",
        "productId",
        "order_id",
        "orderId",
        "source_url",
        "sourceUrl",
        "raw_text",
        "rawText",
        "raw_cells",
        "rawCells",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    for k in ("raw_text", "rawText", "raw_cells", "rawCells"):
        if p.get(k) is not None:
            extra[k] = p.get(k)

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_violation (
                id, shop_id, shop_external_id, shop_name, violation_key,
                penalty_text, penalty_score, reason, status, violation_at, biz_date,
                product_id, order_id, source_url, raw_extra, collected_at, ingest_id,
                first_seen_at, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :violation_key,
                :penalty_text, :penalty_score, :reason, :status, :violation_at, :biz_date,
                :product_id, :order_id, :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id,
                now(), now(), now()
            )
            ON CONFLICT (shop_external_id, violation_key) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_violation.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_violation.shop_name),
                penalty_text = COALESCE(EXCLUDED.penalty_text, tk.fact_tiktok_violation.penalty_text),
                penalty_score = COALESCE(EXCLUDED.penalty_score, tk.fact_tiktok_violation.penalty_score),
                reason = COALESCE(EXCLUDED.reason, tk.fact_tiktok_violation.reason),
                status = COALESCE(EXCLUDED.status, tk.fact_tiktok_violation.status),
                violation_at = COALESCE(EXCLUDED.violation_at, tk.fact_tiktok_violation.violation_at),
                biz_date = COALESCE(EXCLUDED.biz_date, tk.fact_tiktok_violation.biz_date),
                product_id = COALESCE(EXCLUDED.product_id, tk.fact_tiktok_violation.product_id),
                order_id = COALESCE(EXCLUDED.order_id, tk.fact_tiktok_violation.order_id),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_violation.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "violation_key": violation_key[:200],
            "penalty_text": penalty_text,
            "penalty_score": _opt_float(
                p.get("penalty_score") if p.get("penalty_score") is not None else p.get("penaltyScore")
            ),
            "reason": reason,
            "status": str(p.get("status") or "").strip() or None,
            "violation_at": violation_at,
            "biz_date": biz_date,
            "product_id": str(p.get("product_id") or p.get("productId") or "").strip() or None,
            "order_id": str(p.get("order_id") or p.get("orderId") or "").strip() or None,
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_review(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 商品评分 → fact_tiktok_review。"""
    p = env.payload or {}
    if not env.shop_id:
        raise ValueError("tiktok_review 需要 shop_id")
    order_id = str(p.get("order_id") or p.get("orderId") or "").strip() or None
    product_id = str(p.get("product_id") or p.get("productId") or "").strip() or None
    review_key = str(p.get("review_key") or p.get("reviewKey") or "").strip()
    if not review_key:
        if order_id and product_id:
            review_key = f"{order_id}:{product_id}"
        elif order_id:
            review_key = f"o:{order_id}"
        elif product_id:
            seed = f"{product_id}|{p.get('review_text') or p.get('reviewText') or ''}|{p.get('biz_date') or ''}"
            review_key = f"p:{product_id}:{abs(hash(seed)) % (10**10)}"
        else:
            raise ValueError("tiktok_review 需要 review_key 或 order_id/product_id")

    rating = _opt_float(p.get("rating") if p.get("rating") is not None else p.get("stars"))
    review_at = _parse_optional_dt(
        p.get("review_at") or p.get("reviewAt") or p.get("date"),
        ref=env.collected_at,
    )
    reply_at = _parse_optional_dt(p.get("reply_at") or p.get("replyAt"), ref=env.collected_at)
    biz_date = env.biz_date
    if not biz_date:
        raw_bd = p.get("biz_date") or p.get("bizDate")
        if raw_bd:
            try:
                biz_date = (
                    raw_bd
                    if isinstance(raw_bd, date) and not isinstance(raw_bd, datetime)
                    else date.fromisoformat(str(raw_bd)[:10])
                )
            except ValueError:
                biz_date = None
    if not biz_date and review_at:
        biz_date = review_at.date() if isinstance(review_at, datetime) else review_at

    has_reply = p.get("has_reply") if p.get("has_reply") is not None else p.get("hasReply")
    if has_reply is None:
        has_reply = bool(str(p.get("reply_text") or p.get("replyText") or "").strip())
    else:
        has_reply = bool(has_reply)

    known = {
        "review_key",
        "reviewKey",
        "order_id",
        "orderId",
        "product_id",
        "productId",
        "product_name",
        "productName",
        "rating",
        "stars",
        "review_text",
        "reviewText",
        "review_at",
        "reviewAt",
        "date",
        "biz_date",
        "bizDate",
        "buyer_name",
        "buyerName",
        "reply_text",
        "replyText",
        "reply_at",
        "replyAt",
        "has_reply",
        "hasReply",
        "source_url",
        "sourceUrl",
        "raw_text",
        "rawText",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    if p.get("raw_text") is not None or p.get("rawText") is not None:
        extra["raw_text"] = p.get("raw_text") or p.get("rawText")

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_review (
                id, shop_id, shop_external_id, shop_name, review_key,
                order_id, product_id, product_name, rating, review_text,
                review_at, biz_date, buyer_name, reply_text, reply_at, has_reply,
                source_url, raw_extra, collected_at, ingest_id,
                first_seen_at, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :review_key,
                :order_id, :product_id, :product_name, :rating, :review_text,
                :review_at, :biz_date, :buyer_name, :reply_text, :reply_at, :has_reply,
                :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id,
                now(), now(), now()
            )
            ON CONFLICT (shop_external_id, review_key) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_review.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_review.shop_name),
                order_id = COALESCE(EXCLUDED.order_id, tk.fact_tiktok_review.order_id),
                product_id = COALESCE(EXCLUDED.product_id, tk.fact_tiktok_review.product_id),
                product_name = COALESCE(EXCLUDED.product_name, tk.fact_tiktok_review.product_name),
                rating = COALESCE(EXCLUDED.rating, tk.fact_tiktok_review.rating),
                review_text = COALESCE(EXCLUDED.review_text, tk.fact_tiktok_review.review_text),
                review_at = COALESCE(EXCLUDED.review_at, tk.fact_tiktok_review.review_at),
                biz_date = COALESCE(EXCLUDED.biz_date, tk.fact_tiktok_review.biz_date),
                buyer_name = COALESCE(EXCLUDED.buyer_name, tk.fact_tiktok_review.buyer_name),
                reply_text = COALESCE(EXCLUDED.reply_text, tk.fact_tiktok_review.reply_text),
                reply_at = COALESCE(EXCLUDED.reply_at, tk.fact_tiktok_review.reply_at),
                has_reply = EXCLUDED.has_reply OR tk.fact_tiktok_review.has_reply,
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_review.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "review_key": review_key[:200],
            "order_id": order_id,
            "product_id": product_id,
            "product_name": str(p.get("product_name") or p.get("productName") or "").strip() or None,
            "rating": rating,
            "review_text": str(p.get("review_text") or p.get("reviewText") or "").strip() or None,
            "review_at": review_at,
            "biz_date": biz_date,
            "buyer_name": str(p.get("buyer_name") or p.get("buyerName") or "").strip() or None,
            "reply_text": str(p.get("reply_text") or p.get("replyText") or "").strip() or None,
            "reply_at": reply_at,
            "has_reply": has_reply,
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_finance_daily(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    p = env.payload or {}
    if not env.shop_id or not env.biz_date:
        raise ValueError("tiktok_finance_daily 需要 shop_id, biz_date")
    known = {
        "settlement_amount",
        "settlementAmount",
        "pending_amount",
        "pendingAmount",
        "refund_amount",
        "refundAmount",
        "currency",
        "source_url",
        "sourceUrl",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_finance_daily (
                id, shop_id, shop_external_id, shop_name, biz_date,
                settlement_amount, pending_amount, refund_amount, currency,
                source_url, raw_extra, collected_at, ingest_id, created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date,
                :settlement_amount, :pending_amount, :refund_amount, :currency,
                :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id, now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_finance_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_finance_daily.shop_name),
                settlement_amount = COALESCE(EXCLUDED.settlement_amount, tk.fact_tiktok_finance_daily.settlement_amount),
                pending_amount = COALESCE(EXCLUDED.pending_amount, tk.fact_tiktok_finance_daily.pending_amount),
                refund_amount = COALESCE(EXCLUDED.refund_amount, tk.fact_tiktok_finance_daily.refund_amount),
                currency = COALESCE(EXCLUDED.currency, tk.fact_tiktok_finance_daily.currency),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_finance_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "settlement_amount": _opt_float(
                p.get("settlement_amount") if p.get("settlement_amount") is not None else p.get("settlementAmount")
            ),
            "pending_amount": _opt_float(
                p.get("pending_amount") if p.get("pending_amount") is not None else p.get("pendingAmount")
            ),
            "refund_amount": _opt_float(
                p.get("refund_amount") if p.get("refund_amount") is not None else p.get("refundAmount")
            ),
            "currency": p.get("currency") or "GBP",
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


def _normalize_window_label(raw: Any) -> str:
    """页面窗口文案 → 幂等键片段。默认近7天（联盟表现 POC 实证默认窗）。"""
    s = str(raw or "").strip()
    if not s:
        return "近7天"
    s2 = re.sub(r"\s+", "", s)
    m = re.search(r"近\s*(\d+)\s*天", s) or re.search(r"近(\d+)天", s2)
    if m:
        return f"近{m.group(1)}天"
    m2 = re.search(r"last\s*(\d+)\s*days?", s, flags=re.I)
    if m2:
        return f"近{m2.group(1)}天"
    if re.search(r"yesterday|昨天", s, flags=re.I):
        return "昨天"
    if re.search(r"today|今天", s, flags=re.I):
        return "今天"
    # 过长文案截断，避免 UNIQUE 键失控
    return s2[:32] if s2 else "近7天"


async def _process_tiktok_affiliate_daily(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 联盟表现·店级 → fact_tiktok_affiliate_daily（P3.1 窗口快照）。"""
    p = env.payload or {}
    if not env.shop_id or not env.biz_date:
        raise ValueError("tiktok_affiliate_daily 需要 shop_id, biz_date")

    raw_win = None
    if isinstance(p.get("raw"), dict):
        raw_win = p["raw"].get("window")
    window_label = _normalize_window_label(
        p.get("window_label") or p.get("windowLabel") or p.get("window") or raw_win
    )

    known = {
        "window_label",
        "windowLabel",
        "window",
        "gmv_affiliate",
        "gmvAffiliate",
        "order_units",
        "orderUnits",
        "refund_amount",
        "refundAmount",
        "video_cnt",
        "videoCnt",
        "live_cnt",
        "liveCnt",
        "creators_published",
        "creatorsPublished",
        "creators_sold",
        "creatorsSold",
        "est_commission",
        "estCommission",
        "currency",
        "source_url",
        "sourceUrl",
        "kpis",
        "raw",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    # 允许 kpis{} 嵌套（采集端整包上报时）
    kpis = p.get("kpis") if isinstance(p.get("kpis"), dict) else {}

    def _kpi(*keys: str) -> float | None:
        for k in keys:
            if p.get(k) is not None and p.get(k) != "":
                return _opt_float(p.get(k))
            if kpis.get(k) is not None and kpis.get(k) != "":
                return _opt_float(kpis.get(k))
        return None

    if isinstance(p.get("raw"), dict):
        extra.setdefault("raw", p.get("raw"))
    if window_label:
        extra.setdefault("window_label_raw", p.get("window") or p.get("window_label"))

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_affiliate_daily (
                id, shop_id, shop_external_id, shop_name, biz_date, window_label,
                gmv_affiliate, order_units, refund_amount, video_cnt, live_cnt,
                creators_published, creators_sold, est_commission,
                currency, source_url, raw_extra, collected_at, ingest_id,
                created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date, :window_label,
                :gmv_affiliate, :order_units, :refund_amount, :video_cnt, :live_cnt,
                :creators_published, :creators_sold, :est_commission,
                :currency, :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id,
                now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date, window_label) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_affiliate_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_affiliate_daily.shop_name),
                gmv_affiliate = COALESCE(EXCLUDED.gmv_affiliate, tk.fact_tiktok_affiliate_daily.gmv_affiliate),
                order_units = COALESCE(EXCLUDED.order_units, tk.fact_tiktok_affiliate_daily.order_units),
                refund_amount = COALESCE(EXCLUDED.refund_amount, tk.fact_tiktok_affiliate_daily.refund_amount),
                video_cnt = COALESCE(EXCLUDED.video_cnt, tk.fact_tiktok_affiliate_daily.video_cnt),
                live_cnt = COALESCE(EXCLUDED.live_cnt, tk.fact_tiktok_affiliate_daily.live_cnt),
                creators_published = COALESCE(EXCLUDED.creators_published, tk.fact_tiktok_affiliate_daily.creators_published),
                creators_sold = COALESCE(EXCLUDED.creators_sold, tk.fact_tiktok_affiliate_daily.creators_sold),
                est_commission = COALESCE(EXCLUDED.est_commission, tk.fact_tiktok_affiliate_daily.est_commission),
                currency = COALESCE(EXCLUDED.currency, tk.fact_tiktok_affiliate_daily.currency),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_affiliate_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "window_label": window_label,
            "gmv_affiliate": _kpi("gmv_affiliate", "gmvAffiliate"),
            "order_units": _kpi("order_units", "orderUnits"),
            "refund_amount": _kpi("refund_amount", "refundAmount"),
            "video_cnt": _kpi("video_cnt", "videoCnt"),
            "live_cnt": _kpi("live_cnt", "liveCnt"),
            "creators_published": _kpi("creators_published", "creatorsPublished"),
            "creators_sold": _kpi("creators_sold", "creatorsSold"),
            "est_commission": _kpi("est_commission", "estCommission"),
            "currency": p.get("currency") or kpis.get("currency") or "GBP",
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl")
            or p.get("url"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


async def _process_tiktok_affiliate_creator(
    db: AsyncSession,
    *,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    """TikTok 联盟表现·达人行 → fact_tiktok_affiliate_creator_daily（P3.1）。"""
    p = env.payload or {}
    creator_id = str(
        p.get("creator_id")
        or p.get("creatorId")
        or p.get("creator_handle")
        or p.get("creatorHandle")
        or p.get("handle")
        or ""
    ).strip()
    if not creator_id or not env.shop_id or not env.biz_date:
        raise ValueError("tiktok_affiliate_creator 需要 shop_id, biz_date, creator_id(handle)")

    window_label = _normalize_window_label(
        p.get("window_label") or p.get("windowLabel") or p.get("window")
    )
    creator_name = (
        str(
            p.get("creator_name")
            or p.get("creatorName")
            or p.get("name")
            or ""
        ).strip()
        or None
    )
    creator_handle = (
        str(p.get("creator_handle") or p.get("creatorHandle") or p.get("handle") or "").strip()
        or creator_id
    )

    gmv = _opt_float(p.get("gmv") if p.get("gmv") is not None else p.get("gmvAffiliate"))
    order_units = _opt_float(
        p.get("order_units") if p.get("order_units") is not None else p.get("orderUnits")
    )
    sold_flag = None
    if p.get("sold_flag") is not None or p.get("soldFlag") is not None:
        sf = p.get("sold_flag") if p.get("sold_flag") is not None else p.get("soldFlag")
        if isinstance(sf, bool):
            sold_flag = sf
        elif str(sf).strip().lower() in ("1", "true", "yes", "y"):
            sold_flag = True
        elif str(sf).strip().lower() in ("0", "false", "no", "n"):
            sold_flag = False
    if sold_flag is None:
        sold_flag = bool((gmv is not None and gmv > 0) or (order_units is not None and order_units > 0))

    known = {
        "creator_id",
        "creatorId",
        "creator_name",
        "creatorName",
        "creator_handle",
        "creatorHandle",
        "handle",
        "name",
        "window_label",
        "windowLabel",
        "window",
        "gmv",
        "gmvAffiliate",
        "order_units",
        "orderUnits",
        "orders",
        "orders_cnt",
        "ordersCnt",
        "refund_amount",
        "refundAmount",
        "refund_units",
        "refundUnits",
        "est_commission",
        "estCommission",
        "video_cnt",
        "videoCnt",
        "live_cnt",
        "liveCnt",
        "product_sold",
        "productSold",
        "samples_shipped",
        "samplesShipped",
        "video_views",
        "videoViews",
        "cvr",
        "sold_flag",
        "soldFlag",
        "currency",
        "source_url",
        "sourceUrl",
        "raw_cells",
        "rawCells",
        "creator_cell_raw",
        "creatorCellRaw",
    }
    extra = {k: v for k, v in p.items() if k not in known}
    if p.get("raw_cells") is not None:
        extra["raw_cells"] = p.get("raw_cells")
    elif p.get("rawCells") is not None:
        extra["raw_cells"] = p.get("rawCells")
    if p.get("creator_cell_raw") or p.get("creatorCellRaw"):
        extra["creator_cell_raw"] = p.get("creator_cell_raw") or p.get("creatorCellRaw")

    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tiktok_affiliate_creator_daily (
                id, shop_id, shop_external_id, shop_name, biz_date, window_label,
                creator_id, creator_name, creator_handle,
                gmv, order_units, orders_cnt, refund_amount, refund_units, est_commission,
                video_cnt, live_cnt, product_sold, samples_shipped, video_views, cvr,
                sold_flag, currency, source_url, raw_extra, collected_at, ingest_id,
                created_at, updated_at
            ) VALUES (
                :id, :shop_id, :shop_external_id, :shop_name, :biz_date, :window_label,
                :creator_id, :creator_name, :creator_handle,
                :gmv, :order_units, :orders_cnt, :refund_amount, :refund_units, :est_commission,
                :video_cnt, :live_cnt, :product_sold, :samples_shipped, :video_views, :cvr,
                :sold_flag, :currency, :source_url, CAST(:raw_extra AS jsonb), :collected_at, :ingest_id,
                now(), now()
            )
            ON CONFLICT (shop_external_id, biz_date, window_label, creator_id) DO UPDATE SET
                shop_id = COALESCE(EXCLUDED.shop_id, tk.fact_tiktok_affiliate_creator_daily.shop_id),
                shop_name = COALESCE(EXCLUDED.shop_name, tk.fact_tiktok_affiliate_creator_daily.shop_name),
                creator_name = COALESCE(EXCLUDED.creator_name, tk.fact_tiktok_affiliate_creator_daily.creator_name),
                creator_handle = COALESCE(EXCLUDED.creator_handle, tk.fact_tiktok_affiliate_creator_daily.creator_handle),
                gmv = COALESCE(EXCLUDED.gmv, tk.fact_tiktok_affiliate_creator_daily.gmv),
                order_units = COALESCE(EXCLUDED.order_units, tk.fact_tiktok_affiliate_creator_daily.order_units),
                orders_cnt = COALESCE(EXCLUDED.orders_cnt, tk.fact_tiktok_affiliate_creator_daily.orders_cnt),
                refund_amount = COALESCE(EXCLUDED.refund_amount, tk.fact_tiktok_affiliate_creator_daily.refund_amount),
                refund_units = COALESCE(EXCLUDED.refund_units, tk.fact_tiktok_affiliate_creator_daily.refund_units),
                est_commission = COALESCE(EXCLUDED.est_commission, tk.fact_tiktok_affiliate_creator_daily.est_commission),
                video_cnt = COALESCE(EXCLUDED.video_cnt, tk.fact_tiktok_affiliate_creator_daily.video_cnt),
                live_cnt = COALESCE(EXCLUDED.live_cnt, tk.fact_tiktok_affiliate_creator_daily.live_cnt),
                product_sold = COALESCE(EXCLUDED.product_sold, tk.fact_tiktok_affiliate_creator_daily.product_sold),
                samples_shipped = COALESCE(EXCLUDED.samples_shipped, tk.fact_tiktok_affiliate_creator_daily.samples_shipped),
                video_views = COALESCE(EXCLUDED.video_views, tk.fact_tiktok_affiliate_creator_daily.video_views),
                cvr = COALESCE(EXCLUDED.cvr, tk.fact_tiktok_affiliate_creator_daily.cvr),
                sold_flag = COALESCE(EXCLUDED.sold_flag, tk.fact_tiktok_affiliate_creator_daily.sold_flag),
                currency = COALESCE(EXCLUDED.currency, tk.fact_tiktok_affiliate_creator_daily.currency),
                source_url = COALESCE(EXCLUDED.source_url, tk.fact_tiktok_affiliate_creator_daily.source_url),
                raw_extra = EXCLUDED.raw_extra,
                collected_at = EXCLUDED.collected_at,
                ingest_id = EXCLUDED.ingest_id,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "shop_id": shop_uuid,
            "shop_external_id": env.shop_id,
            "shop_name": await _shop_display_name(db, shop_uuid, env.shop_name),
            "biz_date": env.biz_date,
            "window_label": window_label,
            "creator_id": creator_id,
            "creator_name": creator_name,
            "creator_handle": creator_handle,
            "gmv": gmv,
            "order_units": order_units,
            "orders_cnt": _opt_float(
                p.get("orders_cnt")
                if p.get("orders_cnt") is not None
                else p.get("ordersCnt")
                if p.get("ordersCnt") is not None
                else p.get("orders")
            ),
            "refund_amount": _opt_float(
                p.get("refund_amount") if p.get("refund_amount") is not None else p.get("refundAmount")
            ),
            "refund_units": _opt_float(
                p.get("refund_units") if p.get("refund_units") is not None else p.get("refundUnits")
            ),
            "est_commission": _opt_float(
                p.get("est_commission") if p.get("est_commission") is not None else p.get("estCommission")
            ),
            "video_cnt": _opt_float(
                p.get("video_cnt") if p.get("video_cnt") is not None else p.get("videoCnt")
            ),
            "live_cnt": _opt_float(
                p.get("live_cnt") if p.get("live_cnt") is not None else p.get("liveCnt")
            ),
            "product_sold": _opt_float(
                p.get("product_sold") if p.get("product_sold") is not None else p.get("productSold")
            ),
            "samples_shipped": _opt_float(
                p.get("samples_shipped")
                if p.get("samples_shipped") is not None
                else p.get("samplesShipped")
            ),
            "video_views": _opt_float(
                p.get("video_views") if p.get("video_views") is not None else p.get("videoViews")
            ),
            "cvr": _opt_float(p.get("cvr")),
            "sold_flag": sold_flag,
            "currency": p.get("currency") or "GBP",
            "source_url": (env.evidence.source_url if env.evidence else None)
            or p.get("source_url")
            or p.get("sourceUrl")
            or p.get("href")
            or p.get("url"),
            "raw_extra": json.dumps(extra, ensure_ascii=False, default=str),
            "collected_at": env.collected_at,
            "ingest_id": ingest_id,
        },
    )


def _default_platform(source: str, env_platform: str | None) -> str | None:
    if env_platform:
        return env_platform
    if source.startswith("tiktok") or source.startswith("tk_"):
        return "tiktok"
    if source in (
        "amz_link_daily",
        "sellfox_link_daily",
        "amazon_link_daily",
        "amz_shop_daily",
        "sellfox_shop_daily",
        "amazon_shop_daily",
        "amz_risk_alert",
        "amazon_risk_alert",
    ):
        return "amazon"
    if source.startswith("temu"):
        return "temu"
    return None


async def _ingest_one(
    db: AsyncSession,
    source: str,
    env: IngestEnvelope,
) -> dict[str, Any]:
    platform = _default_platform(source, env.platform)
    shop_uuid = await _resolve_shop_uuid(db, platform, env.shop_id)
    ingest_id = str(uuid4())
    evidence = (env.evidence.model_dump() if env.evidence else {}) or {}

    try:
        await db.execute(
            text(
                """
                INSERT INTO ingest_raw (
                    id, source, platform, shop_external_id, shop_id, biz_date,
                    idempotency_key, payload, evidence, collected_at, process_status
                ) VALUES (
                    :id, :source, :platform, :shop_external_id, :shop_id, :biz_date,
                    :idempotency_key, CAST(:payload AS jsonb), CAST(:evidence AS jsonb),
                    :collected_at, 'accepted'
                )
                """
            ),
            {
                "id": ingest_id,
                "source": source,
                "platform": platform,
                "shop_external_id": env.shop_id,
                "shop_id": shop_uuid,
                "biz_date": env.biz_date,
                "idempotency_key": env.idempotency_key,
                "payload": json.dumps(env.payload, ensure_ascii=False, default=str),
                "evidence": json.dumps(evidence, ensure_ascii=False),
                "collected_at": env.collected_at,
            },
        )
    except IntegrityError:
        await db.rollback()
        existing = (
            await db.execute(
                text("SELECT id::text FROM ingest_raw WHERE idempotency_key = :k"),
                {"k": env.idempotency_key},
            )
        ).first()
        existing_id = existing[0] if existing else None
        # 事实表可刷新：重复幂等键仍 UPSERT（修正 biz_date/店名/价格等），状态仍报 duplicated
        refreshable = {
            "tiktok_ads",
            "tiktok_orders",
            "tiktok_products",
            "tiktok_product_traffic",
            "tiktok_content",
            "tiktok_affiliate_daily",
            "tiktok_affiliate_shop",
            "tiktok_affiliate_creator",
            "tiktok_affiliate_creators",
            "tiktok_affiliate",
            "tiktok_shop_daily",
            "tiktok_health_daily",
            "tiktok_finance_daily",
            "tiktok_experience_daily",
            "tiktok_creator_health_daily",
            "tiktok_creator_violation",
            "tiktok_creator_violations",
            "tiktok_violation",
            "tiktok_violations",
            "tiktok_review",
            "tiktok_reviews",
            "tiktok_product_reviews",
            "tiktok_anomaly_task",
            "tk_anomaly_task",
            "amz_link_daily",
            "sellfox_link_daily",
            "amazon_link_daily",
            "amz_shop_daily",
            "sellfox_shop_daily",
            "amazon_shop_daily",
            "amz_risk_alert",
            "amazon_risk_alert",
        }
        if source in refreshable and existing_id:
            try:
                await _dispatch_fact(db, source, existing_id, env, shop_uuid)
                await db.commit()
            except Exception as exc:
                await db.rollback()
                return {
                    "idempotency_key": env.idempotency_key,
                    "id": existing_id,
                    "status": "failed",
                    "error": f"refresh: {exc}",
                }
        return {
            "idempotency_key": env.idempotency_key,
            "id": existing_id,
            "status": "duplicated",
            "error": None,
        }

    try:
        await _dispatch_fact(db, source, ingest_id, env, shop_uuid)
        # 其它 source 仅保留原始
        await db.execute(
            text("UPDATE ingest_raw SET process_status = 'processed' WHERE id = :id"),
            {"id": ingest_id},
        )
        await db.commit()
        return {
            "idempotency_key": env.idempotency_key,
            "id": ingest_id,
            "status": "created",
            "error": None,
        }
    except Exception as exc:
        await db.rollback()
        # 重新标记失败：原事务已回滚，补写失败状态可能丢 id，简化返回 failed
        return {
            "idempotency_key": env.idempotency_key,
            "id": ingest_id,
            "status": "failed",
            "error": str(exc),
        }


async def _dispatch_fact(
    db: AsyncSession,
    source: str,
    ingest_id: str,
    env: IngestEnvelope,
    shop_uuid: str | None,
) -> None:
    if source == "tiktok_ads":
        await _process_tiktok_ads(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source == "tiktok_orders":
        await _process_tiktok_orders(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("tiktok_order_lines", "tiktok_order_line", "tiktok_orders_lines"):
        await _process_tiktok_order_lines(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source == "tiktok_products":
        await _process_tiktok_products(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source == "tiktok_product_traffic":
        await _process_tiktok_product_traffic(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source == "tiktok_content":
        await _process_tiktok_content(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("tiktok_affiliate_daily", "tiktok_affiliate_shop"):
        await _process_tiktok_affiliate_daily(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("tiktok_affiliate_creator", "tiktok_affiliate_creators", "tiktok_affiliate"):
        # tiktok_affiliate 兼容：有 creator_id 走达人行，否则当店级
        p0 = env.payload or {}
        has_creator = bool(
            str(
                p0.get("creator_id")
                or p0.get("creatorId")
                or p0.get("creator_handle")
                or p0.get("creatorHandle")
                or ""
            ).strip()
        )
        if source == "tiktok_affiliate" and not has_creator:
            await _process_tiktok_affiliate_daily(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
        else:
            await _process_tiktok_affiliate_creator(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source == "tiktok_shop_daily":
        await _process_tiktok_shop_daily(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source == "tiktok_health_daily":
        await _process_tiktok_health_daily(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source == "tiktok_finance_daily":
        await _process_tiktok_finance_daily(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source == "tiktok_experience_daily":
        await _process_tiktok_experience_daily(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source == "tiktok_creator_health_daily":
        await _process_tiktok_creator_health_daily(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("tiktok_creator_violation", "tiktok_creator_violations"):
        await _process_tiktok_creator_violation(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("tiktok_violation", "tiktok_violations"):
        await _process_tiktok_violation(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("tiktok_review", "tiktok_reviews", "tiktok_product_reviews"):
        await _process_tiktok_review(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("amz_link_daily", "sellfox_link_daily", "amazon_link_daily"):
        await _process_amz_link_daily(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("amz_shop_daily", "sellfox_shop_daily", "amazon_shop_daily"):
        await _process_amz_shop_daily(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("amz_risk_alert", "amazon_risk_alert"):
        await _process_amz_risk_alert(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)
    elif source in ("tiktok_anomaly_task", "tk_anomaly_task", "tiktok_risk_alert"):
        await _process_tiktok_anomaly_task(db, ingest_id=ingest_id, env=env, shop_uuid=shop_uuid)


async def _maybe_auto_eval_after_ingest(
    db: AsyncSession,
    source: str,
    items: list[IngestEnvelope],
    results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """批末自动跑规则：广告 ROI/空耗、商品库存。失败不回滚已入库事实。"""
    from app.config import get_settings

    settings = get_settings()
    ok_n = sum(1 for r in results if r.get("status") in ("created", "duplicated"))
    if ok_n <= 0:
        return None

    # 从本批提取业务日 / 店铺（多值时取第一个非空；规则内可再扫全日）
    biz_dates = [e.biz_date for e in items if e.biz_date]
    shops = [e.shop_id for e in items if e.shop_id]
    biz_date = biz_dates[0] if biz_dates else None
    shop_ext = shops[0] if len(set(shops)) == 1 else None
    project = bool(settings.tk_rules_project_center_task)

    try:
        if source == "tiktok_ads" and settings.tk_ads_auto_eval_on_ingest:
            from app.domain.tk_ads_rules import evaluate_ads_anomalies

            return {
                "kind": "ads",
                **(
                    await evaluate_ads_anomalies(
                        db,
                        biz_date=biz_date,
                        shop_external_id=shop_ext,
                        project_center_task=project,
                        dry_run=False,
                        settings=settings,
                    )
                ),
            }
        if source == "tiktok_products" and settings.tk_product_auto_eval_on_ingest:
            from app.domain.tk_product_rules import evaluate_product_anomalies

            return {
                "kind": "products",
                **(
                    await evaluate_product_anomalies(
                        db,
                        shop_external_id=shop_ext,
                        project_center_task=project,
                        dry_run=False,
                        settings=settings,
                        biz_date=biz_date,
                    )
                ),
            }
        if source == "tiktok_content" and settings.tk_content_auto_eval_on_ingest:
            from app.domain.tk_content_rules import evaluate_content_anomalies

            return {
                "kind": "content",
                **(
                    await evaluate_content_anomalies(
                        db,
                        biz_date=biz_date,
                        shop_external_id=shop_ext,
                        project_center_task=project,
                        dry_run=False,
                        settings=settings,
                    )
                ),
            }
        if (
            source
            in (
                "tiktok_affiliate_daily",
                "tiktok_affiliate_shop",
                "tiktok_affiliate_creator",
                "tiktok_affiliate_creators",
                "tiktok_affiliate",
            )
            and settings.tk_affiliate_auto_eval_on_ingest
        ):
            from app.domain.tk_affiliate_rules import evaluate_affiliate_anomalies

            return {
                "kind": "affiliate",
                **(
                    await evaluate_affiliate_anomalies(
                        db,
                        biz_date=biz_date,
                        shop_external_id=shop_ext,
                        project_center_task=project,
                        dry_run=False,
                        settings=settings,
                    )
                ),
            }
        if source == "tiktok_health_daily" and settings.tk_health_auto_eval_on_ingest:
            from app.domain.tk_health_rules import evaluate_health_anomalies

            return {
                "kind": "health",
                **(
                    await evaluate_health_anomalies(
                        db,
                        biz_date=biz_date,
                        shop_external_id=shop_ext,
                        project_center_task=project,
                        dry_run=False,
                        notify=bool(settings.tk_health_notify_feishu),
                        settings=settings,
                    )
                ),
            }
        if source == "tiktok_experience_daily" and settings.tk_experience_auto_eval_on_ingest:
            from app.domain.tk_experience_rules import evaluate_experience_anomalies

            return {
                "kind": "experience",
                **(
                    await evaluate_experience_anomalies(
                        db,
                        biz_date=biz_date,
                        shop_external_id=shop_ext,
                        project_center_task=project,
                        dry_run=False,
                        notify=bool(settings.tk_health_notify_feishu),
                        settings=settings,
                    )
                ),
            }
        if (
            source
            in (
                "tiktok_creator_health_daily",
                "tiktok_creator_violation",
                "tiktok_creator_violations",
            )
            and settings.tk_creator_health_auto_eval_on_ingest
        ):
            from app.domain.tk_creator_health_rules import evaluate_creator_health_anomalies

            return {
                "kind": "creator_health",
                **(
                    await evaluate_creator_health_anomalies(
                        db,
                        biz_date=biz_date,
                        shop_external_id=shop_ext,
                        project_center_task=project,
                        dry_run=False,
                        notify=bool(settings.tk_health_notify_feishu),
                        settings=settings,
                    )
                ),
            }
        if source in ("tiktok_violation", "tiktok_violations") and settings.tk_violation_auto_eval_on_ingest:
            from app.domain.tk_violation_rules import evaluate_violation_anomalies

            return {
                "kind": "violation",
                **(
                    await evaluate_violation_anomalies(
                        db,
                        shop_external_id=shop_ext,
                        project_center_task=project,
                        dry_run=False,
                        notify=bool(settings.tk_health_notify_feishu),
                        settings=settings,
                    )
                ),
            }
        if (
            source in ("tiktok_review", "tiktok_reviews", "tiktok_product_reviews")
            and settings.tk_review_auto_eval_on_ingest
        ):
            from app.domain.tk_review_rules import evaluate_review_anomalies

            return {
                "kind": "review",
                **(
                    await evaluate_review_anomalies(
                        db,
                        shop_external_id=shop_ext,
                        project_center_task=project,
                        dry_run=False,
                        notify=bool(settings.tk_health_notify_feishu),
                        settings=settings,
                    )
                ),
            }
    except Exception as exc:  # noqa: BLE001 — 规则失败不影响 ingest 主结果
        return {"kind": source, "error": str(exc)}
    return None


@router.post("/{source}")
async def ingest(
    source: str,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_ingest_key),
) -> dict[str, Any]:
    if "items" in body:
        batch = IngestBatch.model_validate(body)
        items = batch.items
    else:
        items = [IngestEnvelope.model_validate(body)]

    results = []
    for env in items:
        results.append(await _ingest_one(db, source, env))

    out: dict[str, Any] = {
        "accepted": sum(1 for r in results if r["status"] == "created"),
        "duplicated": sum(1 for r in results if r["status"] == "duplicated"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }
    auto = await _maybe_auto_eval_after_ingest(db, source, items, results)
    if auto is not None:
        out["auto_anomaly_eval"] = auto
    return out
