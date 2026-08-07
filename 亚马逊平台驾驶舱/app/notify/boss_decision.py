"""「需要老板决策」勾选 → 通知老板。

流程：
  1. 从飞书异常任务母表同步「需要老板决策」到本地（支持负责人手工勾选橙单）
  2. 筛选未关闭且 need_boss 的任务
  3. 按 task_id 去重（已通知过的不再发）
  4. 群机器人卡片 + 可选 @老板 open_id
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings, get_app_config, get_settings
from app.rules.engine import anomaly_type_cn
from app.store.db import Database

logger = logging.getLogger(__name__)

NOTIFY_KIND = "boss_decision"
NEED_BOSS_FIELD = "需要老板决策"
PK_FIELD = "主键"


def _boss_open_ids(cfg: dict[str, Any]) -> list[str]:
    notify = cfg.get("notify") or {}
    raw = notify.get("boss_open_ids")
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x]
    # 兼容单键
    one = notify.get("boss_open_id")
    if one:
        return [str(one).strip()]
    return []


def _tasks_url(cfg: dict[str, Any], settings: Settings) -> str:
    notify = cfg.get("notify") or {}
    base = (notify.get("view_base_url") or "").rstrip("?&")
    if not base and settings.feishu_bitable_app_token:
        base = f"https://dcnkj1up67d5.feishu.cn/base/{settings.feishu_bitable_app_token}"
    if settings.feishu_table_tasks:
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}table={settings.feishu_table_tasks}"
    return base


def _truthy_checkbox(v: Any) -> bool:
    if v is True or v == 1:
        return True
    if v is False or v is None or v == 0:
        return False
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "是", "勾选")
    return bool(v)


def list_notified_boss_task_ids(db: Database) -> set[str]:
    """历史上已成功（或 dry-run 记录）通知过的 task_id。"""
    ids: set[str] = set()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT payload_json FROM notify_log WHERE kind = ?",
            (NOTIFY_KIND,),
        ).fetchall()
    for r in rows:
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        # dry-run 记录不参与去重，避免调试挡住正式推送
        if payload.get("dry_run"):
            continue
        for tid in payload.get("task_ids") or []:
            if tid:
                ids.add(str(tid))
        if payload.get("task_id"):
            ids.add(str(payload["task_id"]))
    return ids


def sync_need_boss_from_feishu(
    db: Database,
    *,
    settings: Settings | None = None,
) -> dict[str, int]:
    """从飞书母表读取「需要老板决策」写回本地 anomaly_tasks.need_boss。"""
    settings = settings or get_settings()
    stats = {"scanned": 0, "updated": 0, "skipped": 0, "errors": 0}
    if not settings.has_feishu or not settings.feishu_bitable_app_token:
        logger.warning("飞书未配置，跳过 need_boss 同步")
        return stats
    table_id = settings.feishu_table_tasks
    if not table_id:
        return stats

    from app.clients.feishu import FeishuClient

    app = settings.feishu_bitable_app_token
    try:
        with FeishuClient(settings) as client:
            for item in client.iter_records(app, table_id, page_size=100):
                stats["scanned"] += 1
                fields = item.get("fields") or {}
                task_id = fields.get(PK_FIELD) or fields.get("异常编号")
                if not task_id:
                    stats["skipped"] += 1
                    continue
                need = 1 if _truthy_checkbox(fields.get(NEED_BOSS_FIELD)) else 0
                with db.connect() as conn:
                    cur = conn.execute(
                        """
                        UPDATE anomaly_tasks
                        SET need_boss = ?, updated_at = datetime('now')
                        WHERE task_id = ?
                          AND COALESCE(need_boss, 0) != ?
                        """,
                        (need, str(task_id), need),
                    )
                    stats["updated"] += int(cur.rowcount or 0)
    except Exception:
        stats["errors"] += 1
        logger.exception("sync_need_boss_from_feishu 失败")
    logger.info("sync_need_boss_from_feishu: %s", stats)
    return stats


def list_boss_decision_tasks(db: Database) -> list[dict[str, Any]]:
    return [
        t
        for t in db.list_tasks()
        if t.get("status") not in ("closed", "resolved")
        and t.get("need_boss")
        and t.get("level") in ("red", "orange")
    ]


def build_boss_decision_card(
    tasks: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
    open_ids: list[str] | None = None,
) -> dict[str, Any]:
    from app.clients.feishu import (
        card_action,
        card_button,
        card_header,
        card_hr,
        card_md,
    )

    settings = settings or get_settings()
    cfg = get_app_config()
    url = _tasks_url(cfg, settings)
    open_ids = open_ids if open_ids is not None else _boss_open_ids(cfg)

    at_line = ""
    if open_ids:
        at_line = "".join(f"<at id={oid}></at>" for oid in open_ids) + "\n"

    ordered = sorted(
        tasks,
        key=lambda x: (
            0 if x.get("level") == "red" else 1,
            x.get("shop_name") or "",
            x.get("asin") or "",
        ),
    )
    red_n = sum(1 for t in ordered if t.get("level") == "red")
    orange_n = sum(1 for t in ordered if t.get("level") == "orange")

    md_lines = [
        f"{at_line}⚠️ **待老板决策** {len(ordered)} 条（🔴{red_n} 🟠{orange_n}）",
        "",
        "> 来源：异常任务表勾选「需要老板决策」",
        "",
    ]
    for t in ordered[:15]:
        icon = "🔴" if t.get("level") == "red" else "🟠"
        cn = t.get("product_title_cn") or t.get("product_title") or ""
        cn_s = f" {cn}" if cn else ""
        summary = t.get("value_summary") or t.get("message") or ""
        sum_s = f" · {summary}" if summary else ""
        md_lines.append(
            f"{icon} `{t.get('task_id')}` {t.get('shop_name')} {t.get('asin')}{cn_s}"
            f" | {anomaly_type_cn(t.get('anomaly_type'))} | {t.get('owner') or '未分配'}{sum_s}"
        )
    if len(ordered) > 15:
        md_lines.append(f"…另有 {len(ordered) - 15} 条，见任务表「06_待老板决策」视图")

    elements = [
        card_md("\n".join(md_lines)),
        card_hr(),
        card_action(card_button("📋 打开任务表", url, primary=True)),
    ]
    return {
        **card_header(f"👔 待老板决策 · {len(ordered)} 条", color="red"),
        "elements": elements,
    }


def notify_boss_decisions(
    db: Database,
    *,
    settings: Settings | None = None,
    dry_run: bool = False,
    sync_from_feishu: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """同步勾选状态并通知老板（默认仅新勾选、未通知过的任务）。"""
    settings = settings or get_settings()
    cfg = get_app_config()
    out: dict[str, Any] = {
        "sync": {},
        "candidates": 0,
        "new": 0,
        "sent": False,
        "dry_run": dry_run,
        "task_ids": [],
    }

    if sync_from_feishu:
        out["sync"] = sync_need_boss_from_feishu(db, settings=settings)

    tasks = list_boss_decision_tasks(db)
    out["candidates"] = len(tasks)
    if not tasks:
        logger.info("无「需要老板决策」未关闭任务")
        return out

    if not force:
        already = list_notified_boss_task_ids(db)
        tasks = [t for t in tasks if str(t.get("task_id") or "") not in already]
    out["new"] = len(tasks)
    out["task_ids"] = [str(t.get("task_id")) for t in tasks if t.get("task_id")]
    if not tasks:
        logger.info("待老板决策任务均已通知过（可用 force 重发）")
        return out

    open_ids = _boss_open_ids(cfg)
    card = build_boss_decision_card(tasks, settings=settings, open_ids=open_ids)
    text_fallback = (
        f"【ASIN健康度】待老板决策 {len(tasks)} 条\n"
        + "\n".join(
            f"- [{t.get('level')}] {t.get('shop_name')} {t.get('asin')} "
            f"{anomaly_type_cn(t.get('anomaly_type'))} {t.get('owner')}"
            for t in tasks[:20]
        )
    )

    payload = {
        "task_ids": out["task_ids"],
        "count": len(tasks),
        "card": card,
        "text": text_fallback,
        "boss_open_ids": open_ids,
        "force": force,
        "dry_run": dry_run,
    }
    # dry-run 也记 log，避免反复 dry-run 刷屏时重复；force 可重发
    if not dry_run or True:
        db.log_notify(NOTIFY_KIND, payload)

    if dry_run:
        logger.info(
            "boss_decision dry-run %s 条:\n%s",
            len(tasks),
            json.dumps(card, ensure_ascii=False, indent=2),
        )
        return out

    webhook = (settings.feishu_bot_webhook or "").strip()
    if not webhook:
        logger.warning("未配置 FEISHU_BOT_WEBHOOK，老板决策通知仅写 notify_log")
        out["logged_only"] = True
        return out

    try:
        from app.clients.feishu import FeishuClient

        with FeishuClient(settings) as client:
            client.send_webhook_card(card, webhook=webhook)
        out["sent"] = True
        logger.info("老板决策通知已发送: %s 条", len(tasks))
    except Exception:
        logger.exception("老板决策通知发送失败")
        out["error"] = True
    return out
