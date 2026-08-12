from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.infra.security import create_access_token, get_current_user, verify_password
from app.config import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str = Field(min_length=1)


@router.post("/login")
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                """
                SELECT id::text, username, password_hash, is_active
                FROM org_user WHERE username = :u
                """
            ),
            {"u": body.username},
        )
    ).mappings().first()
    if not row or not row["is_active"] or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(row["id"], extra={"username": row["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": get_settings().jwt_expire_minutes * 60,
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "is_admin": user["is_admin"],
    }
