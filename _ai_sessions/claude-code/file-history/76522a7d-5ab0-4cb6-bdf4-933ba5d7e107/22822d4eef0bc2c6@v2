"""TK 异常任务 API 集成测试。"""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_tk_anomaly_types(client, auth_headers):
    r = await client.get("/api/v1/tk/anomaly-tasks/types", headers=auth_headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert isinstance(items, list)
    assert any(i["code"] == "product_stock_low" for i in items)


@pytest.mark.asyncio
async def test_tk_anomaly_crud_flow(client, auth_headers):
    suffix = uuid.uuid4().hex[:8]
    create_body = {
        "anomaly_code": "ads_roi_low",
        "summary": f"测试低ROI-{suffix}",
        "shop_external_id": "27501502216807",
        "object_ref": f"camp-{suffix}",
        "object_type": "campaign",
        "product_name": f"Test Campaign {suffix}",
        "priority": "P1",
        "metric_snapshot": "ROI=1.1 spend=20",
        "progress_note": "联调创建",
        "project_center_task": True,
    }
    r = await client.post("/api/v1/tk/anomaly-tasks", headers=auth_headers, json=create_body)
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["anomaly_code"] == "ads_roi_low"
    assert task["anomaly_type"] == "广告ROI过低"
    assert task["status"] == "open"
    assert task["center_task_id"]
    task_id = task["id"]

    # 列表能查到
    r = await client.get(
        "/api/v1/tk/anomaly-tasks",
        headers=auth_headers,
        params={"q": suffix, "open_only": True},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 1
    assert any(i["id"] == task_id for i in data["items"])
    assert "summary" in data

    # 详情
    r = await client.get(f"/api/v1/tk/anomaly-tasks/{task_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["task_key"] == task["task_key"]

    # 进度
    r = await client.post(
        f"/api/v1/tk/anomaly-tasks/{task_id}/progress",
        headers=auth_headers,
        json={"note": "已暂停投放观察", "status": "in_progress"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_progress"
    assert "已暂停" in (r.json().get("progress_note") or "")

    # 闭环
    r = await client.post(
        f"/api/v1/tk/anomaly-tasks/{task_id}/resolve",
        headers=auth_headers,
        json={"note": "ROI 回升，关闭", "status": "resolved"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    assert r.json()["resolved_at"]

    # 再更新进度应失败
    r = await client.post(
        f"/api/v1/tk/anomaly-tasks/{task_id}/progress",
        headers=auth_headers,
        json={"note": "不应成功"},
    )
    assert r.status_code == 400
