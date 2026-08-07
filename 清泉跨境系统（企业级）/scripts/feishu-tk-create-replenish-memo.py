# -*- coding: utf-8 -*-
"""创建 / 补齐飞书「TK补货备忘」手工表（方案 B，不进日更同步）。

幂等：同名表已存在则复用 table_id；字段/视图按名 skip。
人员字段（负责人）飞书 API 对应用 type 需租户权限，失败则跳过并提示 UI 补。

用法（仓库根）:
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-create-replenish-memo.py
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-create-replenish-memo.py --dry-run
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
TABLE_NAME = "TK补货备忘"
# grid 视图名；看板单独创建
GRID_VIEWS = ["待确认", "已下单在途"]
KANBAN_VIEW = "按状态看板"


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


def req(
    method: str,
    url: str,
    body=None,
    token: str | None = None,
    retries: int = 4,
) -> dict:
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(retries):
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
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            time.sleep(0.8 * (attempt + 1))
    raise urllib.error.URLError(f"req failed after {retries} tries: {last_err}")


def field_specs() -> list[dict]:
    def text(n: str) -> dict:
        return {"field_name": n, "type": 1}

    def num(n: str, fmt: str = "0") -> dict:
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

    # type 11 = 人员；部分应用可能无权限，失败可 UI 补
    def user(n: str) -> dict:
        return {
            "field_name": n,
            "type": 11,
            "property": {"multiple": False},
        }

    return [
        date("登记日期"),
        text("店铺"),
        text("商品ID"),
        text("商品名"),
        text("SKU"),
        num("可售库存", "0"),
        num("建议补货量", "0"),
        sel("紧急度", ["断货", "低库存", "预补"]),
        sel("状态", ["待确认", "已下单", "在途", "已上架", "取消"]),
        user("负责人"),
        date("期望到货日"),
        text("来源异常"),
        text("备注"),
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
    existing_tid = (env.get("FEISHU_BITABLE_TABLE_TK_REPLENISH_MEMO") or "").strip()

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

    listed = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?page_size=100",
        token=token,
    )
    if listed.get("code") != 0:
        print("list tables fail", listed)
        return 1
    items = (listed.get("data") or {}).get("items") or []
    by_name = {(t.get("name") or ""): t for t in items}
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
        body = {
            "table": {
                "name": TABLE_NAME,
                "default_view_name": "全部",
                "fields": [
                    {"field_name": "商品ID", "type": 1},
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
    soft_fails: list[str] = []
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
            # 人员字段失败不阻断整表
            if spec.get("type") == 11:
                print(f"  SOFT  {msg}  → 请在飞书 UI 手动加「负责人」人员字段")
                soft_fails.append(msg)
            else:
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

    for vn in GRID_VIEWS:
        if vn in vexist:
            print(f"  view skip {vn}")
            continue
        if args.dry_run:
            print(f"  would view {vn} grid")
            continue
        r = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
            {"view_name": vn, "view_type": "grid"},
            token,
        )
        if r.get("code") == 0:
            print(f"  view OK {vn} (grid)")
            vexist.add(vn)
        else:
            print(f"  view FAIL {vn} {r.get('code')} {r.get('msg')}")
        time.sleep(0.3)

    if KANBAN_VIEW not in vexist:
        if args.dry_run:
            print(f"  would view {KANBAN_VIEW} kanban")
        else:
            r = req(
                "POST",
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
                {"view_name": KANBAN_VIEW, "view_type": "kanban"},
                token,
            )
            if r.get("code") == 0:
                print(f"  view OK {KANBAN_VIEW} (kanban)")
            else:
                # 部分环境 kanban 需指定 group 字段；失败则降级 grid
                print(f"  view kanban FAIL {r.get('code')} {r.get('msg')} → try grid")
                r2 = req(
                    "POST",
                    f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
                    {"view_name": KANBAN_VIEW, "view_type": "grid"},
                    token,
                )
                if r2.get("code") == 0:
                    print(f"  view OK {KANBAN_VIEW} (grid fallback)")
                else:
                    print(f"  view FAIL {KANBAN_VIEW} {r2.get('code')} {r2.get('msg')}")
    else:
        print(f"  view skip {KANBAN_VIEW}")

    print()
    print("=== 完成（手工表，勿写入日更 table_key）===")
    print(f"table_id={table_id}")
    print(f"可选记录: FEISHU_BITABLE_TABLE_TK_REPLENISH_MEMO={table_id}")
    print(f"打开: https://dcnkj1up67d5.feishu.cn/base/{app_token}?table={table_id}")
    print()
    print("请在飞书 UI 补视图筛选：")
    print("  · 待确认 → 状态 = 待确认，登记日期降序")
    print("  · 已下单在途 → 状态 = 已下单 或 在途")
    print("  · 按状态看板 → 分组字段 = 状态（若已是看板）")
    if soft_fails:
        print("soft field notes:", soft_fails)
    if fails:
        print("field fails:", fails)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
