# -*- coding: utf-8 -*-
"""List TK Base tables; count records on experience-like tables."""
from __future__ import annotations

import json
import os
import urllib.request


def req(method: str, url: str, body=None, token: str | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    # load from process env (docker --env-file injects via host .env when we source)
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    app_token = (
        os.environ.get("FEISHU_BITABLE_APP_TOKEN_TK")
        or os.environ.get("FEISHU_BITABLE_APP_TOKEN")
        or ""
    )
    print("app_token", app_token[:12], "...", "len", len(app_token))
    tok = req(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    assert tok.get("code") == 0, tok
    token = tok["tenant_access_token"]
    listed = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?page_size=100",
        token=token,
    )
    print("list_code", listed.get("code"), listed.get("msg"))
    items = (listed.get("data") or {}).get("items") or []
    for t in items:
        name = t.get("name")
        tid = t.get("table_id")
        mark = ""
        if "体验" in str(name) or tid in (
            "tblSyTljO6C6tRaY",
            "tbl9CYd8vb4DJaGN",
        ):
            mark = " <<<<"
        print(f"  {tid}  {name}{mark}")

    for tid in ("tblSyTljO6C6tRaY", "tbl9CYd8vb4DJaGN"):
        try:
            rec = req(
                "GET",
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{tid}/records?page_size=5",
                token=token,
            )
            total = (rec.get("data") or {}).get("total")
            print(f"records {tid}: code={rec.get('code')} msg={rec.get('msg')} total={total}")
            items = (rec.get("data") or {}).get("items") or []
            for it in items[:3]:
                print("   fields keys", list((it.get("fields") or {}).keys())[:8])
        except Exception as e:
            print(f"records {tid}: EXC {e}")


if __name__ == "__main__":
    main()
