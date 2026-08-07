"""GET /tk/content 冒烟。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_content_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/tk/content")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_content_shape_when_authed():
    from app.config import get_settings

    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "username": getattr(settings, "admin_username", None) or "admin",
                "password": getattr(settings, "admin_password", None) or "admin123",
            },
        )
        if login.status_code != 200:
            pytest.skip("no admin login in this env")
        token = login.json().get("access_token")
        r = await client.get(
            "/api/v1/tk/content",
            params={"page_size": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body
    assert "summary" in body
    assert body["summary"].get("metric") == "window_snapshot"
    assert isinstance(body["items"], list)
    if body["items"]:
        row = body["items"][0]
        assert "content_id" in row
        assert "channel" in row
        assert "biz_date" in row
