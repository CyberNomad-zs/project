# -*- coding: utf-8 -*-
"""Query Feishu bitable meta / members if permissions allow."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
from app.config import get_settings


def main() -> None:
    s = get_settings()
    app_token = "FrXvbTodVad1Kqs0hCkckrI8noc"
    # token
    r = httpx.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": s.feishu_app_id, "app_secret": s.feishu_app_secret},
        timeout=30,
    )
    r.raise_for_status()
    token = r.json()["tenant_access_token"]
    h = {"Authorization": f"Bearer {token}"}

    endpoints = [
        ("GET", f"/bitable/v1/apps/{app_token}", None),
        ("GET", f"/drive/v1/metas/batch_query", None),
        # drive file meta by token
        ("GET", f"/drive/v1/metas/{app_token}?doc_type=bitable", None),
        ("GET", f"/drive/v1/permissions/{app_token}/members?type=bitable", None),
        ("GET", f"/drive/v1/permissions/{app_token}/members?type=base", None),
        ("GET", f"/drive/v1/permissions/{app_token}/public?type=bitable", None),
        ("GET", f"/bitable/v1/apps/{app_token}/tables", None),
        # wiki / explorer
        ("POST", "/drive/v1/metas/batch_query", {"request_docs": [{"doc_token": app_token, "doc_type": "bitable"}], "with_url": True}),
    ]

    base = "https://open.feishu.cn/open-apis"
    for method, path, body in endpoints:
        url = base + path if path.startswith("/") else path
        try:
            if method == "GET":
                resp = httpx.get(url if url.startswith("http") else base + path, headers=h, timeout=30)
            else:
                resp = httpx.post(base + path, headers={**h, "Content-Type": "application/json"}, json=body or {}, timeout=30)
            print("=" * 60)
            print(method, path, "->", resp.status_code)
            data = resp.json()
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
        except Exception as e:
            print("=" * 60)
            print(method, path, "ERR", e)


if __name__ == "__main__":
    main()
