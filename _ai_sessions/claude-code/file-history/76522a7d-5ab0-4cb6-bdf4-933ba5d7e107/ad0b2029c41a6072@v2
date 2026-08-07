"""TK 异常任务 API：列表 / 详情 / 新建 / 进度 / 闭环。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import tk_anomaly
from app.infra.db import get_db
from app.infra.security import get_current_user

router = APIRouter(prefix="/api/v1/tk/anomaly-tasks", tags=["tk-anomaly-tasks"])


class TkAnomalyCreate(BaseModel):
    anomaly_code: str | None = None
    anomaly_type: str | None = None
    summary: str | None = None
    shop_id: str | None = None
    shop_external_id: str | None = None
    shop_name: str | None = None
    product_id: str | None = None
    seller_sku: str | None = None
    product_name: str | None = None
    product_name_cn: str | None = None
    object_ref: str | None = None
    object_type: str | None = None
    priority: str | None = None
    owner_name: str | None = None
    due_at: datetime | None = None
    progress_note: str | None = None
    metric_snapshot: str | None = None
    biz_date: date | None = None
    task_key: str | None = None
    dedupe_key: str | None = None
    source_url: str | None = None
    project_center_task: bool = True


class ProgressBody(BaseModel):
    note: str = Field(min_length=1)
    status: Literal["open", "in_progress"] | None = "in_progress"
    owner_name: str | None = None


class ResolveBody(BaseModel):
    note: str | None = None
    status: Literal["resolved", "cancelled", "ignored"] = "resolved"
    owner_name: str | None = None


@router.get("/types")
async def list_types(
    enabled_only: bool = True,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    items = await tk_anomaly.list_anomaly_types(db, enabled_only=enabled_only)
    return {"items": items}


@router.get("")
async def list_tasks(
    status: str | None = None,
    priority: str | None = None,
    anomaly_code: str | None = None,
    shop_external_id: str | None = None,
    object_type: str | None = None,
    q: str | None = None,
    open_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    return await tk_anomaly.list_anomaly_tasks(
        db,
        status=status,
        priority=priority,
        anomaly_code=anomaly_code,
        shop_external_id=shop_external_id,
        object_type=object_type,
        q=q,
        open_only=open_only,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return await tk_anomaly.get_anomaly_task(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", status_code=201)
async def create_task(
    body: TkAnomalyCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not body.anomaly_code and not body.anomaly_type:
        raise HTTPException(status_code=400, detail="需要 anomaly_code 或 anomaly_type")
    try:
        return await tk_anomaly.create_anomaly_task(
            db,
            anomaly_code=body.anomaly_code,
            anomaly_type=body.anomaly_type,
            summary=body.summary,
            shop_id=body.shop_id,
            shop_external_id=body.shop_external_id,
            shop_name=body.shop_name,
            product_id=body.product_id,
            seller_sku=body.seller_sku,
            product_name=body.product_name,
            product_name_cn=body.product_name_cn,
            object_ref=body.object_ref,
            object_type=body.object_type,
            priority=body.priority,
            owner_name=body.owner_name or user.get("display_name") or user.get("username"),
            owner_user_id=user.get("id"),
            due_at=body.due_at,
            progress_note=body.progress_note,
            metric_snapshot=body.metric_snapshot,
            biz_date=body.biz_date,
            task_key=body.task_key,
            dedupe_key=body.dedupe_key,
            source_url=body.source_url,
            project_center_task=body.project_center_task,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        return await tk_anomaly.update_progress(
            db,
            task_id,
            body.note,
            status=body.status,
            operator_user_id=user.get("id"),
            owner_name=body.owner_name or user.get("display_name") or user.get("username"),
        )
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from exc


@router.post("/{task_id}/resolve")
async def resolve(
    task_id: str,
    body: ResolveBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return await tk_anomaly.resolve_task(
            db,
            task_id,
            note=body.note,
            status=body.status,
            operator_user_id=user.get("id"),
            owner_name=body.owner_name or user.get("display_name") or user.get("username"),
        )
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from exc
