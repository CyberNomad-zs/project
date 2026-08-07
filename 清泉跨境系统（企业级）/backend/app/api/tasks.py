from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import task_engine
from app.infra.db import get_db
from app.infra.security import get_current_user

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    platform: str
    shop_id: str | None = None
    anomaly_type: str
    biz_id: str
    title: str
    owner_user_id: str | None = None
    due_at: datetime | None = None
    progress_note: str | None = None


class ProgressBody(BaseModel):
    note: str = Field(min_length=1)
    status: str | None = None
    action_code: str | None = None


class ResolveBody(BaseModel):
    note: str | None = None
    action_code: str | None = None
    effect_code: str | None = None


@router.get("")
async def list_tasks(
    status: str | None = None,
    platform: str | None = None,
    shop_id: str | None = None,
    owner_user_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    clauses = ["1=1"]
    params: dict[str, Any] = {
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    if status:
        clauses.append("status = :status")
        params["status"] = status
    if platform:
        clauses.append("platform = :platform")
        params["platform"] = platform
    if shop_id:
        clauses.append("shop_id = :shop_id")
        params["shop_id"] = shop_id
    if owner_user_id:
        clauses.append("owner_user_id = :owner_user_id")
        params["owner_user_id"] = owner_user_id

    where = " AND ".join(clauses)
    total = (
        await db.execute(text(f"SELECT COUNT(*) FROM task WHERE {where}"), params)
    ).scalar_one()
    rows = (
        await db.execute(
            text(
                f"""
                SELECT id::text, dedupe_key, status, platform, shop_id::text, anomaly_type,
                       biz_id, title, owner_user_id::text, due_at, progress_note,
                       created_at, updated_at, resolved_at
                FROM task
                WHERE {where}
                ORDER BY updated_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()
    return {"total": total, "items": [dict(r) for r in rows]}


@router.post("", status_code=201)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        task = await task_engine.upsert_task_from_anomaly(
            db,
            platform=body.platform,
            shop_id=body.shop_id,
            anomaly_type=body.anomaly_type,
            biz_id=body.biz_id,
            title=body.title,
            detail=body.progress_note,
            owner_user_id=body.owner_user_id or user["id"],
        )
        return task
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/progress")
async def progress(
    task_id: str,
    body: ProgressBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return await task_engine.update_progress(
            db,
            task_id,
            body.note,
            status=body.status,
            operator_user_id=user["id"],
            action_code=body.action_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/resolve")
async def resolve(
    task_id: str,
    body: ResolveBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return await task_engine.resolve_task(
            db,
            task_id,
            note=body.note,
            operator_user_id=user["id"],
            action_code=body.action_code,
            effect_code=body.effect_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
