# -*- coding: utf-8 -*-
"""重建 TK 总表「达人日」：系统主键（索引列）改为「日期」，「本地ID」降为普通文本列。

当前旧表 tblDTIwDWHGlJ9qf 的首字段是「本地ID」，不符合其他 TK 总表以「日期」为主键的约定。

步骤：
  1. 从旧表读取字段（保留「是否出单」单选选项、数字/日期 formatter）
  2. 旧表改名为 达人日_归档_YYYYMMDD
  3. 新建「达人日」，首字段 = 日期（type 5，yyyy/MM/dd）
  4. 补齐其余字段，「本地ID」作为普通文本列（非主键）
  5. 打印需写入 .env 的 FEISHU_BITABLE_TABLE_TK_AFFILIATE_CREATOR_DAILY

用法（仓库根）:
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-rebuild-affiliate-table.py --dry-run
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-rebuild-affiliate-table.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def req(method: str, url: str, body=None, token: str | None = None, retries: int = 5) -> dict:
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
            raise RuntimeError(f"list fields: {r}")
        data = r.get("data") or {}
        items.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    return items


def list_tables(app_token: str, token: str) -> list[dict]:
    items: list[dict] = []
    page_token = None
    while True:
        q = "page_size=100"
        if page_token:
            q += f"&page_token={page_token}"
        r = req(
            "GET",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?{q}",
            token=token,
        )
        if r.get("code") != 0:
            raise RuntimeError(f"list tables: {r}")
        data = r.get("data") or {}
        items.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    return items


def field_create_body(src: dict) -> dict | None:
    name = (src.get("field_name") or "").strip()
    ftype = src.get("type")
    if not name or ftype is None:
        return None
    # 跳过系统/公式/关联/自动编号等不可建字段
    if ftype in (18, 19, 20, 1001, 1002, 1003, 1004, 1005):
        return None
    body: dict = {"field_name": name, "type": int(ftype)}
    prop = src.get("property")
    if isinstance(prop, dict) and prop:
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
    return body


def reorder_specs(specs: list[dict]) -> list[dict]:
    """首字段强制「日期」，「本地ID」挪到最后（普通文本列，非主键）。"""
    by = {s["field_name"]: s for s in specs}
    ordered: list[dict] = []
    if "日期" in by:
        ordered.append(by.pop("日期"))
    for s in specs:
        n = s["field_name"]
        if n in by and n != "本地ID":
            ordered.append(by.pop(n))
    if "本地ID" in by:
        ordered.append(by.pop("本地ID"))
    return ordered


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--old-table-id",
        default="",
        help="旧总表 table_id，默认读 .env FEISHU_BITABLE_TABLE_TK_AFFILIATE_CREATOR_DAILY",
    )
    ap.add_argument("--new-name", default="达人日", help="新表名称（默认仍叫达人日）")
    args = ap.parse_args()

    env = load_env()
    app_id = env.get("FEISHU_APP_ID") or ""
    app_secret = env.get("FEISHU_APP_SECRET") or ""
    app_token = (
        env.get("FEISHU_BITABLE_APP_TOKEN_TK")
        or env.get("FEISHU_BITABLE_APP_TOKEN")
        or ""
    )
    old_tid = (
        args.old_table_id
        or env.get("FEISHU_BITABLE_TABLE_TK_AFFILIATE_CREATOR_DAILY")
        or ""
    ).strip()
    if not all([app_id, app_secret, app_token, old_tid]):
        print("missing FEISHU credentials or old table id")
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
    print(f"token ok  app={app_token}  old={old_tid}  dry_run={args.dry_run}")

    src_fields = list_all_fields(app_token, old_tid, token)
    print(f"source fields: {len(src_fields)}")
    specs: list[dict] = []
    seen: set[str] = set()
    for f in src_fields:
        body = field_create_body(f)
        if not body:
            print(f"  skip {f.get('field_name')} type={f.get('type')}")
            continue
        n = body["field_name"]
        if n in seen:
            continue
        seen.add(n)
        specs.append(body)
    if "日期" not in seen:
        specs.insert(
            0,
            {
                "field_name": "日期",
                "type": 5,
                "property": {"date_formatter": "yyyy/MM/dd", "auto_fill": False},
            },
        )
    if "本地ID" not in seen:
        specs.append({"field_name": "本地ID", "type": 1})
    specs = reorder_specs(specs)
    print(f"copyable fields: {len(specs)}  primary_will_be={specs[0]['field_name']}")
    print("  order:", " -> ".join(s["field_name"] for s in specs))

    stamp = date.today().strftime("%Y%m%d")
    archive_name = f"达人日_归档_{stamp}"
    new_name = args.new_name

    tables = list_tables(app_token, token)
    by_name = {(t.get("name") or ""): t for t in tables}

    if new_name in by_name:
        exist_id = by_name[new_name].get("table_id") or ""
        if exist_id and exist_id != old_tid:
            print(f"FATAL: table name '{new_name}' already exists as {exist_id}")
            return 2

    if args.dry_run:
        print(f"[dry-run] would rename {old_tid} -> {archive_name}")
        print(f"[dry-run] would CREATE {new_name} with primary={specs[0]['field_name']}")
        print(f"[dry-run] would add {len(specs)-1} more fields")
        return 0

    # 1) 旧表改名归档
    r = req(
        "PATCH",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{old_tid}",
        {"name": archive_name},
        token,
    )
    if r.get("code") != 0:
        print(f"WARN rename old table: {r.get('code')} {r.get('msg')}")
    else:
        print(f"OK rename old -> {archive_name} ({old_tid})")
    time.sleep(0.4)

    # 2) 建新表（仅首字段 = 日期，成为系统主键/索引列）
    first = specs[0]
    created = req(
        "POST",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables",
        {
            "table": {
                "name": new_name,
                "default_view_name": "全部",
                "fields": [first],
            }
        },
        token,
    )
    if created.get("code") != 0:
        print("CREATE table fail", created)
        return 3
    new_tid = (created.get("data") or {}).get("table_id") or ""
    if not new_tid:
        new_tid = ((created.get("data") or {}).get("table") or {}).get("table_id") or ""
    print(f"OK CREATE {new_name} -> {new_tid} primary={first['field_name']}")
    time.sleep(0.5)

    # 3) 追加其余字段
    ok = skip = fail = 0
    for spec in specs[1:]:
        r = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{new_tid}/fields",
            spec,
            token,
        )
        code = r.get("code")
        name = spec["field_name"]
        if code == 0:
            ok += 1
            print(f"  + {name}")
        elif code in (1254014, 1254045):
            skip += 1
            print(f"  skip-dup {name}")
        else:
            fail += 1
            print(f"  FAIL {name}: {code} {r.get('msg')}")
        time.sleep(0.22)
    print(f"fields added ok={ok} skip={skip} fail={fail}")

    # 4) 校验系统主键
    new_fields = list_all_fields(app_token, new_tid, token)
    prim = [f for f in new_fields if f.get("is_primary")]
    print("primary field(s):", [(f.get("field_name"), f.get("type")) for f in prim])
    zj = next((f for f in new_fields if f.get("field_name") == "本地ID"), None)
    if zj:
        print(f"「本地ID」 is_primary={zj.get('is_primary')} type={zj.get('type')}  (期望 False)")

    # 5) 写出结果
    result = {
        "old_table_id": old_tid,
        "old_table_archived_as": archive_name,
        "new_table_id": new_tid,
        "new_table_name": new_name,
        "system_primary": [(f.get("field_name"), f.get("type")) for f in prim],
        "本地ID_is_primary": (zj or {}).get("is_primary"),
        "field_count": len(new_fields),
        "url": f"https://dn86p8pyqr.feishu.cn/base/{app_token}?table={new_tid}",
        "env_line": f"FEISHU_BITABLE_TABLE_TK_AFFILIATE_CREATOR_DAILY={new_tid}",
    }
    out = ROOT / "dist-pack" / f"affiliate-rebuild-{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("--- DONE ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"result file: {out}")
    print("NEXT:")
    print(f"  1) set .env: {result['env_line']}")
    print("  2) clear PG sync_feishu_map where table_key='tk_affiliate_creator_daily' (not ::slug)")
    print("  3) run feishu tk affiliate sync (mode=full)")
    return 0 if fail == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
