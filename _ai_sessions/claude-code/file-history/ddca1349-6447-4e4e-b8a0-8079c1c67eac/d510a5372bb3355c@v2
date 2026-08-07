#!/usr/bin/env python3
"""Dump one SKU report row field union + shop-level attempts for mapping."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import time
import urllib.parse
import urllib.request


def env(n, d=""):
    return (os.environ.get(n) or d).strip()


def token(base, cid, sec):
    q = urllib.parse.urlencode(
        {"client_id": cid, "client_secret": sec, "grant_type": "client_credentials"}
    )
    with urllib.request.urlopen(f"{base}/api/oauth/v2/token.json?{q}", timeout=25) as r:
        body = json.loads(r.read().decode())
    assert body.get("code") == 0, body
    return body["data"]["access_token"]


def post(base, path, cid, sec, tok, payload):
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
    req = urllib.request.Request(
        f"{base}{path}?{query}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    base = env("SELLFOX_BASE_URL", "https://openapi.sellfox.com").rstrip("/")
    cid, sec = env("SELLFOX_CLIENT_ID"), env("SELLFOX_CLIENT_SECRET")
    tok = token(base, cid, sec)
    start, end = "2026-07-07", "2026-08-05"

    # full sku page 1
    resp = post(
        base,
        "/api/financial/tkReport/queryPageSku.json",
        cid,
        sec,
        tok,
        {
            "startDate": start,
            "endDate": end,
            "pageNum": "1",
            "pageSize": "50",
            "currency": "",
        },
    )
    print("sku code", resp.get("code"), resp.get("msg"))
    data = resp.get("data") or {}
    rows = data.get("rows") or []
    print("total", data.get("totalSize"), "page_rows", len(rows))
    keys = set()
    shops = {}
    for r in rows:
        if isinstance(r, dict):
            keys.update(r.keys())
            sid = str(r.get("shopId") or r.get("shop_id") or "")
            sname = str(r.get("shopName") or r.get("shop_name") or "")
            shops.setdefault(f"{sid}|{sname}", 0)
            shops[f"{sid}|{sname}"] += 1
    print("field_union", sorted(keys))
    print("shops", shops)
    if rows:
        # print one full row compact
        print("sample0", json.dumps(rows[0], ensure_ascii=False)[:2000])

    # msku
    time.sleep(1.2)
    resp2 = post(
        base,
        "/api/financial/tkReport/queryPageMsku.json",
        cid,
        sec,
        tok,
        {
            "startDate": start,
            "endDate": end,
            "pageNum": "1",
            "pageSize": "20",
            "currency": "",
        },
    )
    print("\nmsku code", resp2.get("code"), resp2.get("msg"))
    d2 = resp2.get("data") or {}
    rows2 = d2.get("rows") or []
    print("msku total", d2.get("totalSize"), "rows", len(rows2))
    if rows2 and isinstance(rows2[0], dict):
        print("msku keys", sorted(rows2[0].keys())[:40])
        print("msku sample", json.dumps(rows2[0], ensure_ascii=False)[:1200])

    # shop report without shopIds
    time.sleep(1.2)
    resp3 = post(
        base,
        "/api/financial/tkReport/queryPageShop.json",
        cid,
        sec,
        tok,
        {
            "startDate": start,
            "endDate": end,
            "pageNum": "1",
            "pageSize": "50",
            "currency": "",
        },
    )
    print("\nshop_report code", resp3.get("code"), resp3.get("msg"))
    d3 = resp3.get("data") or {}
    rows3 = d3.get("rows") or []
    print("shop total", d3.get("totalSize"), "rows", len(rows3))
    if rows3 and isinstance(rows3[0], dict):
        print("shop keys", sorted(rows3[0].keys())[:40])
        for r in rows3[:10]:
            print(
                " ",
                r.get("shopId"),
                r.get("shopName"),
                r.get("grossSalesAmount"),
                r.get("settlementAmount"),
                r.get("currency"),
            )

    # statement with timeSearchField
    time.sleep(1.2)
    for tsf in ("statementTime", "orderTime", "settleTime", "1", "statement_time"):
        resp4 = post(
            base,
            "/api/financial/tkReport/queryStatementDetail.json",
            cid,
            sec,
            tok,
            {
                "startDate": start,
                "endDate": end,
                "pageNo": 1,
                "pageSize": 5,
                "currency": "",
                "timeSearchField": tsf,
            },
        )
        print("statement", tsf, "code", resp4.get("code"), "msg", resp4.get("msg"))
        d4 = resp4.get("data") or {}
        rows4 = d4.get("rows") or d4.get("list") or []
        if resp4.get("code") == 0:
            print("  total", d4.get("totalSize"), "rows", len(rows4))
            if rows4 and isinstance(rows4[0], dict):
                print("  keys", sorted(rows4[0].keys())[:30])
                print("  sample", json.dumps(rows4[0], ensure_ascii=False)[:800])
            break
        time.sleep(1.0)

    # products shop parent no shop, updateDate, page str
    time.sleep(1.5)
    resp5 = post(
        base,
        "/api/multiplatform/tiktok/shop/product/getParentPageList.json",
        cid,
        sec,
        tok,
        {
            "pageNo": "1",
            "pageSize": "20",
            "dateType": "updateDate",
            "startDate": start,
            "endDate": end,
        },
    )
    print("\nshop_parent code", resp5.get("code"), resp5.get("msg"))
    d5 = resp5.get("data") or {}
    rows5 = d5.get("rows") or []
    print("product total", d5.get("totalSize"), "rows", len(rows5))
    if rows5 and isinstance(rows5[0], dict):
        print("product keys", sorted(rows5[0].keys()))
        shops_p = {}
        for r in rows5:
            shops_p[str(r.get("shopId")) + "|" + str(r.get("shopName"))] = shops_p.get(
                str(r.get("shopId")) + "|" + str(r.get("shopName")), 0
            ) + 1
        print("product shops", shops_p)
        print("sample", json.dumps(rows5[0], ensure_ascii=False)[:1000])


if __name__ == "__main__":
    main()
