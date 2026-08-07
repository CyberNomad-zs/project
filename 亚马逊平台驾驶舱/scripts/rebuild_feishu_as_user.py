#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在「你本人网页新建」的多维表格上初始化业务表，并切换 .env。

前置（必须你手动完成）：
1. 飞书网页 → 新建多维表格（所有者=你）
2. 分享 → 添加应用 asin-health-monitor → 可编辑
3. 复制链接或 app_token 传给本脚本

用法：
  python scripts/rebuild_feishu_as_user.py --app-token XXXXX
  python scripts/rebuild_feishu_as_user.py --url "https://xxx.feishu.cn/base/XXXXX"
  python scripts/rebuild_feishu_as_user.py --url "..." --sync --date 2026-07-21
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.feishu import FeishuClient, FeishuError
from app.config import get_settings
from app.sync.feishu_schema import TABLE_SPECS

ENV_PATH = ROOT / ".env"


def parse_app_token(url_or_token: str) -> str:
    s = (url_or_token or "").strip().strip('"').strip("'")
    if not s:
        raise ValueError("empty token")
    # full URL
    if "feishu.cn" in s or s.startswith("http"):
        # .../base/TOKEN or .../base/TOKEN?...
        m = re.search(r"/base/([A-Za-z0-9]+)", s)
        if not m:
            raise ValueError(f"无法从 URL 解析 app_token: {s}")
        return m.group(1)
    # bare token
    if re.fullmatch(r"[A-Za-z0-9]+", s):
        return s
    raise ValueError(f"无法识别 app_token: {s}")


def update_env(mapping: dict[str, str]) -> Path:
    """Update or append keys in .env; return backup path."""
    if not ENV_PATH.exists():
        raise FileNotFoundError(f"missing {ENV_PATH}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = ROOT / f".env.bak_切换前_{stamp}"
    shutil.copy2(ENV_PATH, bak)

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    keys_done = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in mapping:
            new_lines.append(f"{key}={mapping[key]}")
            keys_done.add(key)
        else:
            new_lines.append(line)
    for k, v in mapping.items():
        if k not in keys_done:
            new_lines.append(f"{k}={v}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return bak


def main() -> int:
    parser = argparse.ArgumentParser(description="在个人所有的 base 上建业务表并切换 .env")
    parser.add_argument("--app-token", default="", help="多维表格 app_token")
    parser.add_argument("--url", default="", help="完整 base 链接")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="建表后立即同步产品分析+规则任务到新表",
    )
    parser.add_argument("--date", default=None, help="同步业务日 YYYY-MM-DD，默认昨天")
    parser.add_argument(
        "--views",
        action="store_true",
        help="建表后创建推荐视图",
    )
    parser.add_argument(
        "--no-write-env",
        action="store_true",
        help="只建表打印结果，不改 .env",
    )
    args = parser.parse_args()

    raw = args.app_token or args.url
    if not raw:
        print("=" * 60)
        print("必须以「你的个人身份」先在飞书网页新建多维表格，")
        print("再把应用 asin-health-monitor 加成【可编辑】，然后执行：")
        print()
        print('  python scripts/rebuild_feishu_as_user.py --url "你的表格链接"')
        print("  或")
        print("  python scripts/rebuild_feishu_as_user.py --app-token XXXXX")
        print()
        print("详细步骤：docs/以个人身份重建飞书表.md")
        print("=" * 60)
        return 2

    try:
        app_token = parse_app_token(raw)
    except ValueError as e:
        print("ERROR:", e)
        return 2

    settings = get_settings()
    if not settings.has_feishu:
        print("ERROR: .env 缺少 FEISHU_APP_ID / FEISHU_APP_SECRET")
        return 2

    print(f"目标 app_token = {app_token}")
    print("检查应用是否能访问该表（需已分享给应用且可编辑）...")

    try:
        with FeishuClient(settings) as client:
            try:
                meta = client._api("GET", f"/bitable/v1/apps/{app_token}")
            except FeishuError as e:
                print(f"无法读取该表 [{e.code}] {e.message}")
                print()
                print("请确认：")
                print("1. 链接/token 正确")
                print("2. 已在「分享」里把应用 asin-health-monitor 加成【可编辑】")
                print("3. 应用权限 bitable:app 已发布")
                return 1

            app_info = (meta.get("data") or {}).get("app") or {}
            print(f"OK 表名: {app_info.get('name')}")
            tables = client.list_tables(app_token)
            print(f"当前子表: {[t.get('name') for t in tables]}")
            existing = {t.get("name"): t.get("table_id") for t in tables}

            env_map = {
                "FEISHU_BITABLE_APP_TOKEN": app_token,
            }

            for spec in TABLE_SPECS:
                name = spec["name"]
                env_key = spec["env_key"]
                fields = spec["fields"]
                if name in existing and existing[name]:
                    table_id = existing[name]
                    print(f"复用已有表: {name} -> {table_id}")
                else:
                    print(f"创建表: {name} ({len(fields)} 字段)...")
                    data = client.create_table(app_token, name, fields)
                    table_id = (
                        data.get("table_id")
                        or (data.get("table") or {}).get("table_id")
                        or ""
                    )
                    if not table_id:
                        print("  失败:", data)
                        return 1
                    print(f"  OK table_id={table_id}")
                env_map[env_key] = table_id

            if not args.no_write_env:
                bak = update_env(env_map)
                print()
                print(f"已更新 .env（备份: {bak.name}）")
                for k, v in env_map.items():
                    print(f"  {k}={v}")
            else:
                print()
                print("未写 .env，请手动设置：")
                for k, v in env_map.items():
                    print(f"  {k}={v}")

            print()
            print(f"新表链接: https://dcnkj1up67d5.feishu.cn/base/{app_token}")
            print("请在飞书确认：所有者 = 你本人；应用 = 可编辑")

    except FeishuError as e:
        print(f"FEISHU ERROR [{e.code}] {e.message}")
        if e.payload:
            print(e.payload)
        return 1

    # reload settings after env write
    if args.sync or args.views:
        # clear settings cache
        try:
            from app.config import get_settings as gs

            gs.cache_clear()
        except Exception:
            pass

    if args.views:
        print()
        print("创建推荐视图...")
        # setup_feishu_views uses env tables
        from scripts.setup_feishu_views import main as views_main

        # ensure path
        code = views_main()
        if code:
            print("视图创建部分失败，可稍后手动建")

    if args.sync:
        print()
        print("开始同步数据到新表...")
        from app.main import cli
        from click.testing import CliRunner

        # prefer direct calls
        from app.config import ensure_data_dir, get_rules_config, get_settings as gs2
        from app.store.db import Database
        from app.sync.product_analyze import resolve_biz_date, sync_product_analyze_day
        from app.sync.inventory import sync_fba_inventory
        from app.rules.engine import evaluate_rows
        from app.rules.tasks import apply_anomalies_to_tasks
        from app.sync.writer import write_tasks_to_feishu

        settings = gs2()
        ensure_data_dir(settings)
        db = Database(settings.db_path)
        day = resolve_biz_date(args.date)
        print("sync product analyze", day)
        print(sync_product_analyze_day(day, db=db))
        try:
            print(sync_fba_inventory(day, db=db))
        except Exception as e:
            print("fba skip:", e)
        db.clear_open_tasks(day)
        rows = db.list_asin_daily(day)
        rules = get_rules_config()
        an = evaluate_rows(rows, rules)
        print(apply_anomalies_to_tasks(an, biz_date=day, db=db, rules_cfg=rules))
        tasks = [
            t
            for t in db.list_tasks(biz_date=day)
            if t.get("status") not in ("closed", "resolved")
        ]
        print("push tasks", write_tasks_to_feishu(tasks, settings=settings))
        print("同步完成，请打开新表核对 ASIN每日数据 / 异常任务")

    print()
    print("完成。旧表可改名备份或停用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
