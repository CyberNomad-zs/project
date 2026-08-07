# -*- coding: utf-8 -*-
"""创建 / 补齐飞书 T6「内容日」多维表（P2.4）。

幂等：同名表已存在则复用 table_id；字段按名 skip。
成功后打印应写入 .env 的 FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY=tbl...

用法（仓库根）:
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-create-t6-content.py
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-create-t6-content.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE_NAME = "内容日"
VIEW_NAMES = ["近窗明细", "有曝无单", "归因GMV Top", "高播放"]


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


def field_specs() -> list[dict]:
    def text(n: str) -> dict:
        return {"field_name": n, "type": 1}

    def num(n: str, fmt: str = "0.00") -> dict:
        return {"field_name": n, "type": 2, "property": {"formatter": fmt}}

    def date(n: str, fmt: str = "yyyy/MM/dd") -> dict:
        return {
            "field_name": n,
            "type": 5,
            "property": {"date_formatter": fmt, "auto_fill": False},
        }

    def sel(n: str, opts: list[str]) -> dict:
        return {
            "field_name": n,
            "type": 3,
            "property": {"options": [{"name": o} for o in opts]},
        }

    return [
        date("日期"),
        text("店铺"),
        text("店铺ID"),
        text("内容ID"),
        text("视频标题"),
        sel("渠道", ["short_video", "live", "photo", "other"]),
        text("商品ID"),
        num("归因GMV"),
        num("归因SKU订单", "0"),
        num("归因成交件数", "0"),
        num("播放量", "0"),
        num("曝光", "0"),
        num("点击", "0"),
        num("CTR", "0.00%"),
        num("CVR", "0.00%"),
        num("客户数", "0"),
        text("币种"),
        text("窗口"),
        text("发布时间"),
        date("抓取时间", "yyyy/MM/dd HH:mm"),
        text("数据源URL"),
        text("本地ID"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    env = load_env()
    app_id = env.get("FEISHU_APP_ID") or ""
    app_secret = env.get("FEISHU_APP_SECRET") or ""
    app_token = (
        env.get("FEISHU_BITABLE_APP_TOKEN_TK")
        or env.get("FEISHU_BITABLE_APP_TOKEN")
        or ""
    )
    existing_tid = (env.get("FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY") or "").strip()

    if not all([app_id, app_secret, app_token]):
        print("missing FEISHU_APP_ID / FEISHU_APP_SECRET / APP_TOKEN in .env")
        return 1

    tok = req(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    if tok.get("code") != 0:
        print("token fail", tok)
        return 1
    token = tok["tenant_access_token"]
    print("token ok  app_token=", app_token)

    # list tables
    listed = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?page_size=100",
        token=token,
    )
    if listed.get("code") != 0:
        print("list tables fail", listed)
        return 1
    items = (listed.get("data") or {}).get("items") or []
    by_name = { (t.get("name") or ""): t for t in items }
    print("tables:", [(t.get("name"), t.get("table_id")) for t in items])

    table_id = existing_tid
    if table_id:
        print(f"use env table_id={table_id}")
    elif TABLE_NAME in by_name:
        table_id = by_name[TABLE_NAME].get("table_id") or ""
        print(f"reuse existing name={TABLE_NAME} table_id={table_id}")
    else:
        if args.dry_run:
            print(f"dry-run: would CREATE table name={TABLE_NAME}")
            print("fields:", [f["field_name"] for f in field_specs()])
            return 0
        # 首字段作为默认索引列
        body = {
            "table": {
                "name": TABLE_NAME,
                "default_view_name": "全部",
                "fields": [
                    {"field_name": "本地ID", "type": 1},
                ],
            }
        }
        created = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables",
            body,
            token,
        )
        if created.get("code") != 0:
            print("create table fail", created)
            return 1
        table_id = (created.get("data") or {}).get("table_id") or ""
        print(f"CREATED table name={TABLE_NAME} table_id={table_id}")
        time.sleep(0.4)

    if not table_id:
        print("no table_id")
        return 1

    if args.dry_run and not existing_tid and TABLE_NAME not in by_name:
        return 0

    # ensure fields
    flist = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=100",
        token=token,
    )
    if flist.get("code") != 0:
        print("list fields fail", flist)
        return 1
    existing = {
        (f.get("field_name") or ""): f
        for f in (flist.get("data") or {}).get("items") or []
    }
    print(f"fields existing={len(existing)}")

    created_n = skipped = failed = 0
    fails: list[str] = []
    for spec in field_specs():
        name = spec["field_name"]
        if name in existing:
            print(f"  skip  {name}")
            skipped += 1
            continue
        if args.dry_run:
            print(f"  would create {name}")
            created_n += 1
            continue
        r = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            spec,
            token,
        )
        if r.get("code") == 0:
            print(f"  OK    {name}")
            created_n += 1
            existing[name] = (r.get("data") or {}).get("field") or {}
        else:
            msg = f"{name}: {r.get('code')} {r.get('msg')}"
            print(f"  FAIL  {msg}")
            fails.append(msg)
            failed += 1
        time.sleep(0.25)

    print(f"fields summary created={created_n} skipped={skipped} failed={failed}")

    # views
    vlist = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
        token=token,
    )
    vexist = set()
    if vlist.get("code") == 0:
        vexist = {
            (v.get("view_name") or "")
            for v in (vlist.get("data") or {}).get("items") or []
        }
    for vn in VIEW_NAMES:
        if vn in vexist:
            print(f"  view skip {vn}")
            continue
        if args.dry_run:
            print(f"  would view {vn}")
            continue
        r = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
            {"view_name": vn, "view_type": "grid"},
            token,
        )
        if r.get("code") == 0:
            print(f"  view OK {vn}")
        else:
            print(f"  view FAIL {vn} {r.get('code')} {r.get('msg')}")
        time.sleep(0.3)

    print()
    print("=== 写入 .env（勿提交含密文件）===")
    print(f"FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY={table_id}")
    print(
        f"打开: https://dcnkj1up67d5.feishu.cn/base/{app_token}?table={table_id}"
    )
    if fails:
        print("field fails:", fails)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
