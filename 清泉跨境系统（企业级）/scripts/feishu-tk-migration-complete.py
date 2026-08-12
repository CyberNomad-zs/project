# -*- coding: utf-8 -*-
"""金猫 → 清泉：TK 驾驶舱多维表迁移（字段 + 记录 + 网格视图名）。

双租户：
  - 源（金猫）：FEISHU_APP_ID / FEISHU_APP_SECRET + FEISHU_BITABLE_APP_TOKEN_TK（旧）
  - 目标（清泉）：--dst-app-id / --dst-app-secret + --dst-app-token

仪表盘组件 OpenAPI 无法完整复制，脚本结束会打印手工重绑清单。
正式链路仍是 PG → 飞书；本脚本用于把飞书侧历史行/结构搬过去。旧 Base 不删除。

用法（仓库根）:
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-migration-complete.py ^
    --dst-app-id cli_xxx --dst-app-secret xxx --dst-app-token Tcb0b...
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-migration-complete.py --dry-run ...
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-migration-complete.py --skip-records ...
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
OUT_MAP = ROOT / "config" / "feishu-tk-migration-map.json"

# 总表（与 .env / 建表方案一致）
CORE_TABLES: list[dict[str, str]] = [
    {
        "key": "tk_shop_daily",
        "env": "FEISHU_BITABLE_TABLE_TK_SHOP_DAILY",
        "default_tid": "tblwh7EVeAFPfvuy",
        "name": "店铺日经营",
        "views": ["昨日全店", "近7日明细", "低ROI店", "健康预警"],
    },
    {
        "key": "tk_ads_campaign",
        "env": "FEISHU_BITABLE_TABLE_TK_ADS_CAMPAIGN",
        "default_tid": "tblXaQ871ZcrrTPL",
        "name": "广告活动日明细",
        "views": ["昨日花费Top", "低效亏损", "高ROI", "预算将尽"],
    },
    {
        "key": "tk_anomaly_task",
        "env": "FEISHU_BITABLE_TABLE_TK_ANOMALY_TASK",
        "default_tid": "tblstt4IVNJihCd3",
        "name": "异常任务",
        "views": ["未闭环", "待老板决策", "全部"],
    },
    {
        "key": "tk_content_daily",
        "env": "FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY",
        "default_tid": "tbleuAjZFdrkLBu6",
        "name": "内容日",
        "views": ["近窗明细", "有曝无单", "归因GMV Top", "高播放"],
    },
    {
        "key": "tk_affiliate_creator_daily",
        "env": "FEISHU_BITABLE_TABLE_TK_AFFILIATE_CREATOR_DAILY",
        "default_tid": "tblsoAKtF05YyyWd",
        "name": "达人日",
        "views": ["近窗明细", "已出单", "未出单", "归因GMV Top", "佣金 Top"],
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


def req(
    method: str,
    url: str,
    body=None,
    token: str | None = None,
    retries: int = 5,
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
            with urllib.request.urlopen(r, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"code": e.code, "msg": raw}
            if parsed.get("code") in (99991400, 99991403, 1254291) or e.code == 429:
                time.sleep(1.5 * (attempt + 1))
                last_err = e
                continue
            return parsed
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            time.sleep(0.8 * (attempt + 1))
    return {"code": -1, "msg": f"req failed after {retries}: {last_err}"}


def get_tenant_token(app_id: str, app_secret: str, label: str) -> str:
    tok = req(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    if tok.get("code") != 0 or not tok.get("tenant_access_token"):
        raise RuntimeError(f"{label} tenant token fail: {tok}")
    print(f"OK  {label} tenant token")
    return tok["tenant_access_token"]


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
            raise RuntimeError(f"list tables {app_token}: {r}")
        data = r.get("data") or {}
        items.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    return items


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


def list_views(app_token: str, table_id: str, token: str) -> list[dict]:
    items: list[dict] = []
    page_token = None
    while True:
        q = "page_size=100"
        if page_token:
            q += f"&page_token={page_token}"
        r = req(
            "GET",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views?{q}",
            token=token,
        )
        if r.get("code") != 0:
            raise RuntimeError(f"list views {table_id}: {r}")
        data = r.get("data") or {}
        items.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    return items


def field_create_body(src: dict) -> dict | None:
    """从源字段构造 create body；跳过系统/公式/关联等不可直接复制类型。"""
    name = (src.get("field_name") or "").strip()
    ftype = src.get("type")
    if not name or ftype is None:
        return None
    # 19 lookup 20 formula 1001~1005 系统字段
    if ftype in (19, 20, 1001, 1002, 1003, 1004, 1005):
        return None
    body: dict = {"field_name": name, "type": ftype}
    prop = src.get("property")
    if isinstance(prop, dict) and prop:
        clean: dict = {}
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


def sanitize_record_fields(fields: dict) -> dict:
    """去掉空值与飞书只读形态，保留可写入字段。"""
    out: dict = {}
    for k, v in (fields or {}).items():
        if v is None or v == "":
            continue
        # 人员/附件等复杂结构若缺权限会失败，原样尝试；失败时上层可记 failed
        out[k] = v
    return out


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
        raise RuntimeError(f"no fields for table {name}")
    first = field_specs[0]
    if dry_run:
        print(f"  dry-run CREATE {name} primary={first.get('field_name')}")
        return f"dry_{name}"
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
    if not tid:
        # 部分返回结构 table.table_id
        tid = ((created.get("data") or {}).get("table") or {}).get("table_id") or ""
    print(f"  CREATED {name} -> {tid}")
    by_name[name] = {"name": name, "table_id": tid}
    time.sleep(0.4)
    return tid


def ensure_fields(
    app_token: str,
    token: str,
    table_id: str,
    field_specs: list[dict],
    dry_run: bool,
) -> tuple[int, int, int]:
    if str(table_id).startswith("dry_"):
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
        elif code in (1254014, 1254045):
            skipped += 1
            existing[name] = {}
        else:
            failed += 1
            print(f"    FAIL field {name}: {code} {r.get('msg')}")
        time.sleep(0.25)
    return created, skipped, failed


def ensure_views(
    app_token: str,
    token: str,
    table_id: str,
    view_names: list[str],
    dry_run: bool,
) -> tuple[int, int]:
    if str(table_id).startswith("dry_"):
        return 0, len(view_names)
    existing = {
        (v.get("view_name") or "")
        for v in list_views(app_token, table_id, token)
    }
    created = skipped = 0
    for name in view_names:
        if not name or name in existing:
            skipped += 1
            continue
        if dry_run:
            created += 1
            continue
        r = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
            {"view_name": name, "view_type": "grid"},
            token,
        )
        if r.get("code") == 0:
            created += 1
            existing.add(name)
        else:
            print(f"    FAIL view {name}: {r.get('code')} {r.get('msg')}")
        time.sleep(0.25)
    return created, skipped


def iter_source_records(
    app_token: str,
    table_id: str,
    token: str,
    page_size: int = 500,
):
    """优先 search，失败回退 list。"""
    page_token = None
    use_search = True
    while True:
        if use_search:
            body: dict = {"page_size": page_size}
            # search 的 page_token 在 query
            q = f"page_size={page_size}"
            if page_token:
                q += f"&page_token={page_token}"
            r = req(
                "POST",
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search?{q}",
                {},
                token,
            )
            if r.get("code") != 0:
                # 无 search 权限时回退 list
                print(f"  search fail ({r.get('code')} {r.get('msg')}), fallback list")
                use_search = False
                page_token = None
                continue
        else:
            q = f"page_size={page_size}"
            if page_token:
                q += f"&page_token={page_token}"
            r = req(
                "GET",
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records?{q}",
                token=token,
            )
            if r.get("code") != 0:
                raise RuntimeError(f"list records {table_id}: {r}")

        data = r.get("data") or {}
        items = data.get("items") or data.get("records") or []
        for it in items:
            yield it
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break


def batch_create_records(
    app_token: str,
    table_id: str,
    token: str,
    records: list[dict],
    dry_run: bool,
) -> tuple[int, int]:
    """返回 (ok, fail)。"""
    if not records:
        return 0, 0
    if dry_run or str(table_id).startswith("dry_"):
        return len(records), 0
    ok = fail = 0
    # 飞书 batch_create 上限 500，稳妥 100
    chunk = 100
    for i in range(0, len(records), chunk):
        part = records[i : i + chunk]
        body = {"records": [{"fields": sanitize_record_fields(x)} for x in part]}
        # 去掉空 fields
        body["records"] = [r for r in body["records"] if r.get("fields")]
        if not body["records"]:
            continue
        r = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            body,
            token,
        )
        if r.get("code") == 0:
            n = len((r.get("data") or {}).get("records") or body["records"])
            ok += n
        else:
            # 逐条重试，定位坏字段
            print(f"    batch fail {r.get('code')} {r.get('msg')}; retry one-by-one")
            for one in body["records"]:
                rr = req(
                    "POST",
                    f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                    {"fields": one["fields"]},
                    token,
                )
                if rr.get("code") == 0:
                    ok += 1
                else:
                    fail += 1
                    if fail <= 5:
                        print(f"      record fail: {rr.get('code')} {rr.get('msg')}")
                time.sleep(0.15)
        time.sleep(0.35)
    return ok, fail


def collect_source_tables(
    env: dict[str, str],
    src_app_token: str,
    src_token: str,
    include_store_tables: bool,
) -> list[dict]:
    """返回 [{key, name, src_table_id, views}]，含可选分店表。"""
    out: list[dict] = []
    for t in CORE_TABLES:
        tid = (env.get(t["env"]) or "").strip() or t["default_tid"]
        out.append(
            {
                "key": t["key"],
                "name": t["name"],
                "src_table_id": tid,
                "views": list(t.get("views") or []),
            }
        )

    if include_store_tables:
        store_json = ROOT / (
            env.get("FEISHU_TK_STORE_TABLES_JSON") or "config/feishu-tk-store-tables.json"
        )
        if store_json.is_file():
            cfg = json.loads(store_json.read_text(encoding="utf-8"))
            tables = cfg.get("tables") or {}
            # name prefix by key
            prefix = {c["key"]: c["name"] for c in CORE_TABLES}
            for store_name, kind_map in tables.items():
                if not isinstance(kind_map, dict):
                    continue
                for kind, tid in kind_map.items():
                    if not tid:
                        continue
                    pname = prefix.get(kind, kind)
                    out.append(
                        {
                            "key": f"{kind}__{store_name}",
                            "name": f"{pname}·{store_name}",
                            "src_table_id": tid,
                            "views": [],
                        }
                    )
        else:
            print(f"WARN store tables json missing: {store_json}")

    # 校验源表可读
    print(f"\n校验源 Base 表可读 app_token={src_app_token}")
    src_list = {t.get("table_id"): t for t in list_tables(src_app_token, src_token)}
    print(f"  源表数量: {len(src_list)}")
    return out


def migrate_one_table(
    *,
    src_app: str,
    src_token: str,
    dst_app: str,
    dst_token: str,
    item: dict,
    dst_by_name: dict[str, dict],
    dry_run: bool,
    skip_records: bool,
) -> dict:
    name = item["name"]
    src_tid = item["src_table_id"]
    print(f"\n======== {name}  src={src_tid} ========")

    raw_fields = list_all_fields(src_app, src_tid, src_token)
    specs: list[dict] = []
    seen: set[str] = set()
    for f in raw_fields:
        body = field_create_body(f)
        if not body:
            continue
        n = body["field_name"]
        if n in seen:
            continue
        seen.add(n)
        specs.append(body)
    if not specs:
        raise RuntimeError(f"no copyable fields on {name}")

    preferred = None
    for cand in ("日期", "主键", "本地ID", "标题", specs[0]["field_name"]):
        for s in specs:
            if s["field_name"] == cand:
                preferred = s
                break
        if preferred:
            break
    ordered = [preferred] + [s for s in specs if s is not preferred]
    print(f"  copyable fields: {len(ordered)}")

    dst_tid = ensure_table(dst_app, dst_token, name, ordered, dst_by_name, dry_run)
    c, sk, f = ensure_fields(dst_app, dst_token, dst_tid, ordered, dry_run)
    print(f"  fields created={c} skipped={sk} failed={f}")

    # 源视图名 + 推荐视图名
    src_view_names = []
    try:
        for v in list_views(src_app, src_tid, src_token):
            vn = (v.get("view_name") or "").strip()
            if vn and vn not in ("全部", "表格", "Grid view"):
                src_view_names.append(vn)
    except Exception as exc:
        print(f"  list src views warn: {exc}")
    want_views = []
    for vn in list(item.get("views") or []) + src_view_names:
        if vn and vn not in want_views:
            want_views.append(vn)
    vc, vs = ensure_views(dst_app, dst_token, dst_tid, want_views, dry_run)
    print(f"  views created={vc} skipped={vs} want={want_views}")

    rec_ok = rec_fail = rec_total = 0
    if not skip_records:
        buf: list[dict] = []
        for row in iter_source_records(src_app, src_tid, src_token):
            fields = row.get("fields") or {}
            if not fields:
                continue
            buf.append(fields)
            rec_total += 1
            if len(buf) >= 100:
                o, ff = batch_create_records(dst_app, dst_tid, dst_token, buf, dry_run)
                rec_ok += o
                rec_fail += ff
                buf = []
                print(f"  records progress total={rec_total} ok={rec_ok} fail={rec_fail}")
        if buf:
            o, ff = batch_create_records(dst_app, dst_tid, dst_token, buf, dry_run)
            rec_ok += o
            rec_fail += ff
        print(f"  records done total={rec_total} ok={rec_ok} fail={rec_fail}")
    else:
        print("  skip records")

    return {
        "key": item["key"],
        "name": name,
        "src_table_id": src_tid,
        "dst_table_id": dst_tid,
        "fields_created": c,
        "fields_failed": f,
        "views_created": vc,
        "records_total": rec_total,
        "records_ok": rec_ok,
        "records_fail": rec_fail,
    }


def print_env_snippet(dst_app_id: str, dst_app_token: str, results: list[dict]) -> None:
    by_key = {r["key"]: r for r in results if "__" not in r["key"]}
    print("\n" + "=" * 60)
    print("写入 .env（清泉）建议：")
    print(f"FEISHU_APP_ID={dst_app_id}")
    print("FEISHU_APP_SECRET=<已提供的 secret，勿提交 git>")
    print(f"FEISHU_BITABLE_APP_TOKEN={dst_app_token}")
    print(f"FEISHU_BITABLE_APP_TOKEN_TK={dst_app_token}")
    env_map = {c["key"]: c["env"] for c in CORE_TABLES}
    for key, envk in env_map.items():
        r = by_key.get(key)
        if r:
            print(f"{envk}={r['dst_table_id']}")
    print("=" * 60)
    print(
        "\n仪表盘 D1~D4：OpenAPI 无法复制组件，请在新 Base 侧栏打开各仪表盘，\n"
        "把数据源改绑到上表新 table_id（字段名与旧表一致）。旧 Base 保留不删。"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Migrate TK Feishu bitable 金猫→清泉")
    ap.add_argument("--src-app-id", default="", help="源租户 App ID，默认读 .env")
    ap.add_argument("--src-app-secret", default="", help="源租户 App Secret，默认读 .env")
    ap.add_argument("--src-app-token", default="", help="源 Base app_token，默认读 .env TK")
    ap.add_argument("--dst-app-id", required=True, help="清泉 App ID")
    ap.add_argument("--dst-app-secret", required=True, help="清泉 App Secret")
    ap.add_argument(
        "--dst-app-token",
        default="Tcb0bPY3baO2TTsaXqpcWF2enfb",
        help="清泉 Base app_token（URL /base/ 后一段）",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-records", action="store_true", help="只建表字段视图，不拷行")
    ap.add_argument(
        "--no-store-tables",
        action="store_true",
        help="不分店表，只迁 5 张总表",
    )
    ap.add_argument(
        "--only",
        default="",
        help="只迁指定 key，逗号分隔，如 tk_shop_daily,tk_ads_campaign",
    )
    args = ap.parse_args()

    env = load_env()
    src_app_id = args.src_app_id or env.get("FEISHU_APP_ID") or ""
    src_app_secret = args.src_app_secret or env.get("FEISHU_APP_SECRET") or ""
    src_app_token = (
        args.src_app_token
        or env.get("FEISHU_BITABLE_APP_TOKEN_TK")
        or env.get("FEISHU_BITABLE_APP_TOKEN")
        or ""
    )
    if not all([src_app_id, src_app_secret, src_app_token]):
        print("missing source FEISHU_APP_ID / SECRET / APP_TOKEN")
        return 1

    print("源 Base (金猫):", src_app_token)
    print("目标 Base (清泉):", args.dst_app_token)
    if args.dry_run:
        print("*** DRY RUN ***")

    try:
        src_token = get_tenant_token(src_app_id, src_app_secret, "源/金猫")
        dst_token = get_tenant_token(args.dst_app_id, args.dst_app_secret, "目标/清泉")
    except RuntimeError as e:
        print(e)
        return 1

    # 探测目标 Base 权限
    try:
        dst_tables = list_tables(args.dst_app_token, dst_token)
        print(f"目标 Base 现有表: {len(dst_tables)} -> {[t.get('name') for t in dst_tables]}")
    except RuntimeError as e:
        print("目标 Base 列表失败（请确认：1) app 已发布 2) 新 Base 已添加该应用为协作者）")
        print(e)
        return 1

    try:
        items = collect_source_tables(
            env,
            src_app_token,
            src_token,
            include_store_tables=not args.no_store_tables,
        )
    except RuntimeError as e:
        print("源 Base 读取失败:", e)
        return 1

    if args.only:
        allow = {x.strip() for x in args.only.split(",") if x.strip()}
        items = [i for i in items if i["key"] in allow or i["key"].split("__")[0] in allow]
        print("only filter ->", [i["name"] for i in items])

    dst_by_name = {(t.get("name") or ""): t for t in dst_tables}
    results: list[dict] = []
    fatal = 0
    for item in items:
        try:
            # 源表是否存在
            list_all_fields(src_app_token, item["src_table_id"], src_token)
        except RuntimeError as e:
            print(f"\nSKIP {item['name']}: 源表不可读 {e}")
            fatal += 1
            continue
        try:
            results.append(
                migrate_one_table(
                    src_app=src_app_token,
                    src_token=src_token,
                    dst_app=args.dst_app_token,
                    dst_token=dst_token,
                    item=item,
                    dst_by_name=dst_by_name,
                    dry_run=args.dry_run,
                    skip_records=args.skip_records,
                )
            )
        except Exception as exc:
            fatal += 1
            print(f"ERR {item['name']}: {exc}")

    payload = {
        "src_app_token": src_app_token,
        "dst_app_token": args.dst_app_token,
        "dst_app_id": args.dst_app_id,
        "results": results,
    }
    if not args.dry_run:
        OUT_MAP.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n映射已写: {OUT_MAP}")

    print_env_snippet(args.dst_app_id, args.dst_app_token, results)
    print(f"\ndone tables_ok={len(results)} fatal={fatal}")
    return 0 if fatal == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
