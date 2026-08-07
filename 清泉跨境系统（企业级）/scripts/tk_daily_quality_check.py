#!/usr/bin/env python3
"""TK 日更后质量门禁：店日连续、ads 新鲜度、content/traffic 空指标、open 异常。

Exit 0 = 通过（或仅 WARN）；exit 1 = 有 FAIL。

Usage:
  python scripts/tk_daily_quality_check.py
  python scripts/tk_daily_quality_check.py --fail-on-warn
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from app.infra.db import engine  # noqa: E402


async def run(*, fail_on_warn: bool) -> int:
    fails: list[str] = []
    warns: list[str] = []
    today = date.today()

    async with engine.connect() as conn:
        shop = (
            await conn.execute(
                text(
                    """
                    SELECT biz_date::text, count(*)::int AS n,
                           count(DISTINCT shop_external_id)::int AS shops
                    FROM tk.fact_tiktok_shop_daily
                    GROUP BY 1 ORDER BY 1 DESC LIMIT 8
                    """
                )
            )
        ).all()
        print("== shop_daily ==")
        for r in shop:
            print(f"  {r[0]} rows={r[1]} shops={r[2]}")
        if not shop:
            fails.append("shop_daily empty")
        else:
            latest = date.fromisoformat(shop[0][0])
            if latest < today - timedelta(days=2):
                warns.append(f"shop_daily stale latest={latest}")
            # 近 3 日历日是否都有 ≥2 店
            need = {today - timedelta(days=i) for i in range(1, 4)}
            have = {date.fromisoformat(r[0]) for r in shop}
            missing = sorted(need - have)
            if missing:
                warns.append(f"shop_daily missing calendar days {missing}")

        ads = (
            await conn.execute(
                text(
                    """
                    SELECT biz_date::text, count(*)::int,
                           round(sum(coalesce(spend,0))::numeric,2)
                    FROM tk.fact_ads_campaign_daily
                    GROUP BY 1 ORDER BY 1 DESC LIMIT 5
                    """
                )
            )
        ).all()
        print("== ads ==")
        for r in ads:
            print(f"  {r[0]} rows={r[1]} spend={r[2]}")
        if not ads:
            warns.append("ads empty")
        else:
            latest = date.fromisoformat(ads[0][0])
            if latest < today - timedelta(days=3):
                warns.append(f"ads stale latest={latest}")

        content = (
            await conn.execute(
                text(
                    """
                    SELECT biz_date::text, count(*)::int,
                           count(*) FILTER (WHERE content_id IS NULL OR content_id='')::int AS bad_id,
                           count(*) FILTER (WHERE impressions IS NULL AND play_count IS NULL)::int AS null_view
                    FROM tk.fact_tiktok_content_daily
                    GROUP BY 1 ORDER BY 1 DESC LIMIT 5
                    """
                )
            )
        ).all()
        print("== content ==")
        for r in content:
            print(f"  {r[0]} n={r[1]} bad_id={r[2]} null_view={r[3]}")
            if r[2] > 0:
                fails.append(f"content {r[0]} missing content_id x{r[2]}")

        traffic = (
            await conn.execute(
                text(
                    """
                    SELECT biz_date::text, count(*)::int AS n,
                           count(*) FILTER (WHERE impressions IS NULL)::int AS null_imp,
                           count(*) FILTER (WHERE cvr IS NULL)::int AS null_cvr,
                           count(*) FILTER (WHERE gmv IS NULL)::int AS null_gmv
                    FROM tk.fact_tiktok_product_traffic_daily
                    GROUP BY 1 ORDER BY 1 DESC LIMIT 5
                    """
                )
            )
        ).all()
        print("== product_traffic ==")
        for r in traffic:
            print(
                f"  {r[0]} n={r[1]} null_imp={r[2]} null_cvr={r[3]} null_gmv={r[4]}"
            )
            if r[1] > 0 and r[2] > r[1] * 0.3:
                fails.append(
                    f"traffic {r[0]} impressions null {r[2]}/{r[1]} (>30%)"
                )
            elif r[2] > 0:
                warns.append(f"traffic {r[0]} impressions null {r[2]}/{r[1]}")

        anom = (
            await conn.execute(
                text(
                    """
                    SELECT anomaly_code, count(*)::int
                    FROM tk.fact_tk_anomaly_task
                    WHERE status IN ('open','in_progress')
                    GROUP BY 1 ORDER BY 2 DESC
                    """
                )
            )
        ).all()
        print("== open anomalies ==")
        total_open = 0
        for r in anom:
            print(f"  {r[0]} {r[1]}")
            total_open += r[1]
        print(f"  TOTAL_OPEN={total_open}")

    print("== result ==")
    for w in warns:
        print(f"WARN {w}")
    for f in fails:
        print(f"FAIL {f}")
    if fails:
        return 1
    if fail_on_warn and warns:
        return 1
    if not fails and not warns:
        print("OK")
    else:
        print("OK_WITH_WARN")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fail-on-warn", action="store_true")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(fail_on_warn=args.fail_on_warn)))


if __name__ == "__main__":
    main()
