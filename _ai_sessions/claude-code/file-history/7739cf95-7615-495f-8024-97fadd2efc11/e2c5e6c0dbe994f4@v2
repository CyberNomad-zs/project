# -*- coding: utf-8 -*-
"""为三个 TK 店铺各克隆一套可分店表（纯 API，文件夹需手工拖）。

从现网总表复制字段定义，建：
  店铺日经营·{店}
  广告活动日明细·{店}
  异常任务·{店}
  内容日·{店}

幂等：同名表复用；字段按名 skip。
成功后写 config/feishu-tk-store-tables.json，并打印 .env 提示。

用法（仓库根）:
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-create-store-tables.py
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-create-store-tables.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "config" / "feishu-tk-store-tables.json"

# 展示名 → 数据里可能出现的别名（同步侧也会用）
STORES: list[dict[str, object]] = [
    {
        "name": "Deal to deal",
        "slug": "deal-to-deal",
        "aliases": ["Deal to deal", "Deal to Deal"],
    },
    {
        "name": "Gardena",
        "slug": "gardena",
        "aliases": ["Gardena", "TikTok - Pop", "TikTok-Pop", "pop店"],
    },
    {
        "name": "SHOP INOUT",
        "slug": "shop-inout",
        "aliases": ["SHOP INOUT", "Tiktok - KK Seagull", "TikTok - KK Seagull"],
    },
]

# kind → 总表 env key / 默认 table_id / 新表名前缀
KINDS: list[dict[str, str]] = [
    {
        "key": "tk_shop_daily",
        "env": "FEISHU_BITABLE_TABLE_TK_SHOP_DAILY",
        "default_tid": "tblwh7EVeAFPfvuy",
        "prefix": "店铺日经营",
    },
    {
        "key": "tk_ads_campaign",
        "env": "FEISHU_BITABLE_TABLE_TK_ADS_CAMPAIGN",
        "default_tid": "tblXaQ871ZcrrTPL",
        "prefix": "广告活动日明细",
    },
    {
        "key": "tk_anomaly_task",
        "env": "FEISHU_BITABLE_TABLE_TK_ANOMALY_TASK",
        "default_tid": "tblstt4IVNJihCd3",
        "prefix": "异常任务",
    },
    {
        "key": "tk_content_daily",
        "env": "FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY",
        "default_tid": "tbleuAjZFdrkLBu6",
        "prefix": "内容日",
    },
]


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


def req(method: str, url: str, body=None, token: str | None = None, retries: int = 4) -> dict:
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
            with urllib.request.urlopen(r, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"code": e.code, "msg": raw}
            # 限流重试
            if parsed.get("code") in (99991400, 99991403, 1254291) or e.code == 429:
                time.sleep(1.2 * (attempt + 1))
                last_err = e
                continue
            return parsed
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            time.sleep(0.8 * (attempt + 1))
    return {"code": -1, "msg": f"req failed after {retries}: {last_err}"}


def list_all_fields(app_token: str, table_id: str, token: str) -> list[dict]:
    items: list[dict] = []
    page_token = None
    while True:
        q = "page_size=100"
        if page_token:
            q += f"&page_token={page_token}"
        r = req(
            "GET",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?{q}",
            token=token,
        )
        if r.get("code") != 0:
            raise RuntimeError(f"list fields {table_id}: {r}")
        data = r.get("data") or {}
        items.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    return items


def field_create_body(src: dict) -> dict | None:
    """从源字段构造 create body；跳过系统/不支持复制的类型。"""
    name = (src.get("field_name") or "").strip()
    ftype = src.get("type")
    if not name or ftype is None:
        return None
    # 跳过：自动编号(1005)、创建/修改时间、创建人/修改人、公式(20) 有时需重配——公式尽量跳过避免依赖
    # 飞书 type: 1 text 2 num 3 single 4 multi 5 date 7 checkbox 11 user 13 phone 15 url 17 attachment 18 link 19 lookup 20 formula 1001 created_time 1002 modified_time 1003 created_user 1004 modified_user 1005 auto_number
    if ftype in (19, 20, 1001, 1002, 1003, 1004, 1005):
        return None
    body: dict = {"field_name": name, "type": ftype}
    prop = src.get("property")
    if isinstance(prop, dict) and prop:
        # 去掉只读/id 类键，保留 options/formatter 等
        clean = {}
        for k, v in prop.items():
            if k in ("options", "formatter", "date_formatter", "auto_fill", "multiple"):
                if k == "options" and isinstance(v, list):
                    clean[k] = [
                        {"name": o.get("name")}
                        for o in v
                        if isinstance(o, dict) and o.get("name")
                    ]
                else:
                    clean[k] = v
        if clean:
            body["property"] = clean
    ui = src.get("ui_type")
    if ui:
        body["ui_type"] = ui
    return body


def ensure_table(
    app_token: str,
    token: str,
    name: str,
    field_specs: list[dict],
    by_name: dict[str, dict],
    dry_run: bool,
) -> str:
    if name in by_name:
        tid = by_name[name].get("table_id") or ""
        print(f"  reuse table {name} -> {tid}")
        return tid
    if not field_specs:
        raise RuntimeError(f"no fields to create table {name}")
    first = field_specs[0]
    if dry_run:
        print(f"  dry-run CREATE {name} primary={first.get('field_name')} +{len(field_specs)-1} fields")
        return f"dry_{re.sub(r'[^a-z0-9]+', '_', name.lower())}"
    body = {
        "table": {
            "name": name,
            "default_view_name": "全部",
            "fields": [first],
        }
    }
    created = req(
        "POST",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables",
        body,
        token,
    )
    if created.get("code") != 0:
        raise RuntimeError(f"create table {name}: {created}")
    tid = (created.get("data") or {}).get("table_id") or ""
    print(f"  CREATED {name} -> {tid}")
    by_name[name] = {"name": name, "table_id": tid}
    time.sleep(0.35)
    return tid


def ensure_fields(
    app_token: str,
    token: str,
    table_id: str,
    field_specs: list[dict],
    dry_run: bool,
) -> tuple[int, int, int]:
    if table_id.startswith("dry_"):
        return 0, len(field_specs), 0
    existing_list = list_all_fields(app_token, table_id, token)
    existing = {(f.get("field_name") or ""): f for f in existing_list}
    created = skipped = failed = 0
    for spec in field_specs:
        name = spec["field_name"]
        if name in existing:
            skipped += 1
            continue
        if dry_run:
            print(f"    dry-run field {name}")
            created += 1
            continue
        r = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            spec,
            token,
        )
        code = r.get("code")
        if code == 0:
            created += 1
            existing[name] = {}
        elif code in (1254014, 1254045):  # duplicated / already exists
            skipped += 1
            existing[name] = {}
            print(f"    skip-dup {name}")
        else:
            failed += 1
            print(f"    FAIL field {name}: {code} {r.get('msg')}")
        time.sleep(0.25)
    return created, skipped, failed


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
    if not all([app_id, app_secret, app_token]):
        print("missing FEISHU_APP_ID / SECRET / APP_TOKEN")
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
    print("token ok  app=", app_token)

    items: list[dict] = []
    page_token = None
    while True:
        q = "page_size=100"
        if page_token:
            q += f"&page_token={page_token}"
        listed = req(
            "GET",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?{q}",
            token=token,
        )
        if listed.get("code") != 0:
            print("list tables fail", listed)
            return 1
        data = listed.get("data") or {}
        items.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    by_name = {(t.get("name") or ""): t for t in items}
    print(f"tables listed: {len(items)}")

    # 预取各 kind 源字段
    source_fields: dict[str, list[dict]] = {}
    for kind in KINDS:
        tid = (env.get(kind["env"]) or "").strip() or kind["default_tid"]
        print(f"\n源表 {kind['prefix']} {tid}")
        raw = list_all_fields(app_token, tid, token)
        specs: list[dict] = []
        seen: set[str] = set()
        for f in raw:
            body = field_create_body(f)
            if not body:
                continue
            n = body["field_name"]
            if n in seen:
                continue
            seen.add(n)
            specs.append(body)
        # 主键倾向：有「本地ID」则放到创建后补；首字段用文本/日期
        if not specs:
            print("  no copyable fields")
            return 1
        # 建表首字段优先 日期 或 主键 或 第一个
        preferred = None
        for cand in ("日期", "主键", "本地ID", specs[0]["field_name"]):
            for s in specs:
                if s["field_name"] == cand:
                    preferred = s
                    break
            if preferred:
                break
        ordered = [preferred] + [s for s in specs if s is not preferred]
        source_fields[kind["key"]] = ordered
        print(f"  copyable fields: {len(ordered)}")

    mapping: dict[str, object] = {
        "version": 1,
        "app_token": app_token,
        "stores": [],
        "tables": {},  # store_name -> { table_key: table_id }
    }

    total_fail = 0
    for store in STORES:
        sname = str(store["name"])
        slug = str(store["slug"])
        print(f"\n======== 店铺 {sname} ({slug}) ========")
        store_map: dict[str, str] = {}
        for kind in KINDS:
            tname = f"{kind['prefix']}·{sname}"
            specs = source_fields[kind["key"]]
            print(f"→ {tname}")
            try:
                tid = ensure_table(app_token, token, tname, specs, by_name, args.dry_run)
                c, sk, f = ensure_fields(app_token, token, tid, specs, args.dry_run)
                print(f"  fields created={c} skipped={sk} failed={f}")
                total_fail += f
                store_map[kind["key"]] = tid
            except Exception as exc:
                total_fail += 1
                print(f"  ERR {exc}")
        mapping["tables"][sname] = store_map
        mapping["stores"].append(
            {
                "name": sname,
                "slug": slug,
                "aliases": store["aliases"],
            }
        )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        OUT_JSON.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nWROTE {OUT_JSON}")
    else:
        print("\ndry-run mapping preview:")
        print(json.dumps(mapping, ensure_ascii=False, indent=2))

    print("\n.env 可选（映射文件优先）:")
    print(f"FEISHU_TK_STORE_TABLES_JSON=config/feishu-tk-store-tables.json")
    print("\nDONE", "fails=", total_fail)
    return 1 if total_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
