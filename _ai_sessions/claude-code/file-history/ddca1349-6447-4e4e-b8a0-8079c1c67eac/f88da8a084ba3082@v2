#!/usr/bin/env python3
"""Sellfox TK probe variants on server — find working body shapes."""
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


def get_token(base: str, cid: str, sec: str):
    q = urllib.parse.urlencode(
        {"client_id": cid, "client_secret": sec, "grant_type": "client_credentials"}
    )
    with urllib.request.urlopen(f"{base}/api/oauth/v2/token.json?{q}", timeout=25) as r:
        body = json.loads(r.read().decode())
    if body.get("code") != 0:
        raise SystemExit(f"token fail: {body}")
    return body["data"]["access_token"]


def signed_post(base, path, cid, sec, tok, payload):
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
    body = json.dumps(payload, ensure_ascii=False).encode()
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
            return {"http_status": e.code, "raw": raw[:400]}


def show(label, resp, payload=None):
    data = resp.get("data")
    rows = []
    total = None
    if isinstance(data, dict):
        rows = data.get("rows") or data.get("list") or data.get("records") or []
        total = data.get("totalSize")
    elif isinstance(data, list):
        rows = data
    n = len(rows) if isinstance(rows, list) else "?"
    print(f"\n[{label}] code={resp.get('code')} msg={resp.get('msg')} rows={n} total={total}")
    if payload is not None:
        print("  payload=", json.dumps(payload, ensure_ascii=False)[:220])
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        r0 = rows[0]
        keys = sorted(r0.keys())
        print("  sample_keys=", keys[:28])
        for k in (
            "shopId",
            "shopName",
            "productId",
            "productName",
            "tkStatus",
            "parentId",
            "platformProductId",
            "grossSalesAmount",
            "settlementAmount",
            "grossProfit",
            "adsCost",
            "currency",
            "salesQuantity",
        ):
            if k in r0:
                v = r0[k]
                if isinstance(v, str) and len(v) > 70:
                    v = v[:70] + "…"
                print(f"   {k}={v}")


def main():
    base = env("SELLFOX_BASE_URL", "https://openapi.sellfox.com").rstrip("/")
    cid = env("SELLFOX_CLIENT_ID")
    sec = env("SELLFOX_CLIENT_SECRET")
    print("exit check via env host; client_id=", cid, "secret_len=", len(sec))
    tok = get_token(base, cid, sec)
    print("token=OK")

    shops = ["GBLCJGQ23Q", "GBLCAW729L", "HKGBCB8LQLRC"]
    start, end = "2026-07-07", "2026-08-05"

    cases = []

    # --- shop parent variants ---
    path_shop = "/api/multiplatform/tiktok/shop/product/getParentPageList.json"
    for name, body in [
        (
            "shop_parent_int_pages_str_shops",
            {
                "pageNo": 1,
                "pageSize": 10,
                "dateType": "createDate",
                "startDate": start,
                "endDate": end,
                "shopIdList": shops,
            },
        ),
        (
            "shop_parent_str_pages",
            {
                "pageNo": "1",
                "pageSize": "10",
                "dateType": "createDate",
                "startDate": start,
                "endDate": end,
                "shopIdList": shops,
            },
        ),
        (
            "shop_parent_no_shop",
            {
                "pageNo": 1,
                "pageSize": 10,
                "dateType": "createDate",
                "startDate": start,
                "endDate": end,
            },
        ),
        (
            "shop_parent_updateDate",
            {
                "pageNo": 1,
                "pageSize": 10,
                "dateType": "updateDate",
                "startDate": start,
                "endDate": end,
            },
        ),
        (
            "shop_parent_one_shop",
            {
                "pageNo": 1,
                "pageSize": 10,
                "dateType": "createDate",
                "startDate": start,
                "endDate": end,
                "shopIdList": ["GBLCJGQ23Q"],
            },
        ),
    ]:
        cases.append((name, path_shop, body))

    # --- global parent ---
    path_g = "/api/multiplatform/tiktok/global/product/getParentPageList.json"
    for name, body in [
        (
            "global_with_dates_no_shop",
            {
                "pageNo": 1,
                "pageSize": 10,
                "dateType": "createDate",
                "startDate": start,
                "endDate": end,
            },
        ),
        (
            "global_with_dates_shops",
            {
                "pageNo": 1,
                "pageSize": 10,
                "dateType": "createDate",
                "startDate": start,
                "endDate": end,
                "shopIdList": shops,
            },
        ),
        ("global_min", {"pageNo": 1, "pageSize": 10}),
    ]:
        cases.append((name, path_g, body))

    # --- fully managed ---
    path_f = "/api/multiplatform/tiktok/fullyManaged/product/getParentPageList.json"
    for name, body in [
        ("fm_min", {"pageNo": 1, "pageSize": 10}),
        (
            "fm_dates",
            {
                "pageNo": 1,
                "pageSize": 10,
                "dateType": "createDate",
                "startDate": start,
                "endDate": end,
            },
        ),
        (
            "fm_shops_str_page",
            {"pageNo": "1", "pageSize": "10", "shopIdList": shops},
        ),
    ]:
        cases.append((name, path_f, body))

    # --- report ---
    path_r = "/api/financial/tkReport/queryPageShop.json"
    for name, body in [
        (
            "report_str_shops",
            {
                "startDate": start,
                "endDate": end,
                "pageNum": "1",
                "pageSize": "10",
                "currency": "",
                "shopIds": shops,
            },
        ),
        (
            "report_no_shop",
            {
                "startDate": start,
                "endDate": end,
                "pageNum": "1",
                "pageSize": "10",
                "currency": "",
            },
        ),
        (
            "report_page_int",
            {
                "startDate": start,
                "endDate": end,
                "pageNum": 1,
                "pageSize": 10,
            },
        ),
        (
            "report_currency_GBP",
            {
                "startDate": start,
                "endDate": end,
                "pageNum": "1",
                "pageSize": "10",
                "currency": "GBP",
            },
        ),
        (
            "report_marketplace_UK",
            {
                "startDate": start,
                "endDate": end,
                "pageNum": "1",
                "pageSize": "10",
                "currency": "",
                "marketplaceCodes": ["UK"],
            },
        ),
    ]:
        cases.append((name, path_r, body))

    # --- sku report no shop ---
    path_sku = "/api/financial/tkReport/queryPageSku.json"
    cases.append(
        (
            "report_sku_no_shop",
            path_sku,
            {
                "startDate": start,
                "endDate": end,
                "pageNum": "1",
                "pageSize": "10",
                "currency": "",
            },
        )
    )

    # --- statement ---
    path_st = "/api/financial/tkReport/queryStatementDetail.json"
    cases.append(
        (
            "statement_no_shop",
            path_st,
            {
                "startDate": start,
                "endDate": end,
                "pageNo": 1,
                "pageSize": 10,
                "currency": "",
            },
        )
    )

    # --- temu product control (known working family on this app?) ---
    path_temu = "/api/multiplatform/temu/product/getParentPageList.json"
    cases.append(
        (
            "temu_control_whitelist",
            path_temu,
            {
                "pageNo": 1,
                "pageSize": 5,
                "dateType": "createDate",
                "startDate": "2024-01-01",
                "endDate": end,
                "shopIdList": ["396706", "398202", "398203"],
            },
        )
    )

    # --- channels control (auth/IP smoke) ---
    path_ch = "/api/packageShip/queryShipChannel.json"
    cases.append(("channels", path_ch, {"logisticsType": ["1"]}))

    ok_with_rows = []
    ok_empty = []
    fail = []

    for name, path, body in cases:
        resp = signed_post(base, path, cid, sec, tok, body)
        show(name, resp, body)
        if resp.get("code") == 0:
            data = resp.get("data")
            rows = []
            if isinstance(data, dict):
                rows = data.get("rows") or data.get("list") or data.get("records") or []
                if not rows and data.get("totalSize"):
                    rows = ["_nonzero_total"]
            elif isinstance(data, list):
                rows = data
            if rows:
                ok_with_rows.append(name)
            else:
                ok_empty.append(name)
        else:
            fail.append((name, resp.get("code"), resp.get("msg")))

    print("\n======== SUMMARY ========")
    print("OK_WITH_ROWS:", ok_with_rows or "none")
    print("OK_EMPTY:", ok_empty or "none")
    print("FAIL:")
    for n, c, m in fail:
        print(f"  {n}: code={c} msg={m}")

    if ok_with_rows:
        print("verdict=SERVER_CAN_READ_SOME_SELLFOX")
        return 0
    if ok_empty and not fail:
        print("verdict=ALL_OK_EMPTY")
        return 0
    if any(c == 40005 for _, c, _ in fail):
        print("verdict=IP_BLOCK")
        return 1
    print("verdict=NEED_PARAM_OR_MODULE")
    return 1


if __name__ == "__main__":
    sys.exit(main())
