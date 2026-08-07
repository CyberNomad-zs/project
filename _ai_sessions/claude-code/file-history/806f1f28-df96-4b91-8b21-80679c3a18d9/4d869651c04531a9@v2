from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.infra.security import get_current_user

router = APIRouter(prefix="/api/v1/shops", tags=["shops"])


class ShopCreate(BaseModel):
    platform: str
    external_shop_id: str
    name: str
    primary_owner_user_id: str | None = None
    timezone: str = "Asia/Shanghai"
    currency: str = "GBP"
    meta: dict[str, Any] = Field(default_factory=dict)


class ShopUpdate(BaseModel):
    name: str | None = None
    primary_owner_user_id: str | None = None
    status: str | None = None
    meta: dict[str, Any] | None = None


@router.get("")
async def list_shops(
    platform: str | None = None,
    status: str | None = Query(default="active"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}
    if platform:
        clauses.append("platform = :platform")
        params["platform"] = platform
    if status:
        clauses.append("status = :status")
        params["status"] = status
    sql = f"""
        SELECT id::text, platform, external_shop_id, name, primary_owner_user_id::text,
               timezone, currency, status, meta
        FROM shop
        WHERE {' AND '.join(clauses)}
        ORDER BY platform, name
    """
    rows = (await db.execute(text(sql), params)).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("", status_code=201)
async def create_shop(
    body: ShopCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    shop_id = str(uuid4())
    import json

    try:
        await db.execute(
            text(
                """
                INSERT INTO shop (
                    id, platform, external_shop_id, name, primary_owner_user_id,
                    timezone, currency, meta
                ) VALUES (
                    :id, :platform, :external_shop_id, :name, :owner,
                    :timezone, :currency, CAST(:meta AS jsonb)
                )
                """
            ),
            {
                "id": shop_id,
                "platform": body.platform,
                "external_shop_id": body.external_shop_id,
                "name": body.name,
                "owner": body.primary_owner_user_id,
                "timezone": body.timezone,
                "currency": body.currency,
                "meta": json.dumps(body.meta, ensure_ascii=False),
            },
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"创建失败: {exc}") from exc
    row = (
        await db.execute(
            text(
                """
                SELECT id::text, platform, external_shop_id, name, primary_owner_user_id::text,
                       timezone, currency, status, meta
                FROM shop WHERE id = :id
                """
            ),
            {"id": shop_id},
        )
    ).mappings().first()
    return dict(row)


@router.patch("/{shop_id}")
async def update_shop(
    shop_id: str,
    body: ShopUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict[str, Any]:
    import json

    current = (
        await db.execute(text("SELECT id::text FROM shop WHERE id = :id"), {"id": shop_id})
    ).first()
    if not current:
        raise HTTPException(status_code=404, detail="店铺不存在")

    sets = ["updated_at = now()"]
    params: dict[str, Any] = {"id": shop_id}
    if body.name is not None:
        sets.append("name = :name")
        params["name"] = body.name
    if body.primary_owner_user_id is not None:
        sets.append("primary_owner_user_id = :owner")
        params["owner"] = body.primary_owner_user_id
    if body.status is not None:
        sets.append("status = :status")
        params["status"] = body.status
    if body.meta is not None:
        sets.append("meta = CAST(:meta AS jsonb)")
        params["meta"] = json.dumps(body.meta, ensure_ascii=False)

    await db.execute(text(f"UPDATE shop SET {', '.join(sets)} WHERE id = :id"), params)
    await db.commit()
    row = (
        await db.execute(
            text(
                """
                SELECT id::text, platform, external_shop_id, name, primary_owner_user_id::text,
                       timezone, currency, status, meta
                FROM shop WHERE id = :id
                """
            ),
            {"id": shop_id},
        )
    ).mappings().first()
    return dict(row)
