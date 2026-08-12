#!/usr/bin/env python3
"""Backfill tk.fact_tiktok_product_traffic_daily impressions/cvr/gmv from raw_extra.raw_cells.

Usage (repo root or backend cwd with PYTHONPATH=backend):
  python scripts/tk_backfill_product_traffic_metrics.py
  python scripts/tk_backfill_product_traffic_metrics.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from app.api.ingest import _enrich_traffic_from_raw_cells  # noqa: E402
from app.infra.db import engine  # noqa: E402


async def run(*, dry_run: bool) -> int:
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT id::text,
                           impressions, clicks, ctr, orders_cnt, gmv, cvr, customers,
                           raw_extra
                    FROM tk.fact_tiktok_product_traffic_daily
                    WHERE impressions IS NULL
                       OR cvr IS NULL
                       OR gmv IS NULL
                    ORDER BY biz_date DESC, shop_external_id, product_id
                    """
                )
            )
        ).mappings().all()

        updated = 0
        skipped = 0
        for r in rows:
            extra = r["raw_extra"] or {}
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except json.JSONDecodeError:
                    extra = {}
            cells = extra.get("raw_cells") or extra.get("rawCells")
            headers = extra.get("table_headers") or extra.get("tableHeaders")
            m = _enrich_traffic_from_raw_cells(
                impressions=float(r["impressions"]) if r["impressions"] is not None else None,
                clicks=float(r["clicks"]) if r["clicks"] is not None else None,
                ctr=float(r["ctr"]) if r["ctr"] is not None else None,
                orders_cnt=float(r["orders_cnt"]) if r["orders_cnt"] is not None else None,
                gmv=float(r["gmv"]) if r["gmv"] is not None else None,
                cvr=float(r["cvr"]) if r["cvr"] is not None else None,
                customers=float(r["customers"]) if r["customers"] is not None else None,
                raw_cells=cells,
                table_headers=headers,
            )
            changed = any(
                (m[k] is not None)
                and (
                    r[k] is None
                    or abs(float(r[k]) - float(m[k])) > 1e-9  # type: ignore[arg-type]
                )
                for k in ("impressions", "cvr", "gmv", "clicks", "ctr", "orders_cnt", "customers")
            )
            if not changed:
                skipped += 1
                continue
            if dry_run:
                print(
                    f"dry id={r['id'][:8]}… "
                    f"imp {r['impressions']}→{m['impressions']} "
                    f"cvr {r['cvr']}→{m['cvr']} gmv {r['gmv']}→{m['gmv']}"
                )
                updated += 1
                continue
            await conn.execute(
                text(
                    """
                    UPDATE tk.fact_tiktok_product_traffic_daily
                    SET impressions = COALESCE(:impressions, impressions),
                        clicks = COALESCE(:clicks, clicks),
                        ctr = COALESCE(:ctr, ctr),
                        orders_cnt = COALESCE(:orders_cnt, orders_cnt),
                        gmv = COALESCE(:gmv, gmv),
                        cvr = COALESCE(:cvr, cvr),
                        customers = COALESCE(:customers, customers),
                        updated_at = now()
                    WHERE id = CAST(:id AS uuid)
                    """
                ),
                {
                    "id": r["id"],
                    "impressions": m["impressions"],
                    "clicks": m["clicks"],
                    "ctr": m["ctr"],
                    "orders_cnt": m["orders_cnt"],
                    "gmv": m["gmv"],
                    "cvr": m["cvr"],
                    "customers": m["customers"],
                },
            )
            updated += 1

    print(f"candidates={len(rows)} updated={updated} skipped={skipped} dry_run={dry_run}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(dry_run=args.dry_run)))


if __name__ == "__main__":
    main()
