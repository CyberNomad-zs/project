#!/usr/bin/env python
"""运营动作记录表合并到异常任务表 — 飞书云端执行脚本。

步骤：
  1. 在「异常任务」表（及所有子表）上新增长 13 个运营动作字段
  2. 删除「运营动作记录」表（及所有子表）

用法:
  python scripts/merge_action_to_task.py                    # 完整执行
  python scripts/merge_action_to_task.py --dry-run          # 仅检测，不修改
  python scripts/merge_action_to_task.py --skip-delete      # 只加字段，不删旧表
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.clients.feishu import FeishuClient, FeishuError
from app.config import get_settings
from app.sync.shops import (
    KIND_TO_MOTHER_NAME,
    ShopTableRegistry,
    child_table_name,
    parse_child_table_name,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("merge_action_to_task")

# 需要在异常任务表新增的运营动作字段: {field_name: type}
NEW_ACTION_FIELDS: list[tuple[str, int]] = [
    ("是否属实", 1),
    ("原因", 1),
    ("判断依据", 1),
    ("采取动作", 1),
    ("执行日期", 5),
    ("执行人", 1),
    ("需审核事项", 1),
    ("复查日期", 5),
    ("动作前数据", 1),
    ("动作后数据", 1),
    ("是否有效", 1),
    ("下一步动作", 1),
    ("闭环状态", 1),
]


def ensure_fields_on_table(
    client: FeishuClient,
    app_token: str,
    table_id: str,
    table_label: str,
    *,
    dry_run: bool = False,
) -> list[str]:
    """在指定表上补充缺失的运营动作字段（幂等）。返回本次新建的字段名列表。"""
    existing = {
        f.get("field_name")
        for f in client.list_fields(app_token, table_id)
        if f.get("field_name")
    }
    created = []
    for field_name, field_type in NEW_ACTION_FIELDS:
        if field_name in existing:
            logger.debug("[%s] 字段已存在: %s", table_label, field_name)
            continue
        if dry_run:
            logger.info("[DRY-RUN] [%s] 将创建字段: %s (type=%d)", table_label, field_name, field_type)
            created.append(field_name)
        else:
            try:
                client.create_field(app_token, table_id, field_name, field_type)
                logger.info("[%s] [OK] 创建字段: %s (type=%d)", table_label, field_name, field_type)
                created.append(field_name)
                time.sleep(0.15)
            except FeishuError as e:
                logger.error("[%s] ❌ 创建字段失败 %s: [%s] %s", table_label, field_name, e.code, e.message)
    return created


def delete_action_tables(
    client: FeishuClient,
    app_token: str,
    *,
    dry_run: bool = False,
) -> list[str]:
    """查找并删除所有「运营动作记录」相关表（母表+子表）。返回已删表名列表。"""
    all_tables = client.list_tables(app_token)
    action_tables = [
        t for t in all_tables
        if ("运营动作记录" in (t.get("name") or ""))
    ]
    deleted = []
    for t in action_tables:
        name = t.get("name", "")
        tid = t.get("table_id", "")
        if dry_run:
            logger.info("[DRY-RUN] 将删除表: %s (%s)", name, tid)
            deleted.append(name)
        else:
            try:
                client._api("DELETE", f"/bitable/v1/apps/{app_token}/tables/{tid}")
                logger.info("[OK] 已删除表: %s (%s)", name, tid)
                deleted.append(name)
                time.sleep(0.3)
            except FeishuError as e:
                logger.error("❌ 删除表失败 %s: [%s] %s", name, e.code, e.message)
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description="合并运营动作记录到异常任务表")
    parser.add_argument("--dry-run", action="store_true", help="只检测不修改")
    parser.add_argument("--skip-delete", action="store_true", help="只加字段，不删旧表")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_feishu:
        logger.error("缺少飞书凭证 (FEISHU_APP_ID / FEISHU_APP_SECRET)")
        return 1

    app_token = settings.feishu_bitable_app_token
    task_table_id = settings.feishu_table_tasks

    if not app_token or not task_table_id:
        logger.error("缺少 FEISHU_BITABLE_APP_TOKEN 或 FEISHU_TABLE_TASKS")
        return 1

    logger.info("模式: %s", "DRY-RUN" if args.dry_run else "执行")
    logger.info("Bitable: %s", app_token)
    logger.info("异常任务母表: %s", task_table_id)

    with FeishuClient(settings) as client:
        # ── 1. 给异常任务表加字段：母表 + 子表 ──────────────────
        logger.info("=== 第 1 步：异常任务表补充运营动作字段 ===")

        total_created = 0

        # 母表
        logger.info("--- 母表 ---")
        created = ensure_fields_on_table(
            client, app_token, task_table_id, "异常任务(母表)",
            dry_run=args.dry_run,
        )
        total_created += len(created)

        # 子表
        registry = ShopTableRegistry.load(settings.shop_tables_path)
        task_children = registry.all_table_ids("tasks")
        if task_children:
            logger.info("--- 子表 (%d 张) ---", len(task_children))
            for shop, tid in task_children:
                created = ensure_fields_on_table(
                    client, app_token, tid, f"异常任务__{shop}",
                    dry_run=args.dry_run,
                )
                total_created += len(created)
        else:
            logger.info("无子表注册表，跳过子表字段补充")

        # 同时删除旧的 动作- 前缀列（如果存在，可选）
        # 注意：飞书 API 不支持删字段，只能手动在 UI 操作

        # ── 2. 删除运营动作记录表 ──────────────────────────────
        if not args.skip_delete:
            logger.info("=== 第 2 步：删除运营动作记录表 ===")
            deleted = delete_action_tables(client, app_token, dry_run=args.dry_run)
        else:
            logger.info("=== 第 2 步：跳过删除（--skip-delete）===")
            deleted = []

    # ── 摘要 ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("执行摘要:")
    print(f"  新增字段: {total_created} 个（跨所有异常任务表）")
    if not args.skip_delete:
        print(f"  删除旧表: {len(deleted)} 张")
    else:
        print(f"  删除旧表: 跳过")
    if args.dry_run:
        print("\n[DRY-RUN] 未实际修改。去掉 --dry-run 执行。")
    else:
        print("\n[DONE] 完成！")
        print("后续手动操作:")
        print("  1. 在飞书 UI 中删除旧字段：关联运营动作、动作-闭环状态等（API 不支持删字段）")
        print("  2. 调整表格视图，把新字段拖到合适位置")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
