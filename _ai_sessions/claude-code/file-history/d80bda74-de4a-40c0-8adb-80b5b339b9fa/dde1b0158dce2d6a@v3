from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.clients.sellfox import SellfoxClient, SellfoxError
from app.config import ensure_data_dir, get_app_config, get_settings
from app.store.db import Database
from app.sync.mapping import map_product_analyze_row
from app.sync.writer import write_rows

logger = logging.getLogger(__name__)


def resolve_biz_date(biz_date: str | date | None) -> str:
    if biz_date is None:
        d = date.today() - timedelta(days=1)
        return d.isoformat()
    if isinstance(biz_date, date):
        return biz_date.isoformat()
    return str(biz_date)


def sync_product_analyze_day(
    biz_date: str | date | None = None,
    *,
    db: Database | None = None,
    client: SellfoxClient | None = None,
    save_snapshot: bool | None = None,
) -> dict[str, Any]:
    """Pull productAnalyze V2 for one day and sink to sqlite/feishu."""
    settings = get_settings()
    ensure_data_dir(settings)
    cfg = get_app_config()
    sf_cfg = cfg.get("sellfox") or {}
    sync_cfg = cfg.get("sync") or {}
    owners = cfg.get("owners") or {}

    day = resolve_biz_date(biz_date)
    db = db or Database(settings.db_path)
    own_client = client is None
    client = client or SellfoxClient(
        settings,
        db,
        min_interval=float(sf_cfg.get("min_interval_seconds") or 1.1),
    )

    field_modules = sf_cfg.get("field_modules") or [
        "PRODUCT_INFO",
        "SALE_INFO",
        "SESSION_PERFORMANCE_INFO",
        "PERFORMANCE_INFO",
        "AD_INFO",
        "FBA_INVENTORY_INFO",
        "REVIEW_PERFORMANCE_INFO",
    ]
    page_size = int(sf_cfg.get("page_size") or 100)
    body: dict[str, Any] = {
        "dimType": str(sf_cfg.get("dim_type") or "1"),
        "subType": "0",
        "startDate": day,
        "endDate": day,
        "compareTypeList": [str(x) for x in (sf_cfg.get("compare_type_list") or ["1"])],
        "fieldModules": field_modules,
        "isNewOrMovingOrInStock": str(
            sf_cfg.get("is_new_or_moving_or_in_stock") or "0"
        ),
    }
    shop_ids = sf_cfg.get("shop_id_list") or []
    if shop_ids:
        body["shopIdList"] = [str(x) for x in shop_ids]

    if save_snapshot is None:
        save_snapshot = bool(sync_cfg.get("save_raw_snapshot"))

    run_id = db.start_sync_run(day, meta={"source": "productAnalyze.V2", "body": body})
    pages = 0
    mapped: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []

    try:
        # count pages by reusing iterator; track page breaks via request logging in client
        page_size = min(page_size, 100)
        # manual pagination to know page count
        page = 1
        while True:
            payload = dict(body)
            payload["pageNo"] = str(page)
            payload["pageSize"] = str(page_size)
            data = client.product_analyze_v2_page(payload)
            page_data = data.get("data") or {}
            rows = page_data.get("rows") or []
            pages += 1
            logger.info(
                "productAnalyze V2 date=%s page=%s rows=%s totalSize=%s",
                day,
                page,
                len(rows),
                page_data.get("totalSize"),
            )
            for raw in rows:
                raw_rows.append(raw)
                mapped.append(
                    map_product_analyze_row(
                        raw, biz_date=day, owners=owners
                    )
                )
            total_page = page_data.get("totalPage")
            total_size = int(page_data.get("totalSize") or 0)
            if not rows:
                break
            if total_page is not None and page >= int(total_page):
                break
            if page * page_size >= total_size and total_size > 0:
                break
            if len(rows) < page_size:
                break
            page += 1

        written = write_rows(
            mapped,
            db=db,
            sync_run_id=run_id,
            sink=str(sync_cfg.get("sink") or "sqlite"),
            settings=settings,
        )
        if save_snapshot and raw_rows:
            snap = (
                Path(settings.data_dir)
                / "snapshots"
                / f"product_analyze_{day}_{run_id}.json"
            )
            snap.write_text(
                json.dumps(raw_rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("Saved snapshot %s (%s rows)", snap, len(raw_rows))

        db.finish_sync_run(
            run_id, status="success", total_rows=written, pages=pages
        )
        result = {
            "biz_date": day,
            "run_id": run_id,
            "status": "success",
            "total_rows": written,
            "pages": pages,
        }
        logger.info("Sync done: %s", result)
        return result
    except Exception as e:
        err = str(e)
        logger.exception("Sync failed: %s", err)
        db.finish_sync_run(
            run_id,
            status="failed",
            total_rows=len(mapped),
            pages=pages,
            error=err,
        )
        if isinstance(e, SellfoxError):
            raise
        raise SellfoxError("sync", err) from e
    finally:
        if own_client:
            client.close()
