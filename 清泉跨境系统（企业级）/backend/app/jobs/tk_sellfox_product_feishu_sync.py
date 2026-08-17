"""赛狐 PG → 飞书 TK产品表 同步（只读 PG，写飞书）。

前置：先跑 `python -m app.jobs.tk_sellfox_sync` 刷新 PG 赛狐数据
（fact_tiktok_product source=sellfox + fact_sellfox_tk_profit_sku）。

灌入范围（见 SPEC/ARCH/EXPLORE/FINDINGS）：
  主数据 5 列：货源 / 品名 / SKUID / 上架状态 / 售价含VAT
  成本 1 列：采购 GBP（profit_sku purchaseFee 取绝对值）
  13 公式列 + CNY/亚马逊/黑马/服务费/操作费/配送费/SKU —— 不灌（飞书自算或保留手填）

覆盖策略：
  --full：首次全量，覆盖已有行 6 可写列 + 新建 PG 有而飞书无的行
  默认（只新增）：仅 batch_create PG 有而飞书无的行，已有行不动

缺数据：赛狐无 profit_sku 的在售 SKU 记日志 + 推飞书群（SKU 列表，无金额）

用法（容器内）:
  PYTHONPATH=/app python -m app.jobs.tk_sellfox_product_feishu_sync --dry-run
  PYTHONPATH=/app python -m app.jobs.tk_sellfox_product_feishu_sync --full
  PYTHONPATH=/app python -m app.jobs.tk_sellfox_product_feishu_sync            # 只新增
  PYTHONPATH=/app python -m app.jobs.tk_sellfox_product_feishu_sync --shop gardena --full

环境变量:
  DATABASE_URL
  FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_BITABLE_APP_TOKEN_TK
  FEISHU_BITABLE_TABLE_TK_PRODUCT
  FEISHU_BOT_WEBHOOK_TK_HEALTH（缺数据告警，空则只落日志）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.feishu import bitable
from app.adapters.feishu.bitable import BASE, FeishuError, get_tenant_access_token
from app.config import get_settings
from app.infra.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("qingquan.tk_sellfox_product_feishu_sync")

# 在售状态过滤（PG fact_tiktok_product.status）
_IN_SELL_STATUSES = ("在售", "active", "在线")

# 飞书 TK产品表 table_id（.env）
_TABLE_TK_PRODUCT = "tbl69GJ8cAAhizmj"


# ---- PG 读取 ----

# 在售商品 + 关联 profit_sku（拆 seller_sku 多规格 | 拼接，取 period_end 最大一期）
# 返回每行：product_id, product_name, seller_sku(原始), status, price_include_vat, purchase_fee_gbp(abs)
_PRODUCT_SELECT = """
SELECT
    p.product_id,
    p.product_name,
    p.seller_sku,
    p.status,
    p.raw_extra->>'price_include_vat' AS price_include_vat,
    prof.purchase_fee_gbp
FROM tk.fact_tiktok_product p
LEFT JOIN LATERAL (
    SELECT abs(CAST(raw_extra->>'purchaseFee' AS numeric)) AS purchase_fee_gbp
    FROM tk.fact_sellfox_tk_profit_sku s
    WHERE s.currency = 'GBP'
      AND (
          s.sku_key = p.seller_sku
          OR s.sku_key = ANY(string_to_array(p.seller_sku, '|'))
      )
    ORDER BY s.period_end DESC
    LIMIT 1
) prof ON true
WHERE p.status = ANY(:statuses)
ORDER BY p.product_id
"""


async def _read_in_sell_products(db: AsyncSession) -> list[dict[str, Any]]:
    """读在售商品 + 关联赛狐采购成本。"""
    rows = (
        await db.execute(
            text(_PRODUCT_SELECT),
            {"statuses": list(_IN_SELL_STATUSES)},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def _check_sellfox_data_present(db: AsyncSession) -> tuple[bool, bool]:
    """前置检查：product 表 / profit_sku 表是否有数据。返回 (has_product, has_profit_sku)。"""
    p = (
        await db.execute(text("SELECT count(*) FROM tk.fact_tiktok_product"))
    ).scalar() or 0
    s = (
        await db.execute(text("SELECT count(*) FROM tk.fact_sellfox_tk_profit_sku"))
    ).scalar() or 0
    return int(p) > 0, int(s) > 0


# ---- 飞书现有行读取（建 product_id → record_id 幂等 dict）----


async def _list_feishu_records(
    token: str, app_token: str, table_id: str
) -> dict[str, str]:
    """拉飞书表所有记录，返回 {货源列值(product_id): record_id}。

    货源是主字段（is_primary）；货源列为空的行无法匹配，跳过。
    """
    mapping: dict[str, str] = {}
    page_token: str | None = None
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            url = (
                f"{BASE}/bitable/v1/apps/{app_token}/tables/{table_id}"
                f"/records?page_size=500"
            )
            if page_token:
                url += f"&page_token={page_token}"
            resp = await client.get(
                url, headers={"Authorization": f"Bearer {token}"}
            )
            data = resp.json()
            if data.get("code") != 0:
                logger.warning("list feishu records failed: %s", data.get("msg"))
                break
            for item in (data.get("data") or {}).get("items") or []:
                rid = item.get("record_id")
                fields = item.get("fields") or {}
                # 货源是 Text 主字段；飞书返回纯字符串或 [文本段] 列表
                v = fields.get("货源")
                pid = _extract_text(v)
                if pid and rid:
                    mapping[pid] = rid
            if not (data.get("data") or {}).get("has_more"):
                break
            page_token = (data.get("data") or {}).get("page_token")
    return mapping


def _extract_text(v: Any) -> str:
    """飞书 Text 字段值可能是 str 或 [{type:text,text:...}, ...]，提取纯文本。"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        parts = []
        for seg in v:
            if isinstance(seg, dict):
                parts.append(str(seg.get("text") or seg.get("name") or ""))
            else:
                parts.append(str(seg))
        return "".join(parts).strip()
    return str(v).strip()


async def _list_table_field_names(
    token: str, app_token: str, table_id: str
) -> set[str]:
    """飞书表现存字段名（写前过滤；NOTE：含 Formula 列名，不挡公式列——见 FINDINGS）。"""
    names: set[str] = set()
    page_token: str | None = None
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            url = (
                f"{BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=100"
            )
            if page_token:
                url += f"&page_token={page_token}"
            resp = await client.get(
                url, headers={"Authorization": f"Bearer {token}"}
            )
            data = resp.json()
            if data.get("code") != 0:
                break
            for it in (data.get("data") or {}).get("items") or []:
                n = (it.get("field_name") or "").strip()
                if n:
                    names.add(n)
            if not (data.get("data") or {}).get("has_more"):
                break
            page_token = (data.get("data") or {}).get("page_token")
    return names


def _filter_fields(fields: dict[str, Any], allowed: set[str] | None) -> dict[str, Any]:
    if not allowed:
        return fields
    return {k: v for k, v in fields.items() if k in allowed}


# ---- 缺数据告警（飞书群机器人，无金额）----


async def _notify_missing(
    webhook: str, missing_skus: list[str], stats: dict[str, Any]
) -> None:
    """推飞书群告警：缺赛狐利润数据的在售 SKU 列表（不含金额）。webhook 空则只落日志。"""
    if not missing_skus:
        return
    if not webhook:
        logger.warning(
            "missing sellfox profit data for %d SKUs (webhook 未配置，仅落日志): %s",
            len(missing_skus),
            ", ".join(missing_skus[:50]),
        )
        return
    sku_list = "\n".join(f"- {s}" for s in missing_skus[:100])
    msg = {
        "msg_type": "text",
        "content": {
            "text": (
                f"【TK产品表赛狐同步】{len(missing_skus)} 个在售 SKU 赛狐无利润数据\n"
                f"同步统计：created={stats.get('created',0)} "
                f"updated={stats.get('updated',0)} "
                f"skipped={stats.get('skipped_no_sellfox',0)} "
                f"failed={stats.get('failed',0)}\n"
                f"缺数据 SKU（前100）：\n{sku_list}"
            )
        },
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook, json=msg)
            data = resp.json()
            if data.get("code") not in (0, None):
                logger.warning("notify webhook resp: %s", data)
    except Exception as exc:
        logger.warning("notify webhook failed: %s", exc)


# ---- 主同步 ----


async def run_sync(*, full: bool, dry_run: bool, shop_filter: str | None) -> dict[str, Any]:
    """主同步。

    full=True：首次全量（覆盖已有行 6 可写列 + 新建缺行）
    full=False：只新增（仅 create PG 有而飞书无的行，已有行不动）
    dry_run=True：打印将 create/update 的行/列，不实写
    shop_filter：可选单店过滤（deal/gardena/shop-inout，按 shop_external_id）
    """
    settings = get_settings()
    stats = {
        "scanned": 0,
        "created": 0,
        "updated": 0,
        "skipped_no_sellfox": 0,
        "unchanged": 0,
        "failed": 0,
    }
    missing_skus: list[str] = []

    # 飞书配置
    app_token = (settings.feishu_bitable_app_token_tk or settings.feishu_bitable_app_token or "").strip()
    table_id = (settings.feishu_bitable_table_tk_product or "").strip() or _TABLE_TK_PRODUCT
    if not app_token:
        raise RuntimeError("FEISHU_BITABLE_APP_TOKEN_TK 未配置")
    webhook = (settings.feishu_bot_webhook_tk_health or "").strip()

    # 前置检查：PG 赛狐数据
    async with SessionLocal() as db:
        has_product, has_profit = await _check_sellfox_data_present(db)
        if not has_product:
            logger.error("PG fact_tiktok_product 无数据；先跑 python -m app.jobs.tk_sellfox_sync")
            return {"status": "aborted", "reason": "no product data", "stats": stats}
        if not has_profit:
            logger.warning("PG fact_sellfox_tk_profit_sku 无数据（采购GBP 将全空）；建议先跑 tk_sellfox_sync")

        rows = await _read_in_sell_products(db)
        if shop_filter:
            # 单店过滤（按 shop_external_id；这里 product 无店字段，简化为不过滤或后续扩展）
            # 注：fact_tiktok_product 有 shop_external_id，但本期 SELECT 未取；单店过滤留 P4
            logger.info("shop_filter=%s 暂未在 SQL 层过滤（本期 P4 待补）", shop_filter)

    stats["scanned"] = len(rows)
    logger.info("in-sell products scanned=%d full=%s dry_run=%s", len(rows), full, dry_run)

    # 区分：有采购成本（赛狐有 profit_sku） vs 无（缺数据）
    with_cost: list[dict[str, Any]] = []
    without_cost: list[dict[str, Any]] = []
    for r in rows:
        if r.get("purchase_fee_gbp") is not None:
            with_cost.append(r)
        else:
            without_cost.append(r)
            sku = str(r.get("seller_sku") or "").strip()
            if sku:
                missing_skus.append(sku)
    stats["skipped_no_sellfox"] = len(without_cost)
    logger.info(
        "with_cost=%d without_cost=%d (将告警)", len(with_cost), len(without_cost)
    )

    if dry_run:
        logger.info("[dry-run] 将 create/update 的行（with_cost 前10）:")
        for r in with_cost[:10]:
            logger.info(
                "  product_id=%s sku=%s purchase_gbp=%s",
                r.get("product_id"), r.get("seller_sku"), r.get("purchase_fee_gbp"),
            )
        return {
            "status": "dry_run",
            "stats": stats,
            "missing_skus_preview": missing_skus[:20],
        }

    # 飞书 token + 现有行映射
    token = await get_tenant_access_token()
    if not token:
        raise RuntimeError("飞书 tenant_access_token 获取失败（检查 FEISHU_APP_ID/SECRET）")

    existing = await _list_feishu_records(token, app_token, table_id)
    logger.info("feishu existing records (by 货源)=%d", len(existing))

    allowed = await _list_table_field_names(token, app_token, table_id)
    logger.info("feishu table writable fields=%d (含 Formula 列名，mapper 已 omit)", len(allowed))

    # 组装 fields
    to_create: list[dict[str, Any]] = []
    to_update: list[tuple[str, dict[str, Any]]] = []
    for r in with_cost:
        fields = _filter_fields(bitable.tk_product_to_fields(r), allowed or None)
        if not fields:
            continue
        pid = str(r.get("product_id") or "").strip()
        if pid in existing:
            if full:
                to_update.append((existing[pid], fields))
            else:
                stats["unchanged"] += 1  # 只新增模式：已有行不动
        else:
            to_create.append(fields)

    logger.info("plan: create=%d update=%d unchanged=%d", len(to_create), len(to_update), stats["unchanged"])

    # 批写（batch 上限 500；稳妥 100）
    BATCH = 100
    for i in range(0, len(to_create), BATCH):
        chunk = to_create[i : i + BATCH]
        try:
            await bitable.batch_create_records(token, app_token, table_id, chunk)
            stats["created"] += len(chunk)
        except FeishuError as exc:
            logger.error("batch_create failed chunk=%d: %s", i, exc)
            stats["failed"] += len(chunk)
    for i in range(0, len(to_update), BATCH):
        chunk = to_update[i : i + BATCH]
        try:
            await bitable.batch_update_records(token, app_token, table_id, chunk)
            stats["updated"] += len(chunk)
        except FeishuError as exc:
            logger.error("batch_update failed chunk=%d: %s", i, exc)
            stats["failed"] += len(chunk)

    # 缺数据告警
    await _notify_missing(webhook, missing_skus, stats)

    # 写 sellfox_sync_run（复用现有表）
    async with SessionLocal() as db:
        run_id = str(uuid4())
        await db.execute(
            text(
                """
                INSERT INTO tk.sellfox_sync_run (
                    id, started_at, status, modules, stats
                ) VALUES (
                    CAST(:id AS uuid), now(), :st,
                    CAST(:modules AS jsonb), CAST(:stats AS jsonb)
                )
                """
            ),
            {
                "id": run_id,
                "st": "success" if stats["failed"] == 0 else "partial",
                "modules": json.dumps(["product_feishu"]),
                "stats": json.dumps(stats, ensure_ascii=False, default=str),
            },
        )
        await db.commit()

    logger.info("done: %s", json.dumps(stats, ensure_ascii=False))
    return {"status": "success" if stats["failed"] == 0 else "partial", "stats": stats, "run_id": run_id}


def main() -> None:
    ap = argparse.ArgumentParser(description="赛狐 PG → 飞书 TK产品表 同步")
    ap.add_argument("--full", action="store_true", help="首次全量：覆盖已有行 6 可写列 + 新建缺行")
    ap.add_argument("--dry-run", action="store_true", help="只打印将 create/update 的行，不实写")
    ap.add_argument("--shop", default=None, help="可选单店过滤（deal/gardena/shop-inout，本期 P4 待补）")
    args = ap.parse_args()
    logger.info("run tk_sellfox_product_feishu_sync full=%s dry_run=%s shop=%s", args.full, args.dry_run, args.shop)
    result = asyncio.run(run_sync(full=args.full, dry_run=args.dry_run, shop_filter=args.shop))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
