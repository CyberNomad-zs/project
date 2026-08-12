"""TikTok 驾驶舱：PG tk 事实表 → 飞书多维表同步。

table_key:
  - tk_shop_daily     → 店日宽表（shop + ads rollup + health/finance）→ T1
  - tk_ads_campaign   → fact_ads_campaign_daily → T2
  - tk_anomaly_task   → fact_tk_anomaly_task → 异常任务（对齐 AMZ 飞书异常任务）
  - tk_content_daily  → fact_tiktok_content_daily → T6 内容日
  - tk_experience_daily → fact_tiktok_experience_daily → 体验分日

正式链路：Ingest → PG → 本模块（export / worker）→ 飞书。
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.feishu import bitable
from app.config import Settings, get_settings

logger = logging.getLogger("qingquan.tk_feishu_sync")

# backend/app/jobs → 仓库根
_REPO_ROOT = Path(__file__).resolve().parents[3]

# 店日宽表：shop_daily 左连广告聚合 + health + finance（同店同日）
_SHOP_DAILY_SELECT = """
    SELECT
        s.id::text AS id,
        s.shop_external_id,
        s.shop_name,
        s.biz_date,
        s.gmv,
        s.orders_cnt,
        s.buyers_cnt,
        s.refund_amount,
        s.currency,
        s.source_url,
        s.collected_at,
        s.updated_at,
        COALESCE(a.ad_spend, 0) AS ad_spend,
        COALESCE(a.ad_revenue, 0) AS ad_revenue,
        COALESCE(a.ad_orders, 0) AS ad_orders,
        a.ad_currency,
        h.health_score,
        h.status_label AS health_status,
        h.late_dispatch_rate,
        h.negative_feedback_rate,
        f.settlement_amount,
        f.pending_amount,
        f.refund_amount AS finance_refund,
        f.currency AS finance_currency
    FROM tk.fact_tiktok_shop_daily s
    LEFT JOIN (
        SELECT
            shop_external_id,
            biz_date,
            SUM(spend) AS ad_spend,
            SUM(revenue) AS ad_revenue,
            SUM(orders) AS ad_orders,
            MAX(currency) AS ad_currency
        FROM tk.fact_ads_campaign_daily
        WHERE campaign_name !~ '^【'
        GROUP BY shop_external_id, biz_date
    ) a
      ON a.shop_external_id = s.shop_external_id
     AND a.biz_date = s.biz_date
    LEFT JOIN tk.fact_tiktok_health_daily h
      ON h.shop_external_id = s.shop_external_id
     AND h.biz_date = s.biz_date
    LEFT JOIN tk.fact_tiktok_finance_daily f
      ON f.shop_external_id = s.shop_external_id
     AND f.biz_date = s.biz_date
    WHERE (
            CAST(:filter_biz AS boolean) = false
            OR s.biz_date = :biz_date
          )
      AND (
            CAST(:filter_since AS boolean) = false
            OR s.updated_at >= :since
            OR s.biz_date >= :since_date
          )
    ORDER BY s.biz_date DESC, s.shop_external_id
    LIMIT :lim
"""

# 无 shop_daily 时：用广告活动日 rollup 撑起 T1 多店对比（GMV 先用广告销售额占位）
_SHOP_FROM_ADS_SELECT = """
    SELECT
        md5(a.shop_external_id || ':' || a.biz_date::text)::uuid::text AS id,
        a.shop_external_id,
        a.shop_name,
        a.biz_date,
        a.ad_revenue AS gmv,
        a.ad_orders AS orders_cnt,
        NULL::numeric AS buyers_cnt,
        NULL::numeric AS refund_amount,
        a.ad_currency AS currency,
        NULL::text AS source_url,
        a.collected_at,
        a.updated_at,
        a.ad_spend,
        a.ad_revenue,
        a.ad_orders,
        a.ad_currency,
        h.health_score,
        h.status_label AS health_status,
        h.late_dispatch_rate,
        h.negative_feedback_rate,
        f.settlement_amount,
        f.pending_amount,
        f.refund_amount AS finance_refund,
        f.currency AS finance_currency
    FROM (
        SELECT
            shop_external_id,
            MAX(shop_name) AS shop_name,
            biz_date,
            SUM(spend) AS ad_spend,
            SUM(revenue) AS ad_revenue,
            SUM(orders) AS ad_orders,
            MAX(currency) AS ad_currency,
            MAX(collected_at) AS collected_at,
            MAX(updated_at) AS updated_at
        FROM tk.fact_ads_campaign_daily
        WHERE campaign_name !~ '^【'
        GROUP BY shop_external_id, biz_date
    ) a
    LEFT JOIN tk.fact_tiktok_health_daily h
      ON h.shop_external_id = a.shop_external_id
     AND h.biz_date = a.biz_date
    LEFT JOIN tk.fact_tiktok_finance_daily f
      ON f.shop_external_id = a.shop_external_id
     AND f.biz_date = a.biz_date
    WHERE (
            CAST(:filter_biz AS boolean) = false
            OR a.biz_date = :biz_date
          )
      AND (
            CAST(:filter_since AS boolean) = false
            OR a.updated_at >= :since
            OR a.biz_date >= :since_date
          )
    ORDER BY a.biz_date DESC, a.shop_external_id
    LIMIT :lim
"""

_ADS_SELECT = """
    SELECT
        id::text,
        shop_external_id,
        shop_name,
        biz_date,
        campaign_name,
        spend,
        orders,
        roi,
        revenue,
        currency,
        row_status,
        source_url,
        plan_status,
        delivery_status,
        daily_budget,
        target_roi,
        net_cost,
        avg_order_cost,
        collected_at,
        updated_at
    FROM tk.fact_ads_campaign_daily
    WHERE campaign_name !~ '^【'
      AND (
            CAST(:filter_biz AS boolean) = false
            OR biz_date = :biz_date
          )
      AND (
            CAST(:filter_since AS boolean) = false
            OR updated_at >= :since
            OR biz_date >= :since_date
          )
    ORDER BY biz_date DESC, shop_external_id, campaign_name
    LIMIT :lim
"""

_ANOMALY_TASK_SELECT = """
    SELECT
        id::text,
        task_key,
        biz_date,
        shop_external_id,
        shop_name,
        product_id,
        seller_sku,
        product_name,
        product_name_cn,
        object_ref,
        object_type,
        anomaly_type,
        anomaly_code,
        priority,
        status,
        owner_name,
        due_at,
        progress_note,
        summary,
        metric_snapshot,
        level_code,
        current_value,
        current_value_label,
        compare_value,
        compare_value_label,
        change_magnitude,
        change_magnitude_label,
        streak_count,
        needs_boss_decision,
        description,
        is_confirmed,
        judgment_basis,
        action_taken,
        executor_name,
        executed_at,
        data_before,
        data_after,
        is_effective,
        review_items,
        review_date,
        next_action,
        close_status,
        reviewer_name,
        center_task_id::text,
        dedupe_key,
        collected_at,
        updated_at
    FROM tk.fact_tk_anomaly_task
    WHERE (
            CAST(:filter_biz AS boolean) = false
            OR biz_date = :biz_date
          )
      AND (
            CAST(:filter_since AS boolean) = false
            OR updated_at >= :since
            OR biz_date >= :since_date
            OR status IN ('open', 'in_progress')
          )
    ORDER BY biz_date DESC, priority, shop_external_id
    LIMIT :lim
"""

_CONTENT_DAILY_SELECT = """
    SELECT
        id::text,
        shop_external_id,
        shop_name,
        biz_date,
        channel,
        content_id,
        content_title,
        product_id,
        attributed_gmv,
        attributed_sku_orders,
        attributed_units,
        play_count,
        impressions,
        clicks,
        ctr,
        cvr,
        customers,
        currency,
        source_url,
        raw_extra,
        collected_at,
        updated_at
    FROM tk.fact_tiktok_content_daily
    WHERE (
            CAST(:filter_biz AS boolean) = false
            OR biz_date = :biz_date
          )
      AND (
            CAST(:filter_since AS boolean) = false
            OR updated_at >= :since
            OR biz_date >= :since_date
          )
    ORDER BY biz_date DESC, shop_external_id, play_count DESC NULLS LAST
    LIMIT :lim
"""

_EXPERIENCE_DAILY_SELECT = """
    SELECT
        id::text,
        shop_external_id,
        shop_name,
        biz_date,
        experience_score,
        product_satisfaction,
        fulfillment_score,
        customer_service_score,
        status_label,
        metrics_json,
        source_url,
        collected_at,
        updated_at
    FROM tk.fact_tiktok_experience_daily
    WHERE (
            CAST(:filter_biz AS boolean) = false
            OR biz_date = :biz_date
          )
      AND (
            CAST(:filter_since AS boolean) = false
            OR updated_at >= :since
            OR biz_date >= :since_date
          )
    ORDER BY biz_date DESC, shop_external_id
    LIMIT :lim
"""

_AFFILIATE_CREATOR_DAILY_SELECT = """
    SELECT
        id::text,
        shop_external_id,
        shop_name,
        biz_date,
        window_label,
        creator_id,
        creator_name,
        creator_handle,
        gmv,
        order_units,
        orders_cnt,
        refund_amount,
        refund_units,
        est_commission,
        video_cnt,
        live_cnt,
        product_sold,
        samples_shipped,
        video_views,
        cvr,
        sold_flag,
        currency,
        source_url,
        collected_at,
        updated_at
    FROM tk.fact_tiktok_affiliate_creator_daily
    WHERE (
            CAST(:filter_biz AS boolean) = false
            OR biz_date = :biz_date
          )
      AND (
            CAST(:filter_since AS boolean) = false
            OR updated_at >= :since
            OR biz_date >= :since_date
          )
    ORDER BY biz_date DESC, shop_external_id, gmv DESC NULLS LAST
    LIMIT :lim
"""

TABLE_SPECS: dict[str, dict[str, Any]] = {
    "tk_shop_daily": {
        "local_table": "tk.fact_tiktok_shop_daily",
        "date_col": "biz_date",
        "mapper": bitable.tk_shop_daily_to_fields,
        "select": _SHOP_DAILY_SELECT,
        # shop_daily 无行时回退：广告日汇总撑 T1（local_id 为稳定 md5 uuid）
        "fallback_select": _SHOP_FROM_ADS_SELECT,
        "fallback_local_table": "tk.ads_shop_day_rollup",
    },
    "tk_ads_campaign": {
        "local_table": "tk.fact_ads_campaign_daily",
        "date_col": "biz_date",
        "mapper": bitable.tk_ads_campaign_to_fields,
        "select": _ADS_SELECT,
    },
    "tk_anomaly_task": {
        "local_table": "tk.fact_tk_anomaly_task",
        "date_col": "biz_date",
        "mapper": bitable.tk_anomaly_task_to_fields,
        "select": _ANOMALY_TASK_SELECT,
    },
    "tk_content_daily": {
        "local_table": "tk.fact_tiktok_content_daily",
        "date_col": "biz_date",
        "mapper": bitable.tk_content_daily_to_fields,
        "select": _CONTENT_DAILY_SELECT,
    },
    "tk_affiliate_creator_daily": {
        "local_table": "tk.fact_tiktok_affiliate_creator_daily",
        "date_col": "biz_date",
        "mapper": bitable.tk_affiliate_creator_daily_to_fields,
        "select": _AFFILIATE_CREATOR_DAILY_SELECT,
    },
    "tk_experience_daily": {
        "local_table": "tk.fact_tiktok_experience_daily",
        "date_col": "biz_date",
        "mapper": bitable.tk_experience_daily_to_fields,
        "select": _EXPERIENCE_DAILY_SELECT,
    },
}


def resolve_tk_app_token(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return (s.feishu_bitable_app_token_tk or s.feishu_bitable_app_token or "").strip()


def resolve_table_id(table_key: str, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    mapping = {
        "tk_shop_daily": s.feishu_bitable_table_tk_shop_daily,
        "tk_ads_campaign": s.feishu_bitable_table_tk_ads_campaign,
        "tk_anomaly_task": s.feishu_bitable_table_tk_anomaly_task,
        "tk_content_daily": s.feishu_bitable_table_tk_content_daily,
        "tk_affiliate_creator_daily": s.feishu_bitable_table_tk_affiliate_creator_daily,
        "tk_experience_daily": s.feishu_bitable_table_tk_experience_daily,
    }
    return (mapping.get(table_key) or "").strip()


def _store_map_path(settings: Settings | None = None) -> Path | None:
    s = settings or get_settings()
    raw = (s.feishu_tk_store_tables_json or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    return p if p.is_file() else None


@lru_cache(maxsize=4)
def load_store_table_mapping(path_str: str) -> dict[str, Any]:
    """读取分店表映射。

    返回:
      {
        "by_slug": { slug: {"name", "aliases": set[str], "tables": {table_key: table_id}} },
        "alias_to_slug": { lower_alias: slug },
      }
    """
    data = json.loads(Path(path_str).read_text(encoding="utf-8"))
    by_slug: dict[str, dict[str, Any]] = {}
    alias_to_slug: dict[str, str] = {}
    tables_root = data.get("tables") or {}
    for st in data.get("stores") or []:
        name = (st.get("name") or "").strip()
        slug = (st.get("slug") or "").strip()
        if not name or not slug:
            continue
        aliases = {str(a).strip() for a in (st.get("aliases") or []) if str(a).strip()}
        aliases.add(name)
        store_tables = tables_root.get(name) or {}
        by_slug[slug] = {
            "name": name,
            "aliases": aliases,
            "tables": {k: str(v).strip() for k, v in store_tables.items() if v},
        }
        for a in aliases:
            alias_to_slug[a.casefold()] = slug
    return {"by_slug": by_slug, "alias_to_slug": alias_to_slug}


def get_store_table_mapping(settings: Settings | None = None) -> dict[str, Any] | None:
    path = _store_map_path(settings)
    if not path:
        return None
    try:
        return load_store_table_mapping(str(path.resolve()))
    except Exception as exc:
        logger.warning("load store table mapping failed: %s", exc)
        return None


def match_store_slug(shop_name: str | None, mapping: dict[str, Any]) -> str | None:
    if not shop_name:
        return None
    key = str(shop_name).strip().casefold()
    if not key:
        return None
    return (mapping.get("alias_to_slug") or {}).get(key)


def map_key_for(table_key: str, store_slug: str | None = None) -> str:
    """sync_feishu_map.table_key：总表用原 key，分店表用 table_key::slug。"""
    if store_slug:
        return f"{table_key}::{store_slug}"
    return table_key


async def _upsert_rows_to_feishu(
    db: AsyncSession,
    *,
    rows: list[Any],
    mapper,
    token: str,
    app_token: str,
    table_id: str,
    map_table_key: str,
    local_table: str,
) -> dict[str, Any]:
    created = updated = unchanged = failed = 0
    errors: list[str] = []

    for row in rows:
        local_id = row["id"]
        fields = mapper(dict(row))
        chash = bitable.content_hash(fields)
        try:
            mapped = (
                await db.execute(
                    text(
                        """
                        SELECT id::text, record_id, content_hash
                        FROM sync_feishu_map
                        WHERE table_key = :tk AND local_id = CAST(:lid AS uuid)
                        """
                    ),
                    {"tk": map_table_key, "lid": local_id},
                )
            ).mappings().first()

            if mapped and mapped["content_hash"] == chash:
                unchanged += 1
                continue

            if mapped:
                await bitable.batch_update_records(
                    token, app_token, table_id, [(mapped["record_id"], fields)]
                )
                await db.execute(
                    text(
                        """
                        UPDATE sync_feishu_map
                        SET content_hash = :h, synced_at = now(),
                            app_token = :app_token, table_id = :table_id
                        WHERE id = CAST(:id AS uuid)
                        """
                    ),
                    {
                        "h": chash,
                        "id": mapped["id"],
                        "app_token": app_token,
                        "table_id": table_id,
                    },
                )
                updated += 1
            else:
                ids = await bitable.batch_create_records(
                    token, app_token, table_id, [fields]
                )
                if not ids:
                    raise RuntimeError("batch_create returned empty")
                await db.execute(
                    text(
                        """
                        INSERT INTO sync_feishu_map (
                            id, table_key, local_table, local_id, app_token, table_id,
                            record_id, content_hash, synced_at
                        ) VALUES (
                            :id, :table_key, :local_table, CAST(:local_id AS uuid),
                            :app_token, :table_id, :record_id, :h, now()
                        )
                        ON CONFLICT (table_key, local_id) DO UPDATE SET
                            record_id = EXCLUDED.record_id,
                            content_hash = EXCLUDED.content_hash,
                            app_token = EXCLUDED.app_token,
                            table_id = EXCLUDED.table_id,
                            synced_at = now()
                        """
                    ),
                    {
                        "id": str(uuid4()),
                        "table_key": map_table_key,
                        "local_table": local_table,
                        "local_id": local_id,
                        "app_token": app_token,
                        "table_id": table_id,
                        "record_id": ids[0],
                        "h": chash,
                    },
                )
                created += 1
            await db.commit()
        except Exception as exc:
            await db.rollback()
            failed += 1
            msg = f"{local_id}: {exc}"
            errors.append(msg)
            logger.exception("sync %s row %s failed", map_table_key, local_id)

    return {
        "scanned": len(rows),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "failed": failed,
        "errors": errors[:10],
    }


async def sync_table(
    db: AsyncSession,
    *,
    table_key: str,
    mode: str = "incremental",
    biz_date: str | date | None = None,
    lookback_days: int = 14,
    limit: int = 500,
    dry_run: bool = False,
) -> dict[str, Any]:
    """将 PG 行 upsert 到飞书总表；若配置了分店映射，再按店写入分店表。"""
    if table_key not in TABLE_SPECS:
        raise ValueError(f"unsupported table_key: {table_key}")

    settings = get_settings()
    app_token = resolve_tk_app_token(settings)
    table_id = resolve_table_id(table_key, settings)
    if not app_token or not table_id:
        return {
            "table_key": table_key,
            "status": "skipped",
            "reason": "feishu tk table not configured",
            "scanned": 0,
            "created": 0,
            "updated": 0,
            "unchanged": 0,
        }

    spec = TABLE_SPECS[table_key]
    # 传 Python date/datetime + 布尔开关，避免 asyncpg 对 NULL 参数类型歧义
    if biz_date is None:
        bd: date | None = None
    elif isinstance(biz_date, datetime):
        bd = biz_date.date()
    elif isinstance(biz_date, date):
        bd = biz_date
    else:
        s = str(biz_date).strip()[:10]
        bd = date.fromisoformat(s) if s else None

    filter_biz = bd is not None
    filter_since = False
    since = datetime(1970, 1, 1, tzinfo=timezone.utc)
    since_date = date(1970, 1, 1)
    if mode == "incremental" and bd is None:
        filter_since = True
        since = datetime.now(timezone.utc) - timedelta(days=max(1, lookback_days))
        since_date = since.date()
    bind_biz = bd or date(1970, 1, 1)

    bind = {
        "filter_biz": filter_biz,
        "filter_since": filter_since,
        "biz_date": bind_biz,
        "since": since,
        "since_date": since_date,
        "lim": limit,
    }
    rows = (await db.execute(text(spec["select"]), bind)).mappings().all()
    local_table = spec["local_table"]
    used_fallback = False
    if not rows and spec.get("fallback_select"):
        rows = (await db.execute(text(spec["fallback_select"]), bind)).mappings().all()
        local_table = spec.get("fallback_local_table") or local_table
        used_fallback = bool(rows)
        if used_fallback:
            logger.info(
                "tk_shop_daily: shop_daily empty, using ads rollup fallback (%s rows)",
                len(rows),
            )

    store_mapping = get_store_table_mapping(settings)
    store_targets: list[dict[str, Any]] = []
    if store_mapping:
        for slug, meta in (store_mapping.get("by_slug") or {}).items():
            tid = (meta.get("tables") or {}).get(table_key) or ""
            if tid and not str(tid).startswith("dry_"):
                store_targets.append(
                    {
                        "slug": slug,
                        "name": meta.get("name"),
                        "table_id": tid,
                        "aliases": meta.get("aliases") or set(),
                    }
                )

    if dry_run:
        by_store = {}
        if store_mapping:
            for t in store_targets:
                n = 0
                for r in rows:
                    if match_store_slug(r.get("shop_name"), store_mapping) == t["slug"]:
                        n += 1
                by_store[t["slug"]] = n
        return {
            "table_key": table_key,
            "status": "dry_run",
            "scanned": len(rows),
            "fallback": used_fallback,
            "store_tables": by_store,
            "sample": [dict(r) for r in rows[:3]],
        }

    token = await bitable.get_tenant_access_token()
    if not token:
        return {
            "table_key": table_key,
            "status": "skipped",
            "reason": "feishu credentials missing",
            "scanned": len(rows),
            "created": 0,
            "updated": 0,
            "unchanged": 0,
        }

    mapper = spec["mapper"]
    global_stats = await _upsert_rows_to_feishu(
        db,
        rows=list(rows),
        mapper=mapper,
        token=token,
        app_token=app_token,
        table_id=table_id,
        map_table_key=map_key_for(table_key),
        local_table=local_table,
    )

    store_stats: dict[str, Any] = {}
    store_failed = 0
    if store_mapping and store_targets:
        for t in store_targets:
            filtered = [
                r
                for r in rows
                if match_store_slug(r.get("shop_name"), store_mapping) == t["slug"]
            ]
            st = await _upsert_rows_to_feishu(
                db,
                rows=filtered,
                mapper=mapper,
                token=token,
                app_token=app_token,
                table_id=t["table_id"],
                map_table_key=map_key_for(table_key, t["slug"]),
                local_table=local_table,
            )
            store_stats[t["slug"]] = {
                "table_id": t["table_id"],
                "name": t["name"],
                **st,
            }
            store_failed += int(st.get("failed") or 0)
            logger.info(
                "store fan-out %s %s -> %s scanned=%s c=%s u=%s",
                table_key,
                t["slug"],
                t["table_id"],
                st.get("scanned"),
                st.get("created"),
                st.get("updated"),
            )

    failed = int(global_stats.get("failed") or 0) + store_failed
    return {
        "table_key": table_key,
        "status": "success" if failed == 0 else "partial",
        "scanned": len(rows),
        "created": global_stats.get("created", 0),
        "updated": global_stats.get("updated", 0),
        "unchanged": global_stats.get("unchanged", 0),
        "failed": failed,
        "fallback": used_fallback,
        "errors": global_stats.get("errors") or [],
        "stores": store_stats,
    }


async def run_feishu_job(db: AsyncSession, job_id: str) -> dict[str, Any]:
    """处理 sync_feishu_job 一行（tk_* table_key）。"""
    row = (
        await db.execute(
            text(
                """
                SELECT id::text, table_key, mode, payload, status
                FROM sync_feishu_job WHERE id = CAST(:id AS uuid)
                """
            ),
            {"id": job_id},
        )
    ).mappings().first()
    if not row:
        return {"status": "missing", "job_id": job_id}

    await db.execute(
        text(
            """
            UPDATE sync_feishu_job
            SET status = 'running', started_at = now()
            WHERE id = CAST(:id AS uuid)
            """
        ),
        {"id": job_id},
    )
    await db.commit()

    payload = row["payload"] or {}
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)
    biz_date = payload.get("biz_date")
    lookback_days = int(payload.get("lookback_days") or 14)
    limit = int(payload.get("limit") or 500)
    dry_run = bool(payload.get("dry_run"))

    try:
        stats = await sync_table(
            db,
            table_key=row["table_key"],
            mode=row["mode"] or "incremental",
            biz_date=biz_date,
            lookback_days=lookback_days,
            limit=limit,
            dry_run=dry_run,
        )
        import json

        await db.execute(
            text(
                """
                UPDATE sync_feishu_job
                SET status = :st, finished_at = now(),
                    payload = payload || CAST(:stats AS jsonb),
                    error_message = NULL
                WHERE id = CAST(:id AS uuid)
                """
            ),
            {
                "id": job_id,
                "st": "success" if stats.get("status") in ("success", "skipped", "dry_run") else "failed",
                "stats": json.dumps({"result": stats}, ensure_ascii=False, default=str),
            },
        )
        await db.commit()
        return stats
    except Exception as exc:
        await db.rollback()
        await db.execute(
            text(
                """
                UPDATE sync_feishu_job
                SET status = 'failed', finished_at = now(), error_message = :err
                WHERE id = CAST(:id AS uuid)
                """
            ),
            {"id": job_id, "err": str(exc)[:2000]},
        )
        await db.commit()
        raise
