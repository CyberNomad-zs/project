"""CLI：达人健康分/违规异常评估。"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import date

from app.domain.tk_creator_health_rules import evaluate_creator_health_anomalies
from app.infra.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("qingquan.tk_creator_health_anomaly_eval")


def _parse_date(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as db:
        return await evaluate_creator_health_anomalies(
            db,
            biz_date=_parse_date(args.biz_date),
            shop_external_id=args.shop_external_id or None,
            project_center_task=not args.no_center_task,
            dry_run=args.dry_run,
            notify=not args.no_notify,
        )


def main() -> None:
    p = argparse.ArgumentParser(description="TK 达人健康下降/新违规 → 异常 + 双通道")
    p.add_argument("--biz-date")
    p.add_argument("--shop-external-id")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-notify", action="store_true")
    p.add_argument("--no-center-task", action="store_true")
    args = p.parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
