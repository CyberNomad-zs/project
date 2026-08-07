"""每日汇总：聚合异常数据写入飞书「每日汇总」母表 + 按店子表。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, get_settings
from app.store.db import Database
from app.sync.feishu_schema import summary_to_fields
from app.sync.shops import (
    ShopTableRegistry,
    dual_write_enabled,
    shop_match_variants,
)

logger = logging.getLogger(__name__)


def build_summary_row(
    db: Database,
    biz_date: str,
    *,
    shop_names: list[str] | None = None,
    pk_suffix: str | None = None,
) -> dict[str, Any]:
    """调用 db 聚合查询，返回飞书字段字典。

    pk_suffix: 子表主键用 biz_date|shop，避免与母表混淆（母表仍用 biz_date）。
    """
    agg = db.aggregate_daily_summary(biz_date, shop_names=shop_names)
    fields = summary_to_fields(agg)
    if pk_suffix:
        fields["主键"] = f"{biz_date}|{pk_suffix}"
    return fields


def write_summary_to_feishu(
    db: Database,
    biz_date: str,
    *,
    settings: Settings | None = None,
) -> int:
    """聚合当日数据并 upsert 到飞书每日汇总母表 + 各店子表。返回母表写入记录数。"""
    settings = settings or get_settings()
    app_token = settings.feishu_bitable_app_token
    table_id = settings.feishu_table_daily_summary

    if not settings.has_feishu or not app_token or not table_id:
        logger.warning("飞书每日汇总表未配置，跳过")
        return 0

    row = build_summary_row(db, biz_date)
    fields = {k: v for k, v in row.items() if v is not None}
    if not fields.get("主键"):
        logger.warning("每日汇总主键为空，跳过 biz_date=%s", biz_date)
        return 0

    from app.clients.feishu import FeishuClient

    with FeishuClient(settings) as client:
        stats = client.upsert_by_text_key(
            app_token, table_id, [fields], key_field="主键"
        )
    n = int(stats.get("total") or 0)
    logger.info("每日汇总母表写入完成 biz_date=%s records=%s", biz_date, n)

    if dual_write_enabled():
        registry = ShopTableRegistry.load(settings.shop_tables_path)
        child_n = 0
        for shop, child_tid in registry.all_table_ids("daily_summary"):
            variants = shop_match_variants(shop)
            child_row = build_summary_row(
                db, biz_date, shop_names=variants, pk_suffix=shop
            )
            child_fields = {k: v for k, v in child_row.items() if v is not None}
            if not child_fields.get("主键"):
                continue
            try:
                with FeishuClient(settings) as client:
                    st = client.upsert_by_text_key(
                        app_token, child_tid, [child_fields], key_field="主键"
                    )
                child_n += int(st.get("total") or 0)
            except Exception:
                logger.exception("每日汇总子表写入失败 shop=%s", shop)
        logger.info("每日汇总子表写入 records=%s", child_n)

    return n
