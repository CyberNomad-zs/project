# -*- coding: utf-8 -*-
"""补齐 TK「异常任务」飞书列与视图，对齐 AMZ ASIN健康度监控·异常任务。

AMZ 参考: TkW0bXEAAa3Fo3sdKagcL9fTn2b / tblXnUm9VSmyQ2AC
TK 表: 清泉 Base LzTAbQsThaPOzis2lFvciDMlnyh / 异常任务 tblgDbCXVfdbp0oS
（旧金猫 C1iHbw…/tblstt4… 仅历史参考，勿再写）

幂等：字段/视图按名 skip。不删旧列。
筛选条件需在飞书 UI 补（API 视图创建仅建壳）。

用法（仓库根）:
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-upgrade-anomaly-amz-style.py
  backend\\.venv\\Scripts\\python.exe scripts\\feishu-tk-upgrade-anomaly-amz-style.py --dry-run
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

# 新增列（AMZ 同名优先）；已有则 skip
NEW_FIELDS: list[dict] = [
    {"field_name": "异常编号", "type": 1},
    {
        "field_name": "等级",
        "type": 3,
        "property": {"options": [{"name": o} for o in ("red", "orange", "yellow")]},
    },
    {"field_name": "指标摘要", "type": 1},
    {"field_name": "当前值", "type": 2, "property": {"formatter": "0.00"}},
    {"field_name": "当前值含义", "type": 1},
    {"field_name": "对比值", "type": 2, "property": {"formatter": "0.00"}},
    {"field_name": "对比值含义", "type": 1},
    {"field_name": "变化幅度", "type": 2, "property": {"formatter": "0.00"}},
    {"field_name": "变化幅度含义", "type": 1},
    {"field_name": "负责人", "type": 1},
    {"field_name": "审核人", "type": 1},
    {"field_name": "连续异常次数", "type": 2, "property": {"formatter": "0"}},
    {"field_name": "需要老板决策", "type": 7},  # checkbox
    {"field_name": "说明", "type": 1},
    {"field_name": "是否属实", "type": 1},
    {"field_name": "判断依据", "type": 1},
    {"field_name": "采取动作", "type": 1},
    {
        "field_name": "执行日期_系统",
        "type": 5,
        "property": {"date_formatter": "yyyy/MM/dd", "auto_fill": False},
    },
    {"field_name": "执行人", "type": 1},
    {"field_name": "动作前数据", "type": 1},
    {"field_name": "动作后数据", "type": 1},
    {"field_name": "是否有效", "type": 1},
    {"field_name": "需审核事项", "type": 1},
    {
        "field_name": "复查日期",
        "type": 5,
        "property": {"date_formatter": "yyyy/MM/dd", "auto_fill": False},
    },
    {"field_name": "下一步动作", "type": 1},
    {"field_name": "闭环状态", "type": 1},
]

VIEW_NAMES = [
    "01_红色任务",
    "02_橙色任务",
    "06_待老板决策",
    "07_全部未关闭",
    "按等级-红橙黄",
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
    raise urllib.error.URLError(f"req failed after {retries}: {last_err}")


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
    tid = (
        (env.get("FEISHU_BITABLE_TABLE_TK_ANOMALY_TASK") or "").strip()
        or "tblgDbCXVfdbp0oS"  # 清泉 Base 异常任务（2026-08-10）
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
    print("token ok  table=", tid)

    flist = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{tid}/fields?page_size=100",
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

    created = skipped = failed = 0
    fails: list[str] = []
    for spec in NEW_FIELDS:
        name = spec["field_name"]
        if name in existing:
            print(f"  skip  {name}")
            skipped += 1
            continue
        if args.dry_run:
            print(f"  would {name} type={spec['type']}")
            created += 1
            continue
        r = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{tid}/fields",
            spec,
            token,
        )
        if r.get("code") == 0:
            print(f"  OK    {name}")
            created += 1
            existing[name] = (r.get("data") or {}).get("field") or {}
        else:
            msg = f"{name}: {r.get('code')} {r.get('msg')}"
            print(f"  FAIL  {msg}")
            fails.append(msg)
            failed += 1
        time.sleep(0.25)

    print(f"fields summary created={created} skipped={skipped} failed={failed}")

    vlist = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{tid}/views",
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
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{tid}/views",
            {"view_name": vn, "view_type": "grid"},
            token,
        )
        if r.get("code") == 0:
            print(f"  view OK {vn}")
        else:
            print(f"  view FAIL {vn} {r.get('code')} {r.get('msg')}")
        time.sleep(0.3)

    print()
    print("=== 完成 ===")
    print(f"打开: https://dcnkj1up67d5.feishu.cn/base/{app_token}?table={tid}")
    print("请在飞书 UI 补筛选：")
    print("  01_红色任务     → 等级 = red；未关闭优先")
    print("  02_橙色任务     → 等级 = orange")
    print("  06_待老板决策   → 需要老板决策 = 是；状态 ≠ 已闭环")
    print("  07_全部未关闭   → 状态 = 未处理 或 处理中")
    print("  按等级-红橙黄   → 分组：等级（可改看板）")
    print("同步新字段后跑: feishu-tk-daily-sync.ps1 -AnomalyOnly")
    if fails:
        print("fails:", fails)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
