#!/usr/bin/env python
"""⚠️ 已废弃 — 运营动作记录表已合并到异常任务表。

此脚本曾在异常任务表末尾追加运营动作信息列，并建立与运营动作记录表的关联。
合并后所有动作字段直接存在于任务表中，不再需要跨表关联。

如需在新版任务表上补充字段，请使用 migrate_feishu_fields.py 或直接更新 feishu_schema.py。
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

from app.clients.feishu import FeishuClient
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("setup_action_lookup")

# ── 配置 ────────────────────────────────────────────────────────
LINK_FIELD_NAME = "关联运营动作"      # 单向关联字段（type=18）

# 从运营动作记录表复制到异常任务表的字段: { 任务表列名: 动作表列名 }
ACTION_COPY_COLUMNS: dict[str, str] = {
    "动作-闭环状态": "闭环状态",
    "动作-原因": "原因",
    "动作-采取动作": "采取动作",
    "动作-是否有效": "是否有效",
    "动作-复查日期": "复查日期",
}


def setup(
    client: FeishuClient,
    app_token: str,
    task_table_id: str,
    action_table_id: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "link_field_created": False,
        "text_columns_created": [],
        "links_backfilled": 0,
        "action_data_backfilled": 0,
    }

    # ── 1. 获取现有字段 ──────────────────────────────────────────
    logger.info("=== 获取异常任务表字段 ===")
    task_fields = client.list_fields(app_token, task_table_id)
    task_field_names = {f.get("field_name") for f in task_fields}

    logger.info("=== 获取运营动作记录表字段 ===")
    action_fields = client.list_fields(app_token, action_table_id)
    action_field_names = {f.get("field_name") for f in action_fields}

    if "异常编号" not in task_field_names:
        logger.error("异常任务表缺少「异常编号」字段！")
        return result
    if "关联异常编号" not in action_field_names:
        logger.error("运营动作记录表缺少「关联异常编号」字段！")
        return result

    # ── 2. 创建单向关联字段（type=18） ──────────────────────────
    if LINK_FIELD_NAME in task_field_names:
        for f in task_fields:
            if f["field_name"] == LINK_FIELD_NAME:
                logger.info("关联字段 [%s] 已存在 (id=%s type=%s)", LINK_FIELD_NAME, f.get("field_id"), f.get("type"))
                break
        result["link_field_created"] = False
    else:
        if dry_run:
            logger.info("[DRY-RUN] 将创建单向关联字段 [%s]", LINK_FIELD_NAME)
            result["link_field_created"] = True
        else:
            resp = client.create_field(
                app_token, task_table_id, LINK_FIELD_NAME, 18,
                property_={"table_id": action_table_id},
            )
            fid = resp.get("field", {}).get("field_id") or resp.get("field_id")
            logger.info("✅ 创建单向关联字段 [%s] (id=%s)", LINK_FIELD_NAME, fid)
            result["link_field_created"] = True
            task_field_names.add(LINK_FIELD_NAME)
            time.sleep(0.3)

    # ── 3. 创建动作信息文本列 ───────────────────────────────────
    for col_name in ACTION_COPY_COLUMNS:
        if col_name in task_field_names:
            logger.info("字段 [%s] 已存在，跳过", col_name)
        else:
            if dry_run:
                logger.info("[DRY-RUN] 将创建文本字段 [%s]", col_name)
                result["text_columns_created"].append(col_name)
            else:
                client.create_field(app_token, task_table_id, col_name, 1)
                logger.info("✅ 创建文本字段 [%s]", col_name)
                result["text_columns_created"].append(col_name)
                task_field_names.add(col_name)
                time.sleep(0.15)

    # ── 4. 回填关联关系 ─────────────────────────────────────────
    logger.info("=== 回填关联关系 ===")

    # 读取运营动作表
    action_info: dict[str, dict[str, Any]] = {}
    for item in client.iter_records(app_token, action_table_id, page_size=100):
        rid = item.get("record_id")
        fields = item.get("fields") or {}
        key = str(fields.get("关联异常编号") or "").strip()
        if key:
            action_info[key] = {"record_id": rid, "fields": fields}
    logger.info("运营动作记录: %d 条", len(action_info))

    # 读取异常任务表，找出需要回填的记录
    to_link: list[dict[str, Any]] = []
    to_update_action: list[dict[str, Any]] = []

    for item in client.iter_records(app_token, task_table_id, page_size=100):
        rid = item.get("record_id")
        fields = item.get("fields") or {}
        task_no = str(fields.get("异常编号") or "").strip()
        if not task_no or not rid:
            continue
        action = action_info.get(task_no)
        if not action:
            continue

        # 检查是否需要回填关联
        link_val = fields.get(LINK_FIELD_NAME)
        has_real_link = False
        if link_val and isinstance(link_val, list):
            for lv in link_val:
                if isinstance(lv, dict) and lv.get("record_ids"):
                    has_real_link = True
                    break
        if not has_real_link:
            to_link.append({
                "record_id": rid,
                "fields": {LINK_FIELD_NAME: [action["record_id"]]},
            })

        # 检查是否需要回填动作文本列
        action_updates = {}
        for task_col, action_col in ACTION_COPY_COLUMNS.items():
            action_val = action["fields"].get(action_col)
            if action_val is not None and str(action_val).strip():
                existing = fields.get(task_col)
                if not existing or str(existing).strip() != str(action_val).strip():
                    action_updates[task_col] = action_val
        if action_updates:
            to_update_action.append({"record_id": rid, "fields": action_updates})

    result["links_backfilled"] = len(to_link)
    result["action_data_backfilled"] = len(to_update_action)

    if to_link:
        if dry_run:
            logger.info("[DRY-RUN] 将回填 %d 条关联", len(to_link))
        else:
            for i in range(0, len(to_link), 100):
                chunk = to_link[i : i + 100]
                client.bitable_batch_update(app_token, task_table_id, chunk)
                logger.info("  关联回填 %d/%d", min(i + 100, len(to_link)), len(to_link))
                time.sleep(0.2)
            logger.info("✅ 关联回填完成: %d 条", len(to_link))
    else:
        logger.info("无需回填（所有关联已就绪）")

    if to_update_action:
        if dry_run:
            logger.info("[DRY-RUN] 将更新 %d 条动作数据", len(to_update_action))
        else:
            for i in range(0, len(to_update_action), 100):
                chunk = to_update_action[i : i + 100]
                client.bitable_batch_update(app_token, task_table_id, chunk)
                logger.info("  动作数据 %d/%d", min(i + 100, len(to_update_action)), len(to_update_action))
                time.sleep(0.2)
            logger.info("✅ 动作数据回填完成: %d 条", len(to_update_action))
    else:
        logger.info("无需回填动作数据")

    return result


def main() -> None:
    print("⚠️  此脚本已废弃。运营动作记录表已合并到异常任务表。")
    print("   所有动作字段（原因、采取动作、闭环状态等）现在直接存在于任务表中。")
    print("   无需再运行此脚本建立跨表关联。")


if __name__ == "__main__":
    main()
