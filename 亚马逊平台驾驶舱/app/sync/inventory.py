from __future__ import annotations

import logging
from typing import Any

from app.clients.sellfox import SellfoxClient, SellfoxError
from app.config import get_app_config, get_settings
from app.store.db import Database
from app.sync.mapping import resolve_owner
from app.sync.product_analyze import resolve_biz_date

logger = logging.getLogger(__name__)


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _first(v: Any) -> Any:
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _first_str(v: Any) -> str:
    x = _first(v)
    return "" if x is None else str(x)


def _pick(raw: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in raw and raw[k] is not None and raw[k] != "":
            return raw[k]
    return None


def map_fba_inventory_row(
    raw: dict[str, Any],
    *,
    owners: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Map Sellfox FBA inventory page row → partial asin_daily inventory fields."""
    asin = _first_str(
        _pick(raw, "asin", "ASIN", "asinList") or raw.get("asin")
    )
    if not asin and isinstance(raw.get("asinList"), list):
        asin = _first_str(raw.get("asinList"))
    if not asin:
        return None

    shop_name = str(
        _pick(raw, "shopName", "shop_name")
        or _first_str(raw.get("shopNameList"))
        or ""
    )
    shop_id = str(
        _pick(raw, "shopId", "shop_id") or _first_str(raw.get("shopIdList")) or ""
    )
    marketplace = str(
        _pick(raw, "marketplaceName", "marketplace", "siteName")
        or _first_str(raw.get("marketplaceNameList"))
        or ""
    )

    # 常见字段名兼容
    available = _num(
        _pick(
            raw,
            "available",
            "fulfillableQuantity",
            "afnFulfillableQuantity",
            "fbaAvailable",
            "quantity",
        )
    )
    in_transit = _num(
        _pick(
            raw,
            "inTransit",
            "inboundShippedQuantity",
            "afnInboundShippedQuantity",
            "inboundWorkingQuantity",
            "reservedQuantity",
        )
    )
    available_days = _num(
        _pick(raw, "availableDays", "fbaAvailableDays", "sellableDays", "daysOfSupply")
    )
    inv_age = _num(
        _pick(
            raw,
            "invAge365PlusDays",
            "invAge365Plus",
            "afnResearchingQuantity",
            "age365",
        )
    )
    # 部分接口拆库龄
    if inv_age is None:
        inv_age = _num(_pick(raw, "invAge365PlusDays"))

    return {
        "shop_name": shop_name,
        "shop_id": shop_id,
        "marketplace": marketplace,
        "asin": asin,
        "msku": _first_str(_pick(raw, "msku", "sellerSku", "mskuList")) or None,
        "sku": _first_str(_pick(raw, "sku", "skuList")) or None,
        "available": available,
        "in_transit": in_transit,
        "available_days": available_days,
        "inv_age_365_plus": inv_age,
        "owner": resolve_owner(shop_name, owners) if owners else None,
        "raw": raw,
    }


def sync_fba_inventory(
    biz_date: str | None = None,
    *,
    db: Database | None = None,
    client: SellfoxClient | None = None,
) -> dict[str, Any]:
    """拉取 FBA 库存明细，按 shop+asin 合并进当日 asin_daily 库存字段。"""
    settings = get_settings()
    cfg = get_app_config()
    sf_cfg = cfg.get("sellfox") or {}
    owners = cfg.get("owners") or {}
    day = resolve_biz_date(biz_date)
    db = db or Database(settings.db_path)
    own = client is None
    client = client or SellfoxClient(
        settings,
        db,
        min_interval=float(sf_cfg.get("min_interval_seconds") or 1.1),
    )
    page_size = min(int(sf_cfg.get("page_size") or 100), 100)

    body: dict[str, Any] = {}
    shop_ids = sf_cfg.get("shop_id_list") or []
    if shop_ids:
        body["shopIdList"] = [str(x) for x in shop_ids]

    pages = 0
    mapped: list[dict[str, Any]] = []
    try:
        page = 1
        while True:
            payload = dict(body)
            payload["pageNo"] = str(page)
            payload["pageSize"] = str(page_size)
            data = client.request("/api/inventoryManage/fba/pageList.json", payload)
            page_data = data.get("data") or {}
            rows = page_data.get("rows") or page_data.get("list") or []
            pages += 1
            logger.info(
                "FBA inventory page=%s rows=%s totalSize=%s",
                page,
                len(rows),
                page_data.get("totalSize") or page_data.get("total"),
            )
            for raw in rows:
                m = map_fba_inventory_row(raw, owners=owners)
                if m:
                    mapped.append(m)
            total_page = page_data.get("totalPage")
            total_size = int(page_data.get("totalSize") or page_data.get("total") or 0)
            if not rows:
                break
            if total_page is not None and page >= int(total_page):
                break
            if total_size and page * page_size >= total_size:
                break
            if len(rows) < page_size:
                break
            page += 1

        updated = db.merge_inventory_into_asin_daily(day, mapped)
        result = {
            "biz_date": day,
            "status": "success",
            "fba_rows": len(mapped),
            "asin_daily_updated": updated,
            "pages": pages,
        }
        logger.info("FBA inventory merge done: %s", result)
        return result
    except SellfoxError:
        raise
    except Exception as e:
        logger.exception("FBA inventory sync failed")
        raise SellfoxError("fba_sync", str(e)) from e
    finally:
        if own:
            client.close()
