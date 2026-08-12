#!/usr/bin/env python3
"""Run on qingquan server: probe Sellfox TK token + shop products + report.

Reads SELLFOX_* from environment (source /opt/qingquan/.env first).
Does not print secrets.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def get_token(base: str, cid: str, sec: str) -> tuple[str | None, dict]:
    q = urllib.parse.urlencode(
        {
            "client_id": cid,
            "client_secret": sec,
            "grant_type": "client_credentials",
        }
    )
    url = f"{base}/api/oauth/v2/token.json?{q}"
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            body = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"http_status": e.code, "raw": raw[:400]}
        return None, body
    except Exception as e:
        return None, {"exc": f"{type(e).__name__}: {e}"}
    tok = (body.get("data") or {}).get("access_token")
    return tok, body


def signed_post(base: str, path: str, cid: str, sec: str, tok: str, payload: dict) -> dict:
    ts = int(time.time() * 1000)
    nonce = random.randint(1, 99999)
    params = {
        "url": path,
        "method": "post",
        "access_token": tok,
        "client_id": cid,
        "timestamp": ts,
        "nonce": nonce,
    }
    data = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sign = hmac.new(sec.encode(), data.encode(), hashlib.sha256).hexdigest()
    query = urllib.parse.urlencode(
        {
            "access_token": tok,
            "client_id": cid,
            "timestamp": ts,
            "nonce": nonce,
            "sign": sign,
        }
    )
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base}{path}?{query}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return {"http_status": e.code, "raw": raw[:500]}
    except Exception as e:
        return {"exc": f"{type(e).__name__}: {e}"}


def summarize_rows(label: str, resp: dict) -> None:
    print(f"=== {label} ===")
    print(
        "code=",
        resp.get("code"),
        "msg=",
        resp.get("msg"),
        "requestId=",
        resp.get("requestId"),
        "http_status=",
        resp.get("http_status"),
        "exc=",
        resp.get("exc"),
    )
    data = resp.get("data")
    if not isinstance(data, dict):
        if data is not None:
            print("data_type=", type(data).__name__)
        return
    rows = data.get("rows") or data.get("list") or data.get("records") or []
    print(
        "row_count=",
        len(rows) if isinstance(rows, list) else "?",
        "totalSize=",
        data.get("totalSize"),
        "keys=",
        sorted(data.keys())[:20],
    )
    if isinstance(rows, list) and rows:
        r0 = rows[0]
        if isinstance(r0, dict):
            print("sample_keys=", sorted(r0.keys())[:30])
            for k in (
                "shopId",
                "shopName",
                "productId",
                "productName",
                "tkStatus",
                "parentId",
                "grossSalesAmount",
                "settlementAmount",
                "grossProfit",
                "adsCost",
                "currency",
            ):
                if k in r0:
                    v = r0[k]
                    if isinstance(v, str) and len(v) > 80:
                        v = v[:80] + "…"
                    print(f"  {k}={v}")


def main() -> int:
    base = env("SELLFOX_BASE_URL", "https://openapi.sellfox.com").rstrip("/")
    cid = env("SELLFOX_CLIENT_ID")
    sec = env("SELLFOX_CLIENT_SECRET")
    print("host_exit_ip_hint: run curl ifconfig.me separately")
    print("base=", base)
    print("client_id=", cid or "(empty)")
    print("client_secret_len=", len(sec))
    if not cid or not sec:
        print("FAIL: missing SELLFOX_CLIENT_ID or SELLFOX_CLIENT_SECRET")
        return 2

    tok, tbody = get_token(base, cid, sec)
    print(
        "token_code=",
        tbody.get("code"),
        "msg=",
        tbody.get("msg"),
        "has_token=",
        bool(tok),
        "http_status=",
        tbody.get("http_status"),
        "exc=",
        tbody.get("exc"),
    )
    if not tok:
        # common: IP whitelist sometimes surfaces oddly; dump safe keys
        print("token_body_keys=", sorted(k for k in tbody.keys()))
        return 1

    shops = ["GBLCJGQ23Q", "GBLCAW729L", "HKGBCB8LQLRC"]
    resp = signed_post(
        base,
        "/api/multiplatform/tiktok/shop/product/getParentPageList.json",
        cid,
        sec,
        tok,
        {
            "pageNo": 1,
            "pageSize": 5,
            "dateType": "createDate",
            "startDate": "2026-07-07",
            "endDate": "2026-08-05",
            "shopIdList": shops,
        },
    )
    summarize_rows("tiktok_shop_parent", resp)

    resp2 = signed_post(
        base,
        "/api/multiplatform/tiktok/global/product/getParentPageList.json",
        cid,
        sec,
        tok,
        {"pageNo": 1, "pageSize": 5, "shopIdList": shops},
    )
    summarize_rows("tiktok_global_parent", resp2)

    resp3 = signed_post(
        base,
        "/api/multiplatform/tiktok/fullyManaged/product/getParentPageList.json",
        cid,
        sec,
        tok,
        {"pageNo": 1, "pageSize": 5, "shopIdList": shops},
    )
    summarize_rows("tiktok_fully_managed_parent", resp3)

    resp4 = signed_post(
        base,
        "/api/financial/tkReport/queryPageShop.json",
        cid,
        sec,
        tok,
        {
            "startDate": "2026-07-07",
            "endDate": "2026-08-05",
            "pageNum": "1",
            "pageSize": "10",
            "currency": "",
            "shopIds": shops,
        },
    )
    summarize_rows("tiktok_report_shop", resp4)

    # light package probe (may be empty for TK)
    resp5 = signed_post(
        base,
        "/api/packageShip/v1/getPackagePage.json",
        cid,
        sec,
        tok,
        {
            "pageNo": "1",
            "pageSize": "5",
            "packageStatus": "to_process",
            "purchaseDateStart": "2026-07-07 00:00:00",
            "purchaseDateEnd": "2026-08-05 23:59:59",
            "shopIdList": shops,
        },
    )
    summarize_rows("package_to_process", resp5)

    ok_codes = []
    for label, r in (
        ("shop_parent", resp),
        ("global_parent", resp2),
        ("fully_managed", resp3),
        ("report", resp4),
        ("package", resp5),
    ):
        if r.get("code") == 0:
            ok_codes.append(label)
    print("=== summary ===")
    print("biz_ok=", ok_codes or "none")
    if resp.get("code") == 40005 or resp4.get("code") == 40005:
        print("verdict=IP_WHITELIST_BLOCK")
        return 1
    if any(
        (r.get("code") == 0)
        and isinstance(r.get("data"), dict)
        and (
            (r["data"].get("rows") or r["data"].get("list") or r["data"].get("totalSize") or 0)
        )
        for r in (resp, resp2, resp3, resp4)
    ):
        print("verdict=SELLFOX_TK_READ_OK")
        return 0
    if all(r.get("code") == 0 for r in (resp, resp2, resp3, resp4)):
        print("verdict=API_OK_BUT_EMPTY_ROWS")
        return 0
    print("verdict=PARTIAL_OR_FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
