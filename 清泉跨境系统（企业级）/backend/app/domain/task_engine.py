"""任务引擎：去重键 + 进行中唯一 + 闭环后重建。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain import kb as kb_mod


def build_dedupe_key(platform: str, biz_id: str, anomaly_type: str) -> str:
    return f"{platform}:{biz_id}:{anomaly_type}"


async def enqueue_feishu_sync(db: AsyncSession, task_id: str) -> None:
    await db.execute(
        text(
            """
            INSERT INTO outbox_event (id, event_type, aggregate_type, aggregate_id, payload)
            VALUES (:id, 'feishu.sync', 'task', :task_id, CAST(:payload AS jsonb))
            """
        ),
        {
            "id": str(uuid4()),
            "task_id": task_id,
            "payload": f'{{"table_key":"tasks","local_id":"{task_id}"}}',
        },
    )


async def upsert_task_from_anomaly(
    db: AsyncSession,
    *,
    platform: str,
    shop_id: str | None,
    anomaly_type: str,
    biz_id: str,
    title: str,
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
    owner_user_id: str | None = None,
    severity: str = "warn",
    biz_id_type: str = "unknown",
) -> dict[str, Any]:
    """存在未闭环同键任务则更新进度；否则新建。"""
    settings = get_settings()
    dedupe = build_dedupe_key(platform, biz_id, anomaly_type)
    now = datetime.now(timezone.utc)
    event_id = str(uuid4())

    await db.execute(
        text(
            """
            INSERT INTO anomaly_event (
                id, platform, shop_id, anomaly_type, biz_id, biz_id_type,
                dedupe_key, severity, title, detail, payload, detected_at
            ) VALUES (
                :id, :platform, :shop_id, :anomaly_type, :biz_id, :biz_id_type,
                :dedupe_key, :severity, :title, :detail, CAST(:payload AS jsonb), :detected_at
            )
            """
        ),
        {
            "id": event_id,
            "platform": platform,
            "shop_id": shop_id,
            "anomaly_type": anomaly_type,
            "biz_id": biz_id,
            "biz_id_type": biz_id_type,
            "dedupe_key": dedupe,
            "severity": severity,
            "title": title,
            "detail": detail,
            "payload": __import__("json").dumps(payload or {}, ensure_ascii=False),
            "detected_at": now,
        },
    )

    existing = (
        await db.execute(
            text(
                """
                SELECT id::text, status, progress_note
                FROM task
                WHERE dedupe_key = :dedupe AND status IN ('open', 'in_progress')
                LIMIT 1
                """
            ),
            {"dedupe": dedupe},
        )
    ).mappings().first()

    if existing:
        note = detail or title
        await db.execute(
            text(
                """
                UPDATE task
                SET progress_note = :note,
                    source_event_id = :event_id,
                    updated_at = :now,
                    status = CASE WHEN status = 'open' THEN 'in_progress' ELSE status END
                WHERE id = :id
                """
            ),
            {"note": note, "event_id": event_id, "now": now, "id": existing["id"]},
        )
        await db.execute(
            text(
                """
                INSERT INTO task_progress (id, task_id, note, from_status, to_status)
                VALUES (:id, :task_id, :note, :from_status, 'in_progress')
                """
            ),
            {
                "id": str(uuid4()),
                "task_id": existing["id"],
                "note": note,
                "from_status": existing["status"],
            },
        )
        await db.execute(
            text("UPDATE anomaly_event SET task_id = :task_id WHERE id = :id"),
            {"task_id": existing["id"], "id": event_id},
        )
        await enqueue_feishu_sync(db, existing["id"])
        await db.commit()
        return await get_task(db, existing["id"])

    task_id = str(uuid4())
    due_at = now + timedelta(days=settings.default_task_due_days)
    try:
        await db.execute(
            text(
                """
                INSERT INTO task (
                    id, dedupe_key, status, platform, shop_id, anomaly_type, biz_id,
                    title, owner_user_id, due_at, progress_note, source_event_id,
                    created_at, updated_at
                ) VALUES (
                    :id, :dedupe_key, 'open', :platform, :shop_id, :anomaly_type, :biz_id,
                    :title, :owner_user_id, :due_at, :progress_note, :source_event_id,
                    :now, :now
                )
                """
            ),
            {
                "id": task_id,
                "dedupe_key": dedupe,
                "platform": platform,
                "shop_id": shop_id,
                "anomaly_type": anomaly_type,
                "biz_id": biz_id,
                "title": title,
                "owner_user_id": owner_user_id,
                "due_at": due_at,
                "progress_note": detail,
                "source_event_id": event_id,
                "now": now,
            },
        )
    except IntegrityError:
        await db.rollback()
        # 并发下已有 open 任务，转更新
        return await upsert_task_from_anomaly(
            db,
            platform=platform,
            shop_id=shop_id,
            anomaly_type=anomaly_type,
            biz_id=biz_id,
            title=title,
            detail=detail,
            payload=payload,
            owner_user_id=owner_user_id,
            severity=severity,
            biz_id_type=biz_id_type,
        )

    await db.execute(
        text("UPDATE anomaly_event SET task_id = :task_id WHERE id = :id"),
        {"task_id": task_id, "id": event_id},
    )
    await db.execute(
        text(
            """
            INSERT INTO task_progress (id, task_id, note, from_status, to_status)
            VALUES (:id, :task_id, :note, NULL, 'open')
            """
        ),
        {"id": str(uuid4()), "task_id": task_id, "note": detail or "创建任务"},
    )
    await enqueue_feishu_sync(db, task_id)
    await db.commit()
    return await get_task(db, task_id)


async def get_task(db: AsyncSession, task_id: str) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                """
                SELECT id::text, dedupe_key, status, platform, shop_id::text, anomaly_type,
                       biz_id, title, owner_user_id::text, due_at, progress_note,
                       last_action_code, last_effect_code, metric_effect,
                       created_at, updated_at, resolved_at
                FROM task WHERE id = :id
                """
            ),
            {"id": task_id},
        )
    ).mappings().first()
    if not row:
        raise ValueError("task not found")
    return dict(row)


async def update_progress(
    db: AsyncSession,
    task_id: str,
    note: str,
    status: str | None = None,
    operator_user_id: str | None = None,
    action_code: str | None = None,
) -> dict[str, Any]:
    current = await get_task(db, task_id)
    if current["status"] in ("resolved", "cancelled"):
        raise ValueError("已闭环/取消的任务不能更新进度")
    new_status = status or "in_progress"
    if new_status not in ("open", "in_progress"):
        raise ValueError("进度接口仅允许 open/in_progress")
    await kb_mod.validate_action_code(db, action_code)
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            """
            UPDATE task
            SET progress_note = :note,
                status = :status,
                updated_at = :now,
                last_action_code = COALESCE(:action_code, last_action_code)
            WHERE id = :id
            """
        ),
        {
            "note": note,
            "status": new_status,
            "now": now,
            "id": task_id,
            "action_code": action_code,
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO task_progress (
                id, task_id, note, from_status, to_status, operator_user_id, action_code
            )
            VALUES (
                :id, :task_id, :note, :from_status, :to_status, :operator, :action_code
            )
            """
        ),
        {
            "id": str(uuid4()),
            "task_id": task_id,
            "note": note,
            "from_status": current["status"],
            "to_status": new_status,
            "operator": operator_user_id,
            "action_code": action_code,
        },
    )
    await enqueue_feishu_sync(db, task_id)
    await db.commit()
    return await get_task(db, task_id)


async def resolve_task(
    db: AsyncSession,
    task_id: str,
    note: str | None = None,
    operator_user_id: str | None = None,
    action_code: str | None = None,
    effect_code: str | None = None,
) -> dict[str, Any]:
    current = await get_task(db, task_id)
    if current["status"] == "resolved":
        return current

    platform = current["platform"]
    anomaly_type = current["anomaly_type"]
    skeleton = kb_mod.is_skeleton_type(platform, anomaly_type)

    await kb_mod.validate_action_code(db, action_code)
    await kb_mod.validate_effect_code(db, effect_code)

    if skeleton and not effect_code:
        raise ValueError("骨架异常类型闭环必须填写 effect_code")

    now = datetime.now(timezone.utc)
    final_note = note or current.get("progress_note") or "已闭环"
    final_action = action_code or current.get("last_action_code")

    await db.execute(
        text(
            """
            UPDATE task
            SET status = 'resolved',
                progress_note = :note,
                resolved_at = :now,
                updated_at = :now,
                last_action_code = COALESCE(:action_code, last_action_code),
                last_effect_code = COALESCE(:effect_code, last_effect_code)
            WHERE id = :id
            """
        ),
        {
            "note": final_note,
            "now": now,
            "id": task_id,
            "action_code": action_code,
            "effect_code": effect_code,
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO task_progress (
                id, task_id, note, from_status, to_status, operator_user_id,
                action_code, effect_code
            )
            VALUES (
                :id, :task_id, :note, :from_status, 'resolved', :operator,
                :action_code, :effect_code
            )
            """
        ),
        {
            "id": str(uuid4()),
            "task_id": task_id,
            "note": final_note,
            "from_status": current["status"],
            "operator": operator_user_id,
            "action_code": final_action,
            "effect_code": effect_code,
        },
    )
    await enqueue_feishu_sync(db, task_id)
    await db.commit()
    return await get_task(db, task_id)

