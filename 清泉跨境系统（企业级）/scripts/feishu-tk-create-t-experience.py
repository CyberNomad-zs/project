# -*- coding: utf-8 -*-
"""在 TK 驾驶舱 Base 创建「体验分日」多维表。

成功后打印:
  FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=tbl...

用法（仓库根）:
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-create-t-experience.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE_NAME = "体验分日"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if not p.is_file():
        return env
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


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
            return {"code": e.code, "msg": raw}


def main() -> int:
    env = load_env()
    app_id = env.get("FEISHU_APP_ID") or ""
    app_secret = env.get("FEISHU_APP_SECRET") or ""
    app_token = (
        env.get("FEISHU_BITABLE_APP_TOKEN_TK")
        or env.get("FEISHU_BITABLE_APP_TOKEN")
        or ""
    )
    if not app_id or not app_secret or not app_token:
        print("missing FEISHU_APP_ID/SECRET or TK app_token", file=sys.stderr)
        return 2
    tok = req(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    if tok.get("code") != 0:
        print("token failed", tok, file=sys.stderr)
        return 1
    token = tok["tenant_access_token"]
    # list tables
    listed = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?page_size=100",
        token=token,
    )
    table_id = ""
    for t in (listed.get("data") or {}).get("items") or []:
        if t.get("name") == TABLE_NAME:
            table_id = t.get("table_id") or ""
            break
    if not table_id:
        created = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables",
            {"table": {"name": TABLE_NAME}},
            token=token,
        )
        if created.get("code") != 0:
            print("create table failed", created, file=sys.stderr)
            return 1
        table_id = (created.get("data") or {}).get("table_id") or ""
    print(f"FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY={table_id}")

    fields = [
        ("日期", 5),
        ("店铺", 1),
        ("店铺ID", 1),
        ("体验总分", 2),
        ("商品满意度", 2),
        ("履约物流", 2),
        ("客户服务", 2),
        ("状态", 1),
        ("子指标摘要", 1),
        ("抓取时间", 5),
        ("数据源URL", 1),
        ("本地ID", 1),
    ]
    existing = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=100",
        token=token,
    )
    names = {
        f.get("field_name")
        for f in ((existing.get("data") or {}).get("items") or [])
    }
    for name, typ in fields:
        if name in names:
            print(f"skip field {name}")
            continue
        body: dict = {"field_name": name, "type": typ}
        if typ == 2:
            body["property"] = {"formatter": "0.00"}
        if typ == 5:
            body["property"] = {"date_formatter": "yyyy/MM/dd", "auto_fill": False}
        r = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            body,
            token=token,
        )
        print("field", name, r.get("code"), r.get("msg", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
