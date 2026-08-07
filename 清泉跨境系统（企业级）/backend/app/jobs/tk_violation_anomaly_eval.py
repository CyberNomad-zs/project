"""CLI：扫描新违规 → 异常任务 + 飞书群。"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from app.domain.tk_violation_rules import evaluate_violation_anomalies
from app.infra.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("qingquan.tk_violation_anomaly_eval")


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as db:
        return await evaluate_violation_anomalies(
            db,
            shop_external_id=args.shop_external_id or None,
            project_center_task=not args.no_center_task,
            dry_run=args.dry_run,
            notify=not args.no_notify,
        )


def main() -> None:
    p = argparse.ArgumentParser(description="TK 违规扣分 → 异常任务 + 飞书群")
    p.add_argument("--shop-external-id", help="仅扫该店")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-notify", action="store_true")
    p.add_argument("--no-center-task", action="store_true")
    args = p.parse_args()
    result = asyncio.run(_run(args))
    logger.info(
        "done scanned=%s hit=%s upserted=%s notified=%s errors=%s",
        result.get("scanned"),
        result.get("hit"),
        result.get("created_or_updated"),
        result.get("notified"),
        len(result.get("errors") or []),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
