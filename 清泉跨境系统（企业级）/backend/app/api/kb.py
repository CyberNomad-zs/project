"""运营知识库 API：guidance / 剧本草稿发布 / 指标回填。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import kb as kb_mod
from app.infra.db import get_db
from app.infra.security import get_current_user

router = APIRouter(prefix="/api/v1/kb", tags=["kb"])


class DraftBody(BaseModel):
    platform: str = Field(min_length=1)
    anomaly_type: str = Field(min_length=1)


class MetricBackfillBody(BaseModel):
    task_id: str = Field(min_length=1)
    window_days: int = Field(default=7, ge=1, le=60)


@router.get("/guidance")
async def guidance(
    platform: str = Query(..., min_length=1),
    anomaly_type: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    return await kb_mod.get_guidance(db, platform, anomaly_type)


@router.post("/playbooks/generate-draft", status_code=201)
async def generate_draft(
    body: DraftBody,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return await kb_mod.generate_draft_from_history(
            db, body.platform, body.anomaly_type
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/playbooks/{playbook_id}/publish")
async def publish(
    playbook_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return await kb_mod.publish_playbook(db, playbook_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/playbooks/{playbook_id}/demote")
async def demote(
    playbook_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """测试/运营：published → draft（反向验证用）。"""
    try:
        return await kb_mod.set_playbook_status(db, playbook_id, "draft")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/metric-backfill")
async def metric_backfill(
    body: MetricBackfillBody,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return await kb_mod.metric_backfill_for_task(
            db, body.task_id, window_days=body.window_days
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
