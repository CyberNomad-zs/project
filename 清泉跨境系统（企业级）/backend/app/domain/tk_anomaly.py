"""TK 异常任务：读写 tk.fact_tk_anomaly_task，可选投影到 public.task。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import task_engine

OPEN_STATUSES = ("open", "in_progress")
CLOSED_STATUSES = ("resolved", "cancelled", "ignored")
ALL_STATUSES = OPEN_STATUSES + CLOSED_STATUSES
PRIORITIES = ("P0", "P1", "P2")
OBJECT_TYPES = ("product", "campaign", "shop", "order", "content", "creator", "other")
LEVEL_BY_PRIORITY = {"P0": "red", "P1": "orange", "P2": "yellow"}
LEVELS = ("red", "orange", "yellow")

_SELECT_COLS = """
    id::text,
    task_key,
    biz_date,
    shop_id::text,
    shop_external_id,
    shop_name,
    product_id,
    seller_sku,
    product_name,
    product_name_cn,
    object_ref,
    object_type,
    anomaly_type,
    anomaly_code,
    priority,
    status,
    owner_name,
    owner_user_id::text,
    due_at,
    progress_note,
    summary,
    metric_snapshot,
    level_code,
    current_value,
    current_value_label,
    compare_value,
    compare_value_label,
    change_magnitude,
    change_magnitude_label,
    streak_count,
    needs_boss_decision,
    description,
    is_confirmed,
    judgment_basis,
    action_taken,
    executor_name,
    executed_at,
    data_before,
    data_after,
    is_effective,
    review_items,
    review_date,
    next_action,
    close_status,
    reviewer_name,
    center_task_id::text,
    anomaly_event_id::text,
    dedupe_key,
    source_url,
    row_status,
    collected_at,
    created_at,
    updated_at,
    resolved_at
"""


def level_from_priority(priority: str | None) -> str:
    pri = (priority or "P1").strip().upper()
    return LEVEL_BY_PRIORITY.get(pri, "orange")


def normalize_level(level: str | None, *, priority: str | None = None) -> str:
    raw = (level or "").strip().lower()
    if raw in LEVELS:
        return raw
    # 兼容中文
    cn = {"红": "red", "红色": "red", "橙": "orange", "橙色": "orange", "黄": "yellow", "黄色": "yellow"}
    if raw in cn:
        return cn[raw]
    return level_from_priority(priority)


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, date):
            d[k] = v.isoformat()
    return d


async def list_anomaly_types(
    db: AsyncSession,
    *,
    enabled_only: bool = True,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    if enabled_only:
        clauses.append("enabled = TRUE")
    rows = (
        await db.execute(
            text(
                f"""
                SELECT code, name_cn, object_type, severity_default, priority_default,
                       description, enabled, sort_order
                FROM tk.dim_tk_anomaly_type
                WHERE {' AND '.join(clauses)}
                ORDER BY sort_order, code
                """
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def get_anomaly_task(db: AsyncSession, task_id: str) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                f"""
                SELECT {_SELECT_COLS}
                FROM tk.fact_tk_anomaly_task
                WHERE id = :id
                """
            ),
            {"id": task_id},
        )
    ).mappings().first()
    if not row:
        raise ValueError("tk anomaly task not found")
    return _row_to_dict(row)


async def list_anomaly_tasks(
    db: AsyncSession,
    *,
    status: str | None = None,
    priority: str | None = None,
    anomaly_code: str | None = None,
    shop_external_id: str | None = None,
    object_type: str | None = None,
    q: str | None = None,
    open_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    clauses = ["1=1"]
    params: dict[str, Any] = {
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    if status:
        clauses.append("status = :status")
        params["status"] = status
    elif open_only:
        clauses.append("status IN ('open', 'in_progress')")
    if priority:
        clauses.append("priority = :priority")
        params["priority"] = priority
    if anomaly_code:
        clauses.append("anomaly_code = :anomaly_code")
        params["anomaly_code"] = anomaly_code
    if shop_external_id:
        clauses.append("shop_external_id = :shop_external_id")
        params["shop_external_id"] = shop_external_id
    if object_type:
        clauses.append("object_type = :object_type")
        params["object_type"] = object_type
    if q:
        clauses.append(
            """
            (
                coalesce(summary, '') ILIKE :q
                OR coalesce(product_name, '') ILIKE :q
                OR coalesce(product_name_cn, '') ILIKE :q
                OR coalesce(product_id, '') ILIKE :q
                OR coalesce(seller_sku, '') ILIKE :q
                OR coalesce(object_ref, '') ILIKE :q
                OR coalesce(shop_name, '') ILIKE :q
                OR coalesce(task_key, '') ILIKE :q
                OR coalesce(anomaly_type, '') ILIKE :q
            )
            """
        )
        params["q"] = f"%{q.strip()}%"

    where = " AND ".join(clauses)
    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM tk.fact_tk_anomaly_task WHERE {where}"),
            params,
        )
    ).scalar_one()

    # 汇总：未过滤分页的开放单数量（同一 where 下按 status）
    status_rows = (
        await db.execute(
            text(
                f"""
                SELECT status, COUNT(*)::int AS cnt
                FROM tk.fact_tk_anomaly_task
                WHERE {where}
                GROUP BY status
                """
            ),
            params,
        )
    ).mappings().all()
    by_status = {r["status"]: r["cnt"] for r in status_rows}

    rows = (
        await db.execute(
            text(
                f"""
                SELECT {_SELECT_COLS}
                FROM tk.fact_tk_anomaly_task
                WHERE {where}
                ORDER BY
                    CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END,
                    CASE status
                        WHEN 'open' THEN 0
                        WHEN 'in_progress' THEN 1
                        ELSE 2
                    END,
                    biz_date DESC,
                    updated_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()

    return {
        "total": total,
        "items": [_row_to_dict(r) for r in rows],
        "summary": {
            "open": by_status.get("open", 0),
            "in_progress": by_status.get("in_progress", 0),
            "resolved": by_status.get("resolved", 0),
            "cancelled": by_status.get("cancelled", 0),
            "ignored": by_status.get("ignored", 0),
        },
    }


async def _lookup_type(db: AsyncSession, anomaly_code: str | None, anomaly_type: str | None) -> tuple[str, str, str, str]:
    """返回 (code, name_cn, object_type, priority_default)。"""
    code = (anomaly_code or "").strip().lower() or None
    name = (anomaly_type or "").strip() or None

    row = None
    if code:
        row = (
            await db.execute(
                text(
                    """
                    SELECT code, name_cn, object_type, priority_default
                    FROM tk.dim_tk_anomaly_type
                    WHERE code = :code
                    LIMIT 1
                    """
                ),
                {"code": code},
            )
        ).mappings().first()
    if not row and name:
        row = (
            await db.execute(
                text(
                    """
                    SELECT code, name_cn, object_type, priority_default
                    FROM tk.dim_tk_anomaly_type
                    WHERE name_cn = :name OR code = :name
                    LIMIT 1
                    """
                ),
                {"name": name},
            )
        ).mappings().first()

    if row:
        return (
            row["code"],
            row["name_cn"],
            row["object_type"],
            row["priority_default"],
        )
    return (
        code or "other",
        name or code or "其它",
        "other",
        "P1",
    )


def _make_task_key(*, biz_date: date, shop: str, obj: str, code: str) -> str:
    day = biz_date.strftime("%Y%m%d")
    safe_obj = (obj or "unknown").replace(" ", "")[:48]
    safe_shop = (shop or "nosshop")[-8:]
    return f"T{day}-{safe_shop}-{safe_obj}-{code}"[:120]


async def create_anomaly_task(
    db: AsyncSession,
    *,
    anomaly_code: str | None = None,
    anomaly_type: str | None = None,
    summary: str | None = None,
    shop_id: str | None = None,
    shop_external_id: str | None = None,
    shop_name: str | None = None,
    product_id: str | None = None,
    seller_sku: str | None = None,
    product_name: str | None = None,
    product_name_cn: str | None = None,
    object_ref: str | None = None,
    object_type: str | None = None,
    priority: str | None = None,
    owner_name: str | None = None,
    owner_user_id: str | None = None,
    due_at: datetime | None = None,
    progress_note: str | None = None,
    metric_snapshot: str | None = None,
    biz_date: date | None = None,
    task_key: str | None = None,
    dedupe_key: str | None = None,
    source_url: str | None = None,
    project_center_task: bool = True,
    # AMZ 对齐：指标明细 + 人维协作
    level_code: str | None = None,
    current_value: float | None = None,
    current_value_label: str | None = None,
    compare_value: float | None = None,
    compare_value_label: str | None = None,
    change_magnitude: float | None = None,
    change_magnitude_label: str | None = None,
    streak_count: int | None = None,
    needs_boss_decision: bool | None = None,
    description: str | None = None,
    next_action: str | None = None,
    reviewer_name: str | None = None,
) -> dict[str, Any]:
    code, name_cn, type_obj, pri_default = await _lookup_type(db, anomaly_code, anomaly_type)
    obj_type = (object_type or type_obj or "other").strip().lower()
    if obj_type not in OBJECT_TYPES:
        obj_type = "other"

    pri = (priority or pri_default or "P1").strip().upper()
    if pri not in PRIORITIES:
        pri = "P1"

    lvl = normalize_level(level_code, priority=pri)
    boss = needs_boss_decision if needs_boss_decision is not None else (pri == "P0")
    streak = int(streak_count) if streak_count is not None and streak_count > 0 else 1
    desc = (description or "").strip() or None

    bd = biz_date or date.today()
    shop_ext = (shop_external_id or "").strip() or None
    shop_nm = (shop_name or "").strip() or None

    if shop_id and (not shop_ext or not shop_nm):
        shop_row = (
            await db.execute(
                text(
                    """
                    SELECT id::text, external_shop_id, name
                    FROM shop WHERE id = :id LIMIT 1
                    """
                ),
                {"id": shop_id},
            )
        ).mappings().first()
        if shop_row:
            shop_id = shop_row["id"]
            shop_ext = shop_ext or shop_row["external_shop_id"]
            shop_nm = shop_nm or shop_row["name"]

    if not shop_id and shop_ext:
        shop_row = (
            await db.execute(
                text(
                    """
                    SELECT id::text, external_shop_id, name
                    FROM shop
                    WHERE external_shop_id = :eid AND platform = 'tiktok'
                    LIMIT 1
                    """
                ),
                {"eid": shop_ext},
            )
        ).mappings().first()
        if shop_row:
            shop_id = shop_row["id"]
            shop_nm = shop_nm or shop_row["name"]

    obj_ref = (
        (object_ref or "").strip()
        or (product_id or "").strip()
        or (seller_sku or "").strip()
        or (shop_ext or "").strip()
        or None
    )
    if not obj_ref:
        raise ValueError("需要 object_ref / product_id / seller_sku / shop_external_id 之一")

    tk = (task_key or "").strip() or _make_task_key(
        biz_date=bd,
        shop=str(shop_ext or ""),
        obj=str(obj_ref),
        code=code,
    )
    dk = (dedupe_key or "").strip() or f"tiktok:{obj_ref}:{code}"
    title = (summary or "").strip() or name_cn
    if not desc:
        # 说明 = 摘要 + 明细（对齐 AMZ「说明」）
        parts = [title]
        if progress_note:
            parts.append(str(progress_note))
        if metric_snapshot:
            parts.append(str(metric_snapshot))
        desc = " | ".join(dict.fromkeys(p for p in parts if p))

    # 未闭环去重
    existing = (
        await db.execute(
            text(
                """
                SELECT id::text, streak_count
                FROM tk.fact_tk_anomaly_task
                WHERE dedupe_key = :dk AND status IN ('open', 'in_progress')
                LIMIT 1
                """
            ),
            {"dk": dk},
        )
    ).mappings().first()
    if existing:
        # 同对象再命中：连续次数 +1，刷新指标
        next_streak = int(existing.get("streak_count") or 1) + 1
        await db.execute(
            text(
                """
                UPDATE tk.fact_tk_anomaly_task
                SET summary = :summary,
                    progress_note = COALESCE(:note, progress_note),
                    metric_snapshot = COALESCE(:metric, metric_snapshot),
                    priority = :priority,
                    level_code = :level_code,
                    current_value = COALESCE(:current_value, current_value),
                    current_value_label = COALESCE(:current_value_label, current_value_label),
                    compare_value = COALESCE(:compare_value, compare_value),
                    compare_value_label = COALESCE(:compare_value_label, compare_value_label),
                    change_magnitude = COALESCE(:change_magnitude, change_magnitude),
                    change_magnitude_label = COALESCE(:change_magnitude_label, change_magnitude_label),
                    streak_count = :streak_count,
                    needs_boss_decision = :needs_boss_decision,
                    description = COALESCE(:description, description),
                    next_action = COALESCE(:next_action, next_action),
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {
                "id": existing["id"],
                "summary": title,
                "note": progress_note,
                "metric": metric_snapshot,
                "priority": pri,
                "level_code": lvl,
                "current_value": current_value,
                "current_value_label": (current_value_label or "").strip() or None,
                "compare_value": compare_value,
                "compare_value_label": (compare_value_label or "").strip() or None,
                "change_magnitude": change_magnitude,
                "change_magnitude_label": (change_magnitude_label or "").strip() or None,
                "streak_count": next_streak,
                "needs_boss_decision": boss or pri == "P0",
                "description": desc,
                "next_action": (next_action or "").strip() or None,
            },
        )
        await db.commit()
        return await get_anomaly_task(db, existing["id"])

    center_task_id = None
    if project_center_task:
        center = await task_engine.upsert_task_from_anomaly(
            db,
            platform="tiktok",
            shop_id=shop_id,
            anomaly_type=code,
            biz_id=str(obj_ref),
            title=title,
            detail=progress_note or metric_snapshot,
            payload={
                "source": "tk.fact_tk_anomaly_task",
                "task_key": tk,
                "anomaly_code": code,
                "anomaly_type": name_cn,
                "level_code": lvl,
            },
            owner_user_id=owner_user_id,
            severity="high" if pri == "P0" else "warn",
            biz_id_type=obj_type,
        )
        center_task_id = center["id"]

    new_id = str(uuid4())
    await db.execute(
        text(
            """
            INSERT INTO tk.fact_tk_anomaly_task (
                id, task_key, biz_date, shop_id, shop_external_id, shop_name,
                product_id, seller_sku, product_name, product_name_cn,
                object_ref, object_type, anomaly_type, anomaly_code,
                priority, status, owner_name, owner_user_id, due_at, progress_note,
                summary, metric_snapshot,
                level_code, current_value, current_value_label,
                compare_value, compare_value_label,
                change_magnitude, change_magnitude_label,
                streak_count, needs_boss_decision, description,
                next_action, reviewer_name,
                center_task_id, dedupe_key,
                source_url, row_status, created_at, updated_at
            ) VALUES (
                :id, :task_key, :biz_date, CAST(:shop_id AS uuid), :shop_external_id, :shop_name,
                :product_id, :seller_sku, :product_name, :product_name_cn,
                :object_ref, :object_type, :anomaly_type, :anomaly_code,
                :priority, 'open', :owner_name, CAST(:owner_user_id AS uuid), :due_at, :progress_note,
                :summary, :metric_snapshot,
                :level_code, :current_value, :current_value_label,
                :compare_value, :compare_value_label,
                :change_magnitude, :change_magnitude_label,
                :streak_count, :needs_boss_decision, :description,
                :next_action, :reviewer_name,
                CAST(:center_task_id AS uuid), :dedupe_key,
                :source_url, 'success', now(), now()
            )
            """
        ),
        {
            "id": new_id,
            "task_key": tk,
            "biz_date": bd,
            "shop_id": shop_id,
            "shop_external_id": shop_ext,
            "shop_name": shop_nm,
            "product_id": (product_id or "").strip() or None,
            "seller_sku": (seller_sku or "").strip() or None,
            "product_name": (product_name or "").strip() or None,
            "product_name_cn": (product_name_cn or "").strip() or None,
            "object_ref": obj_ref,
            "object_type": obj_type,
            "anomaly_type": name_cn,
            "anomaly_code": code,
            "priority": pri,
            "owner_name": (owner_name or "").strip() or None,
            "owner_user_id": owner_user_id,
            "due_at": due_at,
            "progress_note": progress_note,
            "summary": title,
            "metric_snapshot": metric_snapshot,
            "level_code": lvl,
            "current_value": current_value,
            "current_value_label": (current_value_label or "").strip() or None,
            "compare_value": compare_value,
            "compare_value_label": (compare_value_label or "").strip() or None,
            "change_magnitude": change_magnitude,
            "change_magnitude_label": (change_magnitude_label or "").strip() or None,
            "streak_count": streak,
            "needs_boss_decision": bool(boss),
            "description": desc,
            "next_action": (next_action or "").strip() or None,
            "reviewer_name": (reviewer_name or "").strip() or None,
            "center_task_id": center_task_id,
            "dedupe_key": dk,
            "source_url": source_url,
        },
    )
    await db.commit()
    return await get_anomaly_task(db, new_id)


async def update_progress(
    db: AsyncSession,
    task_id: str,
    note: str,
    *,
    status: str | None = None,
    operator_user_id: str | None = None,
    owner_name: str | None = None,
) -> dict[str, Any]:
    current = await get_anomaly_task(db, task_id)
    if current["status"] in CLOSED_STATUSES:
        raise ValueError("已闭环/取消/忽略的任务不能更新进度")

    new_status = status or "in_progress"
    if new_status not in OPEN_STATUSES:
        raise ValueError("进度接口仅允许 open/in_progress")

    await db.execute(
        text(
            """
            UPDATE tk.fact_tk_anomaly_task
            SET progress_note = :note,
                status = :status,
                owner_name = COALESCE(:owner_name, owner_name),
                owner_user_id = COALESCE(CAST(:owner_user_id AS uuid), owner_user_id),
                updated_at = now()
            WHERE id = :id
            """
        ),
        {
            "id": task_id,
            "note": note,
            "status": new_status,
            "owner_name": owner_name,
            "owner_user_id": operator_user_id,
        },
    )

    # 镜像中心任务
    center_id = current.get("center_task_id")
    if center_id:
        try:
            await task_engine.update_progress(
                db,
                center_id,
                note,
                status=new_status,
                operator_user_id=operator_user_id,
            )
        except ValueError:
            # 中心任务已关也不挡 TK 表更新
            await db.commit()
    else:
        await db.commit()

    return await get_anomaly_task(db, task_id)


async def resolve_task(
    db: AsyncSession,
    task_id: str,
    *,
    note: str | None = None,
    status: str = "resolved",
    operator_user_id: str | None = None,
    owner_name: str | None = None,
) -> dict[str, Any]:
    if status not in CLOSED_STATUSES:
        raise ValueError("闭环接口仅允许 resolved/cancelled/ignored")

    current = await get_anomaly_task(db, task_id)
    if current["status"] in CLOSED_STATUSES:
        return current

    final_note = note or current.get("progress_note") or (
        "已忽略" if status == "ignored" else "已取消" if status == "cancelled" else "已闭环"
    )
    now = datetime.now(timezone.utc)

    await db.execute(
        text(
            """
            UPDATE tk.fact_tk_anomaly_task
            SET status = :status,
                progress_note = :note,
                owner_name = COALESCE(:owner_name, owner_name),
                owner_user_id = COALESCE(CAST(:owner_user_id AS uuid), owner_user_id),
                resolved_at = :now,
                updated_at = :now
            WHERE id = :id
            """
        ),
        {
            "id": task_id,
            "status": status,
            "note": final_note,
            "owner_name": owner_name,
            "owner_user_id": operator_user_id,
            "now": now,
        },
    )

    center_id = current.get("center_task_id")
    if center_id and status == "resolved":
        try:
            await task_engine.resolve_task(
                db,
                center_id,
                note=final_note,
                operator_user_id=operator_user_id,
            )
        except ValueError:
            await db.commit()
    elif center_id and status in ("cancelled", "ignored"):
        # 中心任务没有 ignored；映射为 cancelled
        await db.execute(
            text(
                """
                UPDATE task
                SET status = 'cancelled',
                    progress_note = :note,
                    updated_at = :now,
                    resolved_at = :now
                WHERE id = :id AND status IN ('open', 'in_progress')
                """
            ),
            {"id": center_id, "note": final_note, "now": now},
        )
        await db.commit()
    else:
        await db.commit()

    return await get_anomaly_task(db, task_id)
