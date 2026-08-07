"""清泉采集 Agent 最小 SDK（纯标准库，供 PS/插件侧对照实现）。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class AgentClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

    def report(self, source: str, envelope: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/ingest/{source}", envelope)

    def report_batch(self, source: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/ingest/{source}", {"items": items})

    def heartbeat(self, node_id: str, meta: dict[str, Any] | None = None, version: str = "0.1.0") -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/collectors/heartbeat",
            {"node_id": node_id, "version": version, "meta": meta or {}},
        )
