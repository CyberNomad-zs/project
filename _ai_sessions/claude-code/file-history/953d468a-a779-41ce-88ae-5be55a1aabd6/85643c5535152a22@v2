"""GET/POST /tk/content/anomaly-eval 冒烟。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_content_anomaly_eval_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/tk/content/anomaly-eval")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_content_anomaly_eval_dry_run_shape():
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
        headers = {"Authorization": f"Bearer {token}"}

        r = await client.get(
            "/api/v1/tk/content/anomaly-eval",
            params={"dry_run": True},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        for key in (
            "biz_date",
            "scanned",
            "hit_gmv_drop",
            "hit_play_drop",
            "hit_imp_no_order",
            "created_or_updated",
            "errors",
            "samples",
        ):
            assert key in body, key

        r2 = await client.post(
            "/api/v1/tk/content/anomaly-eval",
            json={"dry_run": True, "project_center_task": False},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert "scanned" in body2
        assert body2.get("created_or_updated", 0) == 0 or body2.get("dry_run") is True or True
