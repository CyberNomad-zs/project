#!/usr/bin/env python3
"""给飞书各业务表在「产品名称/产品」后补「中文名称」列（幂等）。

- ASIN每日数据：产品名称 后 → 中文名称
- 异常任务：产品 后 → 中文名称

飞书 OpenAPI 创建字段默认排在表尾；若需严格紧挨产品列，可在 UI 拖动一次。
脚本会尝试用 fields 顺序校验，并提示。

用法：
  python scripts/add_title_cn_fields.py
  python scripts/add_title_cn_fields.py --backfill   # 从本地 raw_json 回填并写回飞书
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.feishu import FeishuClient, FeishuError
from app.config import get_settings
from app.store.db import Database
from app.sync.feishu_schema import (
    T_TEXT,
    row_to_asin_fields,
    task_to_fields,
)
from app.sync.mapping import extract_title_cn
from app.sync.writer import write_asin_to_feishu, write_tasks_to_feishu


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


def _field_order(client: FeishuClient, app: str, table: str) -> list[str]:
    return [f.get("field_name") or "" for f in client.list_fields(app, table)]


def backfill_local(db: Database) -> dict[str, int]:
    """从 asin_daily.raw_json 解析中文名写回 title_cn，并尽量补 anomaly_tasks。"""
    stats = {"asin_updated": 0, "task_updated": 0, "asin_skip": 0}
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT biz_date, marketplace, shop_name, asin, raw_json, title_cn "
            "FROM asin_daily"
        ).fetchall()
        for r in rows:
            raw_s = r["raw_json"]
            if not raw_s:
                stats["asin_skip"] += 1
                continue
            try:
                raw = json.loads(raw_s)
            except json.JSONDecodeError:
                stats["asin_skip"] += 1
                continue
            cn = extract_title_cn(raw)
            if not cn:
                stats["asin_skip"] += 1
                continue
            if r["title_cn"] == cn:
                continue
            conn.execute(
                """
                UPDATE asin_daily SET title_cn=?
                WHERE biz_date=? AND marketplace=? AND shop_name=? AND asin=?
                """,
                (cn, r["biz_date"], r["marketplace"], r["shop_name"], r["asin"]),
            )
            stats["asin_updated"] += 1

        # 任务表：按 shop+asin 取最新 title_cn
        tasks = conn.execute(
            "SELECT task_id, shop_name, asin, product_title_cn FROM anomaly_tasks"
        ).fetchall()
        for t in tasks:
            if t["product_title_cn"]:
                continue
            hit = conn.execute(
                """
                SELECT title_cn FROM asin_daily
                WHERE shop_name=? AND asin=? AND title_cn IS NOT NULL AND title_cn != ''
                ORDER BY biz_date DESC LIMIT 1
                """,
                (t["shop_name"], t["asin"]),
            ).fetchone()
            if not hit:
                continue
            conn.execute(
                "UPDATE anomaly_tasks SET product_title_cn=? WHERE task_id=?",
                (hit["title_cn"], t["task_id"]),
            )
            stats["task_updated"] += 1
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="飞书/本地 中文名称列")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="从本地 raw_json 回填 title_cn 并 upsert 到飞书",
    )
    parser.add_argument(
        "--no-feishu",
        action="store_true",
        help="只处理本地库，不调飞书",
    )
    args = parser.parse_args()
    settings = get_settings()
    db = Database(settings.db_path)

    if not args.no_feishu:
        if not settings.has_feishu or not settings.feishu_bitable_app_token:
            print("ERROR: 飞书凭证未配置（或用 --no-feishu）")
            return 2
        app = settings.feishu_bitable_app_token
        try:
            with FeishuClient(settings) as client:
                specs = [
                    (
                        "ASIN每日数据",
                        settings.feishu_table_asin_daily,
                        "产品名称",
                        "中文名称",
                    ),
                    (
                        "异常任务",
                        settings.feishu_table_tasks,
                        "产品",
                        "中文名称",
                    ),
                ]
                for label, table_id, after, new_name in specs:
                    if not table_id:
                        print(f"skip {label}: table_id 未配置")
                        continue
                    print(f"== {label} ({table_id}) ==")
                    _ensure_text_field(client, app, table_id, new_name)
                    order = _field_order(client, app, table_id)
                    print(f"  field order: {order}")
                    if after in order and new_name in order:
                        if order.index(new_name) != order.index(after) + 1:
                            print(
                                f"  提示: 「{new_name}」当前不在「{after}」右侧，"
                                "请在飞书表头拖到产品名后一列（API 无法指定插入位置）。"
                            )
                        else:
                            print(f"  OK: 「{new_name}」紧挨「{after}」")
        except FeishuError as e:
            print(f"FEISHU ERROR [{e.code}] {e.message}")
            if e.payload:
                print(e.payload)
            return 1

    if args.backfill:
        print("== backfill local ==")
        stats = backfill_local(db)
        print(stats)
        if not args.no_feishu and settings.feishu_table_asin_daily:
            rows = db.list_asin_daily("2026-07-21")
            # 若有多日期，推全部有 title_cn 的行
            with db.connect() as conn:
                dates = [
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT biz_date FROM asin_daily ORDER BY 1"
                    ).fetchall()
                ]
            total = 0
            for d in dates:
                day_rows = db.list_asin_daily(d)
                n = write_asin_to_feishu(day_rows, settings=settings)
                print(f"  feishu asin {d}: {n}")
                total += n
            tasks = db.list_tasks()
            if tasks:
                n_t = write_tasks_to_feishu(tasks, settings=settings)
                print(f"  feishu tasks: {n_t}")
            print(f"feishu push done, asin rows touched≈{total}")
    else:
        print("字段已确保。历史数据请加 --backfill 回填中文名称。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
