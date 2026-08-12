"""CLI：扫描 TK 健康日事实 → 健康分下降/过低异常 + 飞书群提醒。

用法（backend 目录）：

  python -m app.jobs.tk_health_anomaly_eval
  python -m app.jobs.tk_health_anomaly_eval --biz-date 2026-08-05
  python -m app.jobs.tk_health_anomaly_eval --dry-run
  python -m app.jobs.tk_health_anomaly_eval --no-notify
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import date

from app.domain.tk_health_rules import evaluate_health_anomalies
from app.infra.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("qingquan.tk_health_anomaly_eval")


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s)


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as db:
        return await evaluate_health_anomalies(
            db,
            biz_date=_parse_date(args.biz_date),
            shop_external_id=args.shop_external_id or None,
            project_center_task=not args.no_center_task,
            dry_run=args.dry_run,
            notify=not args.no_notify,
        )


def main() -> None:
    p = argparse.ArgumentParser(description="TK 健康分下降/过低 → 异常任务 + 飞书群")
    p.add_argument("--biz-date", help="业务日 YYYY-MM-DD；默认取健康事实最大日")
    p.add_argument("--shop-external-id", help="仅扫该店")
    p.add_argument("--dry-run", action="store_true", help="只统计不落库不推送")
    p.add_argument("--no-notify", action="store_true", help="落库但不发飞书")
    p.add_argument("--no-center-task", action="store_true", help="不投影 public.task")
    args = p.parse_args()
    result = asyncio.run(_run(args))
    logger.info(
        "done biz_date=%s scanned=%s drop=%s low=%s upserted=%s notified=%s errors=%s dry_run=%s",
        result.get("biz_date"),
        result.get("scanned"),
        result.get("hit_drop"),
        result.get("hit_low"),
        result.get("created_or_updated"),
        result.get("notified"),
        len(result.get("errors") or []),
        result.get("dry_run"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
