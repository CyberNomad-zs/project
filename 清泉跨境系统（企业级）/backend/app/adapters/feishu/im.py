"""飞书企业应用 IM 私信（单聊）。"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.adapters.feishu.bitable import BASE, get_tenant_access_token

logger = logging.getLogger(__name__)


class FeishuImError(RuntimeError):
    pass


async def send_im_text(
    *,
    receive_id: str,
    text: str,
    receive_id_type: str = "open_id",
    timeout: float = 20.0,
) -> dict[str, Any]:
    """向单个用户发送文本私信。"""
    rid = (receive_id or "").strip()
    if not rid:
        raise FeishuImError("receive_id empty")
    body_text = str(text or "").strip() or "(空消息)"
    token = await get_tenant_access_token()
    if not token:
        raise FeishuImError("feishu app credentials missing (FEISHU_APP_ID/SECRET)")

    id_type = (receive_id_type or "open_id").strip() or "open_id"
    url = f"{BASE}/im/v1/messages?receive_id_type={id_type}"
    payload = {
        "receive_id": rid,
        "msg_type": "text",
        "content": json.dumps({"text": body_text}, ensure_ascii=False),
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        data = resp.json() if resp.content else {}
        if data.get("code") != 0:
            raise FeishuImError(f"im send failed http={resp.status_code} body={data}")
        return data if isinstance(data, dict) else {"raw": data}


async def send_im_post(
    *,
    receive_id: str,
    title: str,
    lines: list[str],
    receive_id_type: str = "open_id",
    timeout: float = 20.0,
) -> dict[str, Any]:
    """私信发送 post 富文本（标题+多行）。"""
    rid = (receive_id or "").strip()
    if not rid:
        raise FeishuImError("receive_id empty")
    token = await get_tenant_access_token()
    if not token:
        raise FeishuImError("feishu app credentials missing (FEISHU_APP_ID/SECRET)")

    content_lines: list[list[dict[str, Any]]] = []
    for line in lines:
        s = str(line or "").strip()
        if not s:
            continue
        content_lines.append([{"tag": "text", "text": s + "\n"}])
    if not content_lines:
        content_lines = [[{"tag": "text", "text": "(无正文)\n"}]]

    post_body = {
        "zh_cn": {
            "title": str(title or "提醒")[:200],
            "content": content_lines,
        }
    }
    payload = {
        "receive_id": rid,
        "msg_type": "post",
        "content": json.dumps(post_body, ensure_ascii=False),
    }
    id_type = (receive_id_type or "open_id").strip() or "open_id"
    url = f"{BASE}/im/v1/messages?receive_id_type={id_type}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        data = resp.json() if resp.content else {}
        if data.get("code") != 0:
            raise FeishuImError(f"im post failed http={resp.status_code} body={data}")
        return data if isinstance(data, dict) else {"raw": data}
