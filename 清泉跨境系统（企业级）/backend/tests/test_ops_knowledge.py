"""运营知识库 A+B：真实写路径 + guidance + 草稿发布 + 指标回填。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


def _biz(prefix: str = "B0") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8].upper()}"


@pytest.mark.asyncio
async def test_skeleton_resolve_requires_effect(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create = await client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "platform": "amazon",
            "anomaly_type": "link_wow_units_drop",
            "biz_id": _biz(),
            "title": "miss effect",
        },
    )
    assert create.status_code == 201, create.text
    tid = create.json()["id"]

    bad = await client.post(
        f"/api/v1/tasks/{tid}/resolve",
        headers=auth_headers,
        json={"note": "no effect"},
    )
    assert bad.status_code == 400
    assert "effect_code" in bad.json()["detail"]


@pytest.mark.asyncio
async def test_unknown_action_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create = await client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "platform": "tiktok",
            "anomaly_type": "low_roi",
            "biz_id": _biz("TK"),
            "title": "bad action",
        },
    )
    assert create.status_code == 201, create.text
    tid = create.json()["id"]

    bad = await client.post(
        f"/api/v1/tasks/{tid}/progress",
        headers=auth_headers,
        json={"note": "try", "action_code": "not_a_real_action"},
    )
    assert bad.status_code == 400
    assert "action_code" in bad.json()["detail"]


@pytest.mark.asyncio
async def test_structured_resolve_and_guidance_history(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """合法闭环后 history 非空，且至少有一条 published 剧本。"""
    skeletons = [
        ("amazon", "link_wow_units_drop", "amz_adjust_ads", "B0"),
        ("tiktok", "low_roi", "tk_pause_low_roi", "TK"),
        ("temu", "listing_off", "temu_relist", "TM"),
    ]
    for platform, anomaly, action, prefix in skeletons:
        c = await client.post(
            "/api/v1/tasks",
            headers=auth_headers,
            json={
                "platform": platform,
                "anomaly_type": anomaly,
                "biz_id": _biz(prefix),
                "title": f"close {platform}",
            },
        )
        assert c.status_code == 201, c.text
        tid = c.json()["id"]
        r = await client.post(
            f"/api/v1/tasks/{tid}/resolve",
            headers=auth_headers,
            json={
                "note": "done",
                "action_code": action,
                "effect_code": "recovered",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "resolved"
        assert body["last_action_code"] == action
        assert body["last_effect_code"] == "recovered"

        g = await client.get(
            "/api/v1/kb/guidance",
            headers=auth_headers,
            params={"platform": platform, "anomaly_type": anomaly},
        )
        assert g.status_code == 200, g.text
        data = g.json()
        assert data["history"], f"history empty for {platform}"
        codes = {h["action_code"] for h in data["history"]}
        assert action in codes
        assert data["playbooks"], f"no published playbook for {platform}"
        assert all(p["status"] == "published" for p in data["playbooks"])


@pytest.mark.asyncio
async def test_draft_excluded_until_publish(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    platform, anomaly = "amazon", "link_wow_units_drop"

    # ensure some history
    c = await client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "platform": platform,
            "anomaly_type": anomaly,
            "biz_id": _biz(),
            "title": "for draft",
        },
    )
    tid = c.json()["id"]
    await client.post(
        f"/api/v1/tasks/{tid}/resolve",
        headers=auth_headers,
        json={
            "note": "x",
            "action_code": "amz_check_stock",
            "effect_code": "partial",
        },
    )

    draft_r = await client.post(
        "/api/v1/kb/playbooks/generate-draft",
        headers=auth_headers,
        json={"platform": platform, "anomaly_type": anomaly},
    )
    assert draft_r.status_code == 201, draft_r.text
    draft = draft_r.json()
    assert draft["status"] == "draft"
    draft_id = draft["id"]

    g1 = await client.get(
        "/api/v1/kb/guidance",
        headers=auth_headers,
        params={"platform": platform, "anomaly_type": anomaly},
    )
    ids1 = {p["id"] for p in g1.json()["playbooks"]}
    assert draft_id not in ids1

    pub = await client.post(
        f"/api/v1/kb/playbooks/{draft_id}/publish",
        headers=auth_headers,
    )
    assert pub.status_code == 200, pub.text
    assert pub.json()["status"] == "published"

    g2 = await client.get(
        "/api/v1/kb/guidance",
        headers=auth_headers,
        params={"platform": platform, "anomaly_type": anomaly},
    )
    ids2 = {p["id"] for p in g2.json()["playbooks"]}
    assert draft_id in ids2

    # reverse: demote → disappear
    dem = await client.post(
        f"/api/v1/kb/playbooks/{draft_id}/demote",
        headers=auth_headers,
    )
    assert dem.status_code == 200
    assert dem.json()["status"] == "draft"

    g3 = await client.get(
        "/api/v1/kb/guidance",
        headers=auth_headers,
        params={"platform": platform, "anomaly_type": anomaly},
    )
    ids3 = {p["id"] for p in g3.json()["playbooks"]}
    assert draft_id not in ids3
    # A history still present
    assert g3.json()["history"]


@pytest.mark.asyncio
async def test_metric_backfill_skip_without_fact(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    c = await client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "platform": "amazon",
            "anomaly_type": "link_wow_units_drop",
            "biz_id": _biz("NF"),  # no fact rows
            "title": "metric skip",
        },
    )
    tid = c.json()["id"]
    await client.post(
        f"/api/v1/tasks/{tid}/resolve",
        headers=auth_headers,
        json={
            "note": "x",
            "action_code": "amz_adjust_ads",
            "effect_code": "no_effect",
        },
    )
    bf = await client.post(
        "/api/v1/kb/metric-backfill",
        headers=auth_headers,
        json={"task_id": tid, "window_days": 7},
    )
    assert bf.status_code == 200, bf.text
    body = bf.json()
    assert body["status"] == "skipped"
    assert "fact" in body.get("reason", "").lower() or "no" in body.get("reason", "").lower()


@pytest.mark.asyncio
async def test_non_skeleton_note_only_resolve(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    c = await client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "platform": "amazon",
            "anomaly_type": "account_health",
            "biz_id": _biz("AH"),
            "title": "non skeleton",
        },
    )
    tid = c.json()["id"]
    r = await client.post(
        f"/api/v1/tasks/{tid}/resolve",
        headers=auth_headers,
        json={"note": "closed with note only"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
