"""CLI：扫描 TK 商品事实 → 库存异常任务。

  python -m app.jobs.tk_product_anomaly_eval
  python -m app.jobs.tk_product_anomaly_eval --dry-run
  python -m app.jobs.tk_product_anomaly_eval --shop-external-id 27501502216807
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from app.domain.tk_product_rules import evaluate_product_anomalies
from app.infra.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("qingquan.tk_product_anomaly_eval")


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as db:
        return await evaluate_product_anomalies(
            db,
            shop_external_id=args.shop_external_id or None,
            project_center_task=not args.no_center_task,
            dry_run=args.dry_run,
            notify=not args.no_notify,
        )


def main() -> None:
    p = argparse.ArgumentParser(description="TK 商品断货/库存不足 → 异常任务")
    p.add_argument("--shop-external-id", help="仅扫该店")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-center-task", action="store_true")
    p.add_argument("--no-notify", action="store_true", help="不推飞书群/私信")
    args = p.parse_args()
    result = asyncio.run(_run(args))
    logger.info(
        "done scanned=%s stockout=%s low=%s upserted=%s notified=%s notify_skipped=%s errors=%s dry_run=%s",
        result.get("scanned"),
        result.get("hit_stockout"),
        result.get("hit_stock_low"),
        result.get("created_or_updated"),
        result.get("notified"),
        result.get("notify_skipped"),
        len(result.get("errors") or []),
        result.get("dry_run"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
