"""CLI：扫描 TK 店日事实 → ① 店铺分析异常任务。

用法（在 backend 目录，已设 PYTHONPATH / DATABASE_URL）：

  python -m app.jobs.tk_shop_anomaly_eval
  python -m app.jobs.tk_shop_anomaly_eval --biz-date 2026-08-03
  python -m app.jobs.tk_shop_anomaly_eval --dry-run
  python -m app.jobs.tk_shop_anomaly_eval --shop-external-id 27501502216807
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import date

from app.domain.tk_shop_rules import evaluate_shop_anomalies
from app.infra.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("qingquan.tk_shop_anomaly_eval")


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s)


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as db:
        return await evaluate_shop_anomalies(
            db,
            biz_date=_parse_date(args.biz_date),
            shop_external_id=args.shop_external_id or None,
            project_center_task=not args.no_center_task,
            dry_run=args.dry_run,
        )


def main() -> None:
    p = argparse.ArgumentParser(description="TK 店铺 GMV/订单环比骤降 → 异常任务")
    p.add_argument("--biz-date", help="业务日 YYYY-MM-DD；默认取店日事实最大日")
    p.add_argument("--shop-external-id", help="仅扫该店 external_shop_id")
    p.add_argument("--dry-run", action="store_true", help="只统计不落库")
    p.add_argument(
        "--no-center-task",
        action="store_true",
        help="不投影 public.task",
    )
    args = p.parse_args()
    result = asyncio.run(_run(args))
    logger.info(
        "done biz_date=%s scanned=%s gmv_drop=%s order_drop=%s upserted=%s errors=%s dry_run=%s",
        result.get("biz_date"),
        result.get("scanned"),
        result.get("hit_gmv_drop"),
        result.get("hit_order_drop"),
        result.get("created_or_updated"),
        len(result.get("errors") or []),
        result.get("dry_run"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
