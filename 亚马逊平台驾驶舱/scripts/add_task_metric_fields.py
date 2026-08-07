#!/usr/bin/env python3
"""给飞书「异常任务」表补指标语义字段（幂等），并可选回填现有任务。

新增字段：
  - 当前值含义 / 对比值含义 / 变化幅度含义
  - 指标摘要
（「说明」字段已存在则写入规则文案）

回填策略见 app.rules.tasks.enrich_open_task_metrics（不涨 streak）。

用法：
  python scripts/add_task_metric_fields.py
  python scripts/add_task_metric_fields.py --backfill
  python scripts/add_task_metric_fields.py --backfill --date 2026-07-21
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.feishu import FeishuClient, FeishuError
from app.config import get_settings
from app.rules.tasks import enrich_open_task_metrics
from app.store.db import Database
from app.sync.feishu_schema import T_TEXT, task_to_fields
from app.sync.writer import write_tasks_to_feishu


NEW_FIELDS = [
    "当前值含义",
    "对比值含义",
    "变化幅度含义",
    "指标摘要",
]


def _ensure_text_field(
    client: FeishuClient,
    app: str,
    table: str,
    field_name: str,
) -> str | None:
    fields = client.list_fields(app, table)
    by_name = {f.get("field_name"): f for f in fields}
    if field_name in by_name:
        fid = by_name[field_name].get("field_id")
        print(f"  exists: {field_name} -> {fid}")
        return fid
    print(f"  create: {field_name} ...")
    data = client.create_field(app, table, field_name, T_TEXT)
    fid = data.get("field_id") or (data.get("field") or {}).get("field_id")
    print(f"  OK field_id={fid}")
    return fid


def main() -> int:
    parser = argparse.ArgumentParser(description="异常任务指标语义字段")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="安全回填本地任务语义并写回飞书（不涨 streak）",
    )
    parser.add_argument("--date", default="", help="回填业务日 YYYY-MM-DD，默认取任务最新日")
    parser.add_argument(
        "--no-feishu-write",
        action="store_true",
        help="只补飞书列定义 / 本地库，不 upsert 任务行",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_feishu or not settings.feishu_bitable_app_token:
        print("ERROR: 需要 FEISHU_APP_ID/SECRET 与 FEISHU_BITABLE_APP_TOKEN")
        return 2
    table = settings.feishu_table_tasks
    if not table:
        print("ERROR: 未配置 FEISHU_TABLE_TASKS")
        return 2
    app = settings.feishu_bitable_app_token

    try:
        with FeishuClient(settings) as client:
            targets: list[tuple[str, str]] = [("母表-异常任务", table)]
            try:
                from app.sync.shops import ShopTableRegistry

                reg = ShopTableRegistry.load()
                for shop, tid in reg.all_table_ids("tasks"):
                    targets.append((f"子表-{shop}", tid))
            except Exception as e:  # noqa: BLE001
                print(f"  提示: 未加载店铺子表注册表 ({e})")

            for label, tid in targets:
                print(f"== {label} ({tid}) ==")
                for name in NEW_FIELDS:
                    _ensure_text_field(client, app, tid, name)
                _ensure_text_field(client, app, tid, "说明")
    except FeishuError as e:
        print(f"飞书字段失败: {e}")
        return 1

    if not args.backfill:
        print("字段就绪。需要刷新任务内容请加 --backfill")
        return 0

    db = Database(settings.db_path)
    biz_date = args.date.strip()
    if not biz_date:
        with db.connect() as conn:
            row = conn.execute(
                "SELECT biz_date FROM anomaly_tasks ORDER BY biz_date DESC LIMIT 1"
            ).fetchone()
            biz_date = row["biz_date"] if row else ""
    if not biz_date:
        print("无任务可回填")
        return 0

    print(f"回填业务日 {biz_date} ...")
    tasks, stats = enrich_open_task_metrics(db, biz_date=biz_date)
    print("enrich stats:", stats)

    for t in tasks[:5]:
        fields = task_to_fields(t)
        print(
            " sample:",
            t.get("task_id"),
            t.get("anomaly_type"),
            fields.get("指标摘要"),
            "|",
            fields.get("说明"),
        )

    if args.no_feishu_write:
        print("已跳过飞书任务写入（--no-feishu-write）")
        return 0

    n = write_tasks_to_feishu(tasks, settings=settings)
    print(f"飞书写入任务 {n} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
