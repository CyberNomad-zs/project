"""Amazon 驾驶舱：PG 事实表 → 飞书多维表同步。

table_key:
  - amz_shop_daily  → fact_amz_shop_daily → T1
  - amz_link_daily  → fact_amz_link_daily → T3
  - amz_risk        → fact_amz_risk_alert → T6

正式链路：Ingest → PG → 本模块（由 export / worker 触发）→ 飞书。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.feishu import bitable
from app.config import Settings, get_settings

logger = logging.getLogger("qingquan.amz_feishu_sync")

TABLE_SPECS: dict[str, dict[str, Any]] = {
    "amz_shop_daily": {
        "local_table": "fact_amz_shop_daily",
        "date_col": "biz_date",
        "mapper": bitable.amz_shop_daily_to_fields,
        "select": """
            SELECT id::text, shop_external_id, shop_name, biz_date, marketplace, currency,
                   sales_amount, orders_cnt, units, sessions, add_to_cart, aov,
                   refund_units, refund_rate, gross_profit, ad_spend, ad_sales, acos,
                   ad_contrib_margin, net_profit, net_margin, roi,
                   sales_mom_ratio, profit_mom_ratio, sales_yoy_ratio,
                   row_status, source_url, collected_at
            FROM fact_amz_shop_daily
            WHERE (:biz_date IS NULL OR biz_date = CAST(:biz_date AS date))
              AND (:since IS NULL OR updated_at >= CAST(:since AS timestamptz)
                   OR biz_date >= CAST(:since_date AS date))
            ORDER BY biz_date DESC, shop_external_id
            LIMIT :lim
        """,
    },
    "amz_link_daily": {
        "local_table": "fact_amz_link_daily",
        "date_col": "biz_date",
        "mapper": bitable.amz_link_daily_to_fields,
        "select": """
            SELECT id::text, shop_external_id, biz_date, asin, seller_sku, title, category,
                   units, sales_amount, currency, sessions, ad_spend, acos, unit_net_profit,
                   fba_fulfillable, days_of_supply, refund_rate,
                   units_mom_ratio, sales_mom_ratio, problem_tags, owner_name, collected_at
            FROM fact_amz_link_daily
            WHERE (:biz_date IS NULL OR biz_date = CAST(:biz_date AS date))
              AND (:since IS NULL OR updated_at >= CAST(:since AS timestamptz)
                   OR biz_date >= CAST(:since_date AS date))
            ORDER BY biz_date DESC, shop_external_id, asin
            LIMIT :lim
        """,
    },
    "amz_risk": {
        "local_table": "fact_amz_risk_alert",
        "date_col": "detected_on",
        "mapper": bitable.amz_risk_to_fields,
        "select": """
            SELECT id::text, alert_key, detected_on, shop_external_id, shop_name,
                   object_ref, risk_type, priority, summary, metric_snapshot,
                   status, owner_name, task_id::text, updated_at
            FROM fact_amz_risk_alert
            WHERE (:biz_date IS NULL OR detected_on = CAST(:biz_date AS date))
              AND (
                    :since IS NULL
                    OR updated_at >= CAST(:since AS timestamptz)
                    OR detected_on >= CAST(:since_date AS date)
                    OR status IN ('open', 'in_progress')
                  )
            ORDER BY detected_on DESC, priority
            LIMIT :lim
        """,
    },
}


def resolve_amz_app_token(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return (s.feishu_bitable_app_token_amz or s.feishu_bitable_app_token or "").strip()


def resolve_table_id(table_key: str, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    mapping = {
        "amz_shop_daily": s.feishu_bitable_table_amz_shop_daily,
        "amz_link_daily": s.feishu_bitable_table_amz_link_daily,
        "amz_risk": s.feishu_bitable_table_amz_risk,
    }
    return (mapping.get(table_key) or "").strip()


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
    """将 PG 行 upsert 到飞书；返回统计。"""
    if table_key not in TABLE_SPECS:
        raise ValueError(f"unsupported table_key: {table_key}")

    settings = get_settings()
    app_token = resolve_amz_app_token(settings)
    table_id = resolve_table_id(table_key, settings)
    if not app_token or not table_id:
        return {
            "table_key": table_key,
            "status": "skipped",
            "reason": "feishu amz table not configured",
            "scanned": 0,
            "created": 0,
            "updated": 0,
            "unchanged": 0,
        }

    spec = TABLE_SPECS[table_key]
    bd: str | None
    if biz_date is None:
        bd = None
    elif isinstance(biz_date, date):
        bd = biz_date.isoformat()
    else:
        bd = str(biz_date)[:10] or None

    since: str | None = None
    since_date: str | None = None
    if mode == "incremental" and not bd:
        d0 = datetime.now(timezone.utc) - timedelta(days=max(1, lookback_days))
        since = d0.isoformat()
        since_date = d0.date().isoformat()

    rows = (
        await db.execute(
            text(spec["select"]),
            {
                "biz_date": bd,
                "since": since,
                "since_date": since_date or bd,
                "lim": limit,
            },
        )
    ).mappings().all()

    if dry_run:
        return {
            "table_key": table_key,
            "status": "dry_run",
            "scanned": len(rows),
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

    created = updated = unchanged = failed = 0
    errors: list[str] = []
    mapper = spec["mapper"]
    local_table = spec["local_table"]

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
                    {"tk": table_key, "lid": local_id},
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
                ids = await bitable.batch_create_records(token, app_token, table_id, [fields])
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
                        "table_key": table_key,
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
            logger.exception("sync %s row %s failed", table_key, local_id)

    return {
        "table_key": table_key,
        "status": "success" if failed == 0 else "partial",
        "scanned": len(rows),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "failed": failed,
        "errors": errors[:10],
    }


async def run_feishu_job(db: AsyncSession, job_id: str) -> dict[str, Any]:
    """处理 sync_feishu_job 一行。"""
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
