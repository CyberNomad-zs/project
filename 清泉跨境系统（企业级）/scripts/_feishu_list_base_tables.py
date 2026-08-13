# -*- coding: utf-8 -*-
"""List bitable tables under a Base using app credentials (env or CLI args)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def req(method: str, url: str, body=None, token: str | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"code": e.code, "msg": raw, "http_error": True}


def main() -> int:
    app_id = os.environ.get("FEISHU_APP_ID") or (sys.argv[1] if len(sys.argv) > 1 else "")
    app_secret = os.environ.get("FEISHU_APP_SECRET") or (sys.argv[2] if len(sys.argv) > 2 else "")
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN_TK") or (
        sys.argv[3] if len(sys.argv) > 3 else ""
    )
    if not app_id or not app_secret or not app_token:
        print("usage: APP_ID SECRET APP_TOKEN", file=sys.stderr)
        return 2
    tok = req(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    if tok.get("code") != 0:
        print("token_fail", json.dumps(tok, ensure_ascii=False))
        return 1
    token = tok["tenant_access_token"]
    print("token_ok")
    listed = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?page_size=100",
        token=token,
    )
    print("list_code", listed.get("code"), listed.get("msg"))
    if listed.get("code") != 0:
        print(json.dumps(listed, ensure_ascii=False)[:500])
        return 1
    items = (listed.get("data") or {}).get("items") or []
    print("table_count", len(items))
    want = ("体验", "内容", "达人", "异常", "店铺", "广告", "T1", "T2")
    for t in items:
        name = str(t.get("name") or "")
        tid = t.get("table_id")
        flag = " *" if any(k in name for k in want) else ""
        print(f"{tid}\t{name}{flag}")
    # record counts for 体验分日
    for t in items:
        if "体验" in str(t.get("name") or ""):
            tid = t["table_id"]
            rec = req(
                "GET",
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{tid}/records?page_size=1",
                token=token,
            )
            total = (rec.get("data") or {}).get("total")
            print(f"experience_table {tid} total={total} code={rec.get('code')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
