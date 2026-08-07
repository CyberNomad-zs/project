from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_app_config
from app.rules.engine import Anomaly
from app.store.db import Database

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _due_at(level: str, workdays_only: bool = True) -> str:
    """Orange: 1 workday; Red: same calendar day end."""
    now = _utc_now()
    if level == "red":
        due = now.replace(hour=23, minute=59, second=0, microsecond=0)
        return due.strftime("%Y-%m-%dT%H:%M:%SZ")
    # orange default: +1 workday
    d = now
    add = 1
    while add > 0:
        d = d + timedelta(days=1)
        if not workdays_only or d.weekday() < 5:
            add -= 1
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def apply_anomalies_to_tasks(
    anomalies: list[Anomaly],
    *,
    biz_date: str,
    db: Database,
    rules_cfg: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Create/update tasks for orange/red; yellow only counted."""
    cfg = get_app_config()
    reviewers = cfg.get("reviewers") or {}
    default_reviewer = reviewers.get("default")
    workdays_only = True
    if rules_cfg:
        workdays_only = bool(rules_cfg.get("workdays_only", True))

    stats = {"yellow": 0, "orange_new": 0, "orange_updated": 0, "red_new": 0, "red_updated": 0, "skipped": 0}

    for a in anomalies:
        if a.level == "yellow":
            stats["yellow"] += 1
            continue
        if a.level not in ("orange", "red"):
            stats["skipped"] += 1
            continue

        existing = db.get_open_task(a.shop_name, a.asin, a.anomaly_type)
        reviewer = default_reviewer
        if existing:
            streak = int(existing.get("streak") or 1) + 1
            task_id = existing["task_id"]
            # escalate level if worse
            level = a.level
            if existing.get("level") == "red":
                level = "red"
            task = {
                "task_id": task_id,
                "biz_date": biz_date,
                "shop_name": a.shop_name,
                "asin": a.asin,
                "product_title": a.product_title,
                "product_title_cn": a.product_title_cn
                or existing.get("product_title_cn"),
                "anomaly_type": a.anomaly_type,
                "level": level,
                "current_value": a.current_value,
                "baseline_value": a.baseline_value,
                "change_value": a.change_value,
                "current_label": a.current_label,
                "baseline_label": a.baseline_label,
                "change_label": a.change_label,
                "value_summary": a.value_summary,
                "message": a.message,
                "owner": a.owner or existing.get("owner"),
                "reviewer": existing.get("reviewer") or reviewer,
                "status": existing.get("status") or "open",
                "due_at": existing.get("due_at") or _due_at(level, workdays_only),
                "streak": streak,
                "need_boss": 1 if level == "red" else int(existing.get("need_boss") or 0),
                "payload_json": a.to_dict(),
                "created_at": existing.get("created_at"),
            }
            db.upsert_task(task)
            stats[f"{a.level}_updated"] = stats.get(f"{a.level}_updated", 0) + 1
        else:
            task_id = f"T{biz_date.replace('-', '')}-{uuid.uuid4().hex[:10]}"
            task = {
                "task_id": task_id,
                "biz_date": biz_date,
                "shop_name": a.shop_name,
                "asin": a.asin,
                "product_title": a.product_title,
                "product_title_cn": a.product_title_cn,
                "anomaly_type": a.anomaly_type,
                "level": a.level,
                "current_value": a.current_value,
                "baseline_value": a.baseline_value,
                "change_value": a.change_value,
                "current_label": a.current_label,
                "baseline_label": a.baseline_label,
                "change_label": a.change_label,
                "value_summary": a.value_summary,
                "message": a.message,
                "owner": a.owner,
                "reviewer": reviewer,
                "status": "open",
                "due_at": _due_at(a.level, workdays_only),
                "streak": 1,
                "need_boss": 1 if a.level == "red" else 0,
                "payload_json": a.to_dict(),
            }
            db.upsert_task(task)
            stats[f"{a.level}_new"] = stats.get(f"{a.level}_new", 0) + 1

    logger.info("Tasks applied: %s", stats)
    return stats


def _parse_payload(task: dict[str, Any]) -> dict[str, Any]:
    import json

    payload = task.get("payload_json")
    if isinstance(payload, str) and payload:
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _f_num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def enrich_task_metrics_from_anomaly(task: dict[str, Any], a: Anomaly) -> dict[str, Any]:
    """只补语义与指标，保留 status/streak/due_at/reviewer 等。"""
    t = dict(task)
    t["current_value"] = a.current_value
    t["baseline_value"] = a.baseline_value
    t["change_value"] = a.change_value
    t["current_label"] = a.current_label
    t["baseline_label"] = a.baseline_label
    t["change_label"] = a.change_label
    t["value_summary"] = a.value_summary
    t["message"] = a.message
    if a.product_title:
        t["product_title"] = a.product_title
    if a.product_title_cn:
        t["product_title_cn"] = a.product_title_cn
    if a.owner:
        t["owner"] = a.owner
    payload = _parse_payload(t)
    payload.update(a.to_dict())
    t["payload_json"] = payload
    return t


def enrich_open_task_metrics(
    db: Database,
    *,
    biz_date: str,
    rules_cfg: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """安全回填语义字段：匹配规则结果写标签/摘要，不涨 streak、不改状态。"""
    from app.config import get_rules_config
    from app.rules.engine import LEVEL_RANK, evaluate_rows

    stats = {
        "open_tasks": 0,
        "matched_anomaly": 0,
        "from_payload": 0,
        "unchanged": 0,
        "asin_rows": 0,
    }
    tasks = [
        t
        for t in db.list_tasks()
        if t.get("status") not in ("closed", "resolved")
        and t.get("level") in ("red", "orange")
    ]
    stats["open_tasks"] = len(tasks)

    anomaly_map: dict[tuple[str, str, str], Anomaly] = {}
    rows = db.list_asin_daily(biz_date)
    stats["asin_rows"] = len(rows)
    if rows:
        rules = rules_cfg if rules_cfg is not None else get_rules_config()
        for a in evaluate_rows(rows, rules):
            if a.level not in ("orange", "red"):
                continue
            key = (str(a.shop_name or ""), str(a.asin or ""), a.anomaly_type)
            prev = anomaly_map.get(key)
            if prev is None or LEVEL_RANK.get(a.level, 0) >= LEVEL_RANK.get(prev.level, 0):
                anomaly_map[key] = a

    out: list[dict[str, Any]] = []
    for t in tasks:
        key = (
            str(t.get("shop_name") or ""),
            str(t.get("asin") or ""),
            str(t.get("anomaly_type") or ""),
        )
        a = anomaly_map.get(key)
        if a is not None:
            enriched = enrich_task_metrics_from_anomaly(t, a)
            db.upsert_task(enriched)
            out.append(enriched)
            stats["matched_anomaly"] += 1
            continue

        # 无匹配异常：从 payload 补列，再按类型推断标签
        from app.rules.engine import infer_metric_labels

        payload = _parse_payload(t)
        enriched = dict(t)
        changed = False
        for k in (
            "current_label",
            "baseline_label",
            "change_label",
            "value_summary",
            "message",
            "current_value",
            "baseline_value",
            "change_value",
        ):
            if (enriched.get(k) is None or enriched.get(k) == "") and payload.get(
                k
            ) is not None:
                enriched[k] = payload[k]
                changed = True
        if changed:
            stats["from_payload"] += 1

        if not enriched.get("current_label") or not enriched.get("value_summary"):
            inferred = infer_metric_labels(
                enriched.get("anomaly_type"),
                current=_f_num(enriched.get("current_value")),
                baseline=_f_num(enriched.get("baseline_value")),
                change=_f_num(enriched.get("change_value")),
                message=enriched.get("message") or payload.get("message"),
            )
            for k, v in inferred.items():
                if v is not None and (
                    enriched.get(k) is None or enriched.get(k) == ""
                ):
                    enriched[k] = v
                    changed = True
            if not enriched.get("message") and payload.get("message"):
                enriched["message"] = payload["message"]
                changed = True
            # 同步进 payload，便于 task_to_fields 读取
            p2 = dict(payload)
            for k in (
                "current_label",
                "baseline_label",
                "change_label",
                "value_summary",
                "message",
            ):
                if enriched.get(k) is not None:
                    p2[k] = enriched[k]
            enriched["payload_json"] = p2

        if changed:
            db.upsert_task(enriched)
            out.append(enriched)
        else:
            out.append(t)
            stats["unchanged"] += 1

    logger.info("Task metrics enriched: %s", stats)
    return out, stats
