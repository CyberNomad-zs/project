# -*- coding: utf-8 -*-
"""Diagnose Feishu 1254060 TextFieldConvFail when cloning records."""
from __future__ import annotations

import json
import time
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


def req(method: str, url: str, body=None, token: str | None = None, retries: int = 4) -> dict:
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last = None
    for attempt in range(retries):
        r = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(r, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"code": e.code, "msg": raw[:500]}
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.2 * (attempt + 1))
    return {"code": -1, "msg": str(last)}


def main() -> int:
    env = load_env()
    src_id, src_sec = env["FEISHU_APP_ID"], env["FEISHU_APP_SECRET"]
    src_base = env.get("FEISHU_BITABLE_APP_TOKEN_TK") or env["FEISHU_BITABLE_APP_TOKEN"]
    dst_id = "cli_aaf3f14a863bdbc3"
    dst_sec = "psfflrGx8grE1k3Op4aOQfQ6VJcSrAcS"
    dst_base = "Tcb0bPY3baO2TTsaXqpcWF2enfb"
    src_tid = env.get("FEISHU_BITABLE_TABLE_TK_SHOP_DAILY") or "tblwh7EVeAFPfvuy"
    dst_tid = "tblX6kM4qfQbnufm"

    ts = req(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": src_id, "app_secret": src_sec},
    )
    print("src_token", ts.get("code"))
    st = ts["tenant_access_token"]
    td = req(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": dst_id, "app_secret": dst_sec},
    )
    print("dst_token", td.get("code"))
    dt = td["tenant_access_token"]

    fr = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{src_base}/tables/{src_tid}/fields?page_size=100",
        token=st,
    )
    ftypes = {
        f["field_name"]: f.get("type")
        for f in (fr.get("data") or {}).get("items") or []
    }
    print("src_field_types", ftypes)

    df = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{dst_base}/tables/{dst_tid}/fields?page_size=100",
        token=dt,
    )
    dtypes = {
        f["field_name"]: f.get("type")
        for f in (df.get("data") or {}).get("items") or []
    }
    print("dst_field_types", dtypes)

    rr = req(
        "GET",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{src_base}/tables/{src_tid}/records?page_size=1",
        token=st,
    )
    items = (rr.get("data") or {}).get("items") or []
    if not items:
        print("no source records")
        return 1
    fields = items[0].get("fields") or {}
    print("sample_record_keys", list(fields.keys()))
    for k, v in fields.items():
        print(f"  {k} type={type(v).__name__} val={json.dumps(v, ensure_ascii=False)[:180]}")

    # per-field write test
    bad = []
    ok = []
    for k, v in fields.items():
        w = req(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{dst_base}/tables/{dst_tid}/records",
            {"fields": {k: v}},
            token=dt,
        )
        if w.get("code") == 0:
            ok.append(k)
            rid = ((w.get("data") or {}).get("record") or {}).get("record_id")
            if rid:
                req(
                    "DELETE",
                    f"https://open.feishu.cn/open-apis/bitable/v1/apps/{dst_base}/tables/{dst_tid}/records/{rid}",
                    token=dt,
                )
        else:
            bad.append((k, type(v).__name__, json.dumps(v, ensure_ascii=False)[:120], w.get("code"), w.get("msg")))
        time.sleep(0.2)

    print("OK_FIELDS", ok)
    print("BAD_FIELDS")
    for b in bad:
        print(" ", b)

    # try sanitize text segments
    def sanitize(v):
        if isinstance(v, list) and v and isinstance(v[0], dict) and "text" in v[0]:
            return "".join(str(x.get("text") or "") for x in v)
        if isinstance(v, dict) and "text" in v and "type" not in v:
            # single select sometimes {id,text}
            return v.get("text")
        if isinstance(v, dict) and "id" in v and "text" in v:
            return v.get("text")
        if isinstance(v, list) and v and isinstance(v[0], dict) and "text" in v[0] and "id" in v[0]:
            # multi select
            return [x.get("text") for x in v if x.get("text")]
        return v

    cleaned = {k: sanitize(v) for k, v in fields.items()}
    print("cleaned_sample")
    for k, v in cleaned.items():
        print(f"  {k}: {type(v).__name__}={json.dumps(v, ensure_ascii=False)[:120]}")
    w = req(
        "POST",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{dst_base}/tables/{dst_tid}/records",
        {"fields": cleaned},
        token=dt,
    )
    print("WRITE_CLEANED", w.get("code"), w.get("msg"))
    if w.get("code") == 0:
        rid = ((w.get("data") or {}).get("record") or {}).get("record_id")
        if rid:
            req(
                "DELETE",
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{dst_base}/tables/{dst_tid}/records/{rid}",
                token=dt,
            )
            print("deleted test record", rid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
