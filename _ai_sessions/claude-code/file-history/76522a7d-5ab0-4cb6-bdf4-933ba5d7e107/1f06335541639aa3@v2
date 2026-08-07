# -*- coding: utf-8 -*-
"""Ensure TK 异常任务 单选含内容域选项（幂等追加）。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
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


# 需要确保存在的选项
NEED_TYPE = [
    "广告ROI过低",
    "广告空耗",
    "广告预算将尽",
    "广告CPA过高",
    "商品断货",
    "商品库存不足",
    "店铺GMV骤降",
    "店铺订单骤降",
    "视频归因GMV骤降",
    "视频播放/曝光崩",
    "视频有曝无单",
    "其它",
]
NEED_OBJ = ["商品", "广告", "店铺", "订单", "视频内容", "其它"]


def main() -> int:
    env = load_env()
    app_id = env["FEISHU_APP_ID"]
    app_secret = env["FEISHU_APP_SECRET"]
    app_token = env.get("FEISHU_BITABLE_APP_TOKEN_TK") or env["FEISHU_BITABLE_APP_TOKEN"]
    tid = env["FEISHU_BITABLE_TABLE_TK_ANOMALY_TASK"]

    tok = req(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    if tok.get("code") != 0:
        print("token fail", tok)
        return 1
    token = tok["tenant_access_token"]

    flist = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{tid}/fields?page_size=100",
        token=token,
    )
    if flist.get("code") != 0:
        print("list fields fail", flist)
        return 1

    fields = {(f.get("field_name") or ""): f for f in (flist.get("data") or {}).get("items") or []}
    for name in ("异常类型", "对象类型", "状态"):
        f = fields.get(name)
        if not f:
            print(f"MISSING field {name}")
            continue
        opts = ((f.get("property") or {}).get("options")) or []
        print(name, "type=", f.get("type"), "field_id=", f.get("field_id"))
        print("  current:", [o.get("name") for o in opts])

    targets = {
        "异常类型": NEED_TYPE,
        "对象类型": NEED_OBJ,
    }
    for fname, need in targets.items():
        f = fields.get(fname)
        if not f:
            continue
        if f.get("type") != 3:
            print(f"skip {fname}: not single-select type={f.get('type')}")
            continue
        opts = list(((f.get("property") or {}).get("options")) or [])
        have = {o.get("name") for o in opts}
        missing = [n for n in need if n not in have]
        if not missing:
            print(f"OK {fname}: no missing options")
            continue
        # 追加缺失选项（保留原有 id/color）
        new_opts = opts + [{"name": n} for n in missing]
        body = {
            "field_name": fname,
            "type": 3,
            "property": {"options": new_opts},
        }
        r = req(
            "PUT",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{tid}/fields/{f['field_id']}",
            body,
            token,
        )
        if r.get("code") == 0:
            print(f"UPDATED {fname} +{missing}")
        else:
            print(f"FAIL update {fname}", r)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
