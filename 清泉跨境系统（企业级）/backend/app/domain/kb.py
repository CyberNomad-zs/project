"""运营知识库：动作/效果校验、历史聚合、剧本草稿/发布、指标回填。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 首期三平台骨架类型（resolve 必填 effect_code）
SKELETON_TYPES: frozenset[tuple[str, str]] = frozenset(
    {
        ("amazon", "link_wow_units_drop"),
        ("tiktok", "low_roi"),
        ("temu", "listing_off"),
    }
)


def is_skeleton_type(platform: str, anomaly_type: str) -> bool:
    return (platform, anomaly_type) in SKELETON_TYPES


async def action_exists(db: AsyncSession, code: str) -> bool:
    row = (
        await db.execute(
            text(
                """
                SELECT 1 FROM ops_action_dict
                WHERE code = :c AND enabled = TRUE
                LIMIT 1
                """
            ),
            {"c": code},
        )
    ).first()
    return row is not None


async def effect_exists(db: AsyncSession, code: str) -> bool:
    row = (
        await db.execute(
            text(
                """
                SELECT 1 FROM ops_effect_dict
                WHERE code = :c AND enabled = TRUE
                LIMIT 1
                """
            ),
            {"c": code},
        )
    ).first()
    return row is not None


async def validate_action_code(db: AsyncSession, action_code: str | None) -> None:
    if action_code is None or action_code == "":
        return
    if not await action_exists(db, action_code):
        raise ValueError(f"未知 action_code: {action_code}")


async def validate_effect_code(db: AsyncSession, effect_code: str | None) -> None:
    if effect_code is None or effect_code == "":
        return
    if not await effect_exists(db, effect_code):
        raise ValueError(f"未知 effect_code: {effect_code}")


async def get_guidance(
    db: AsyncSession, platform: str, anomaly_type: str
) -> dict[str, Any]:
    """A 历史统计 + B 仅 published 剧本。"""
    rows = (
        await db.execute(
            text(
                """
                SELECT tp.action_code, tp.effect_code, COUNT(*)::int AS cnt
                FROM task_progress tp
                JOIN task t ON t.id = tp.task_id
                WHERE t.platform = :platform
                  AND t.anomaly_type = :anomaly_type
                  AND tp.action_code IS NOT NULL
                  AND tp.to_status = 'resolved'
                GROUP BY tp.action_code, tp.effect_code
                ORDER BY tp.action_code, cnt DESC
                """
            ),
            {"platform": platform, "anomaly_type": anomaly_type},
        )
    ).mappings().all()

    by_action: dict[str, dict[str, Any]] = {}
    for r in rows:
        ac = r["action_code"]
        bucket = by_action.setdefault(
            ac, {"action_code": ac, "count": 0, "effects": {}}
        )
        bucket["count"] += r["cnt"]
        ec = r["effect_code"] or "unknown"
        bucket["effects"][ec] = bucket["effects"].get(ec, 0) + r["cnt"]

    history = sorted(by_action.values(), key=lambda x: x["count"], reverse=True)

    playbooks = (
        await db.execute(
            text(
                """
                SELECT id::text, platform, anomaly_type, title, body,
                       action_codes, status, evidence, created_at, updated_at
                FROM kb_playbook
                WHERE platform = :platform
                  AND anomaly_type = :anomaly_type
                  AND status = 'published'
                ORDER BY updated_at DESC
                """
            ),
            {"platform": platform, "anomaly_type": anomaly_type},
        )
    ).mappings().all()

    return {
        "platform": platform,
        "anomaly_type": anomaly_type,
        "history": history,
        "playbooks": [dict(p) for p in playbooks],
    }


async def generate_draft_from_history(
    db: AsyncSession, platform: str, anomaly_type: str
) -> dict[str, Any]:
    guidance = await get_guidance(db, platform, anomaly_type)
    history = guidance["history"]
    top_actions = [h["action_code"] for h in history[:5]]
    if not top_actions:
        body = "暂无结构化历史；请人工补充处置步骤后发布。"
        title = f"{platform}/{anomaly_type} 草稿剧本（空历史）"
    else:
        lines = []
        for h in history[:5]:
            eff = ", ".join(f"{k}:{v}" for k, v in h["effects"].items())
            lines.append(f"- {h['action_code']} ×{h['count']}（{eff}）")
        body = "根据历史结构化闭环自动生成：\n" + "\n".join(lines)
        title = f"{platform}/{anomaly_type} 历史聚合草稿"

    now = datetime.now(timezone.utc)
    pid = str(uuid4())
    evidence = {
        "source": "generate-draft",
        "history_snapshot": history[:10],
        "generated_at": now.isoformat(),
    }
    await db.execute(
        text(
            """
            INSERT INTO kb_playbook (
                id, platform, anomaly_type, title, body, action_codes,
                status, evidence, created_at, updated_at
            ) VALUES (
                :id, :platform, :anomaly_type, :title, :body, :action_codes,
                'draft', CAST(:evidence AS jsonb), :now, :now
            )
            """
        ),
        {
            "id": pid,
            "platform": platform,
            "anomaly_type": anomaly_type,
            "title": title,
            "body": body,
            "action_codes": top_actions,
            "evidence": json.dumps(evidence, ensure_ascii=False),
            "now": now,
        },
    )
    await db.commit()
    return await get_playbook(db, pid)


async def get_playbook(db: AsyncSession, playbook_id: str) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                """
                SELECT id::text, platform, anomaly_type, title, body,
                       action_codes, status, evidence, created_at, updated_at
                FROM kb_playbook WHERE id = :id
                """
            ),
            {"id": playbook_id},
        )
    ).mappings().first()
    if not row:
        raise ValueError("playbook not found")
    return dict(row)


async def set_playbook_status(
    db: AsyncSession, playbook_id: str, status: str
) -> dict[str, Any]:
    if status not in ("draft", "published", "rejected"):
        raise ValueError("非法 status")
    now = datetime.now(timezone.utc)
    result = await db.execute(
        text(
            """
            UPDATE kb_playbook
            SET status = :status, updated_at = :now
            WHERE id = :id
            RETURNING id::text
            """
        ),
        {"status": status, "now": now, "id": playbook_id},
    )
    if not result.first():
        raise ValueError("playbook not found")
    await db.commit()
    return await get_playbook(db, playbook_id)


async def publish_playbook(db: AsyncSession, playbook_id: str) -> dict[str, Any]:
    return await set_playbook_status(db, playbook_id, "published")


async def metric_backfill_for_task(
    db: AsyncSession,
    task_id: str,
    *,
    window_days: int = 7,
) -> dict[str, Any]:
    """
    对 amazon/link_wow_units_drop：有 fact_amz_link_daily 则写 metric_effect；
    无数据返回 skipped，不抛错。
    """
    task = (
        await db.execute(
            text(
                """
                SELECT id::text, platform, anomaly_type, biz_id, resolved_at, status
                FROM task WHERE id = :id
                """
            ),
            {"id": task_id},
        )
    ).mappings().first()
    if not task:
        raise ValueError("task not found")

    if task["platform"] != "amazon" or task["anomaly_type"] != "link_wow_units_drop":
        return {
            "status": "skipped",
            "reason": "only amazon/link_wow_units_drop supported",
            "task_id": task_id,
        }

    anchor: date
    if task["resolved_at"]:
        ra = task["resolved_at"]
        if isinstance(ra, datetime):
            anchor = ra.date()
        else:
            anchor = date.today()
    else:
        anchor = date.today()

    before_start = anchor - timedelta(days=window_days * 2)
    before_end = anchor - timedelta(days=window_days)
    after_start = anchor
    after_end = anchor + timedelta(days=window_days)

    async def _avg_units(start: date, end: date) -> float | None:
        row = (
            await db.execute(
                text(
                    """
                    SELECT AVG(units)::float AS avg_units, COUNT(*)::int AS n
                    FROM fact_amz_link_daily
                    WHERE asin = :asin
                      AND biz_date >= :start
                      AND biz_date < :end
                    """
                ),
                {"asin": task["biz_id"], "start": start, "end": end},
            )
        ).mappings().first()
        if not row or not row["n"]:
            return None
        return float(row["avg_units"] or 0)

    before = await _avg_units(before_start, before_end)
    after = await _avg_units(after_start, after_end + timedelta(days=1))

    if before is None and after is None:
        return {
            "status": "skipped",
            "reason": "no fact_amz_link_daily rows for asin window",
            "task_id": task_id,
            "biz_id": task["biz_id"],
        }

    before_v = before if before is not None else 0.0
    after_v = after if after is not None else 0.0
    delta_ratio = None
    if before_v > 0:
        delta_ratio = (after_v - before_v) / before_v

    payload = {
        "window_days": window_days,
        "metric": "units",
        "before": before_v,
        "after": after_v,
        "delta_ratio": delta_ratio,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "anchor_date": anchor.isoformat(),
    }
    await db.execute(
        text(
            """
            UPDATE task
            SET metric_effect = CAST(:payload AS jsonb), updated_at = :now
            WHERE id = :id
            """
        ),
        {
            "payload": json.dumps(payload, ensure_ascii=False),
            "now": datetime.now(timezone.utc),
            "id": task_id,
        },
    )
    await db.commit()
    return {"status": "ok", "task_id": task_id, "metric_effect": payload}
