"""飞书自定义群机器人 Webhook（无需 tenant token）。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FeishuBotError(RuntimeError):
    pass


async def send_webhook_text(webhook_url: str, text: str, *, timeout: float = 15.0) -> dict[str, Any]:
    """POST text 消息到群机器人 webhook。"""
    url = (webhook_url or "").strip()
    if not url:
        raise FeishuBotError("webhook_url empty")
    body = {"msg_type": "text", "content": {"text": text}}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=body)
        data = resp.json() if resp.content else {}
        # 飞书机器人成功：StatusCode=0 或 code=0
        ok = (
            resp.status_code == 200
            and (
                data.get("StatusCode") == 0
                or data.get("code") == 0
                or data.get("StatusMessage") == "success"
                or data.get("msg") == "success"
            )
        )
        if not ok:
            raise FeishuBotError(f"webhook text failed http={resp.status_code} body={data}")
        return data if isinstance(data, dict) else {"raw": data}


async def send_webhook_post(
    webhook_url: str,
    *,
    title: str,
    lines: list[str],
    timeout: float = 15.0,
) -> dict[str, Any]:
    """POST 富文本 post 消息（标题 + 多行文本）。"""
    url = (webhook_url or "").strip()
    if not url:
        raise FeishuBotError("webhook_url empty")
    content_lines: list[list[dict[str, Any]]] = []
    for line in lines:
        s = str(line or "").strip()
        if not s:
            continue
        content_lines.append([{"tag": "text", "text": s + "\n"}])
    if not content_lines:
        content_lines = [[{"tag": "text", "text": "(无正文)\n"}]]
    body = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title[:200],
                    "content": content_lines,
                }
            }
        },
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=body)
        data = resp.json() if resp.content else {}
        ok = (
            resp.status_code == 200
            and (
                data.get("StatusCode") == 0
                or data.get("code") == 0
                or data.get("StatusMessage") == "success"
                or data.get("msg") == "success"
            )
        )
        if not ok:
            raise FeishuBotError(f"webhook post failed http={resp.status_code} body={data}")
        return data if isinstance(data, dict) else {"raw": data}
