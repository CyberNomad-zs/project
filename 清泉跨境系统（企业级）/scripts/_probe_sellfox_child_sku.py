#!/usr/bin/env python3
"""Probe Sellfox TK getChildInfo for seller_sku fields. Run on server with SELLFOX_* env.

Usage:
  set -a; source /opt/qingquan/.env; set +a
  python3 /tmp/_probe_sellfox_child_sku.py
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, timedelta


def env(n: str, d: str = "") -> str:
    return (os.environ.get(n) or d).strip()


def token(base: str, cid: str, sec: str) -> str:
    q = urllib.parse.urlencode(
        {"client_id": cid, "client_secret": sec, "grant_type": "client_credentials"}
    )
    with urllib.request.urlopen(f"{base}/api/oauth/v2/token.json?{q}", timeout=25) as r:
        body = json.loads(r.read().decode())
    if body.get("code") != 0:
        raise SystemExit(f"token fail: {body}")
    return body["data"]["access_token"]


def post(base: str, path: str, cid: str, sec: str, tok: str, payload: dict) -> dict:
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
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return {"http_status": e.code, "raw": raw[:800]}


def walk_keys(obj, prefix="", out=None, depth=0):
    if out is None:
        out = Counter()
    if depth > 6:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out[p] += 1
            walk_keys(v, p, out, depth + 1)
    elif isinstance(obj, list) and obj:
        walk_keys(obj[0], prefix + "[]", out, depth + 1)
    return out


SKU_KEY_RE = re.compile(r"(sku|msku|seller)", re.I)


def extract_sku_candidates(obj, path="", found=None, depth=0):
    if found is None:
        found = []
    if depth > 8:
        return found
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if SKU_KEY_RE.search(str(k)):
                if isinstance(v, (str, int, float)) and str(v).strip():
                    found.append((p, str(v)[:200]))
                elif isinstance(v, list) and v and all(isinstance(x, (str, int, float)) for x in v[:5]):
                    found.append((p, json.dumps(v[:10], ensure_ascii=False)[:300]))
            extract_sku_candidates(v, p, found, depth + 1)
    elif isinstance(obj, list):
        for i, it in enumerate(obj[:20]):
            extract_sku_candidates(it, f"{path}[{i}]", found, depth + 1)
    return found


def main() -> None:
    base = env("SELLFOX_BASE_URL", "https://openapi.sellfox.com").rstrip("/")
    cid, sec = env("SELLFOX_CLIENT_ID"), env("SELLFOX_CLIENT_SECRET")
    if not cid or not sec:
        raise SystemExit("missing SELLFOX_CLIENT_ID/SECRET")
    tok = token(base, cid, sec)
    print("token=ok base=", base)

    end = date.today()
    start = end - timedelta(days=29)
    parent_path = "/api/multiplatform/tiktok/shop/product/getParentPageList.json"
    child_path = "/api/multiplatform/tiktok/shop/product/getChildInfo.json"
    # also try global / fullyManaged variants if shop path thin
    child_alts = [
        child_path,
        "/api/multiplatform/tiktok/global/product/getChildInfo.json",
        "/api/multiplatform/tiktok/fullyManaged/product/getChildInfo.json",
    ]

    resp = post(
        base,
        parent_path,
        cid,
        sec,
        tok,
        {
            "pageNo": "1",
            "pageSize": "30",
            "dateType": "updateDate",
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        },
    )
    print("parent code=", resp.get("code"), "msg=", resp.get("msg"))
    data = resp.get("data") or {}
    rows = data.get("rows") or data.get("list") or []
    print("parent total=", data.get("totalSize"), "rows=", len(rows))
    if not rows:
        print("no parent rows; abort")
        return

    # shop distribution
    shops = Counter()
    for r in rows:
        shops[f"{r.get('shopId')}|{r.get('shopName')}"] += 1
    print("parent shops", dict(shops))
    print("parent sample keys", sorted(rows[0].keys()) if isinstance(rows[0], dict) else type(rows[0]))
    print("parent sample", json.dumps(rows[0], ensure_ascii=False)[:1200])

    parents = []
    for r in rows:
        pid = r.get("parentId") or r.get("id")
        if pid:
            parents.append(
                {
                    "parentId": str(pid),
                    "productId": str(r.get("productId") or ""),
                    "shopId": str(r.get("shopId") or ""),
                    "shopName": str(r.get("shopName") or ""),
                    "productName": str(r.get("productName") or "")[:80],
                }
            )
    # unique parentIds, take up to 8
    seen = set()
    uniq = []
    for p in parents:
        if p["parentId"] in seen:
            continue
        seen.add(p["parentId"])
        uniq.append(p)
        if len(uniq) >= 8:
            break

    key_union = Counter()
    sku_hits = Counter()
    for i, p in enumerate(uniq):
        time.sleep(1.25)
        print(f"\n--- child #{i+1} parentId={p['parentId']} productId={p['productId']} shop={p['shopId']}|{p['shopName']} ---")
        body_variants = [
            {"parentId": p["parentId"]},
            {"parentId": str(p["parentId"])},
            {"parent_id": p["parentId"]},
            {"id": p["parentId"]},
            {"productId": p["productId"]} if p["productId"] else None,
        ]
        ok = False
        for path in child_alts:
            for bv in body_variants:
                if not bv:
                    continue
                time.sleep(0.3)
                cr = post(base, path, cid, sec, tok, bv)
                code = cr.get("code")
                if code != 0:
                    # only log first fail per path
                    if bv is body_variants[0]:
                        print(f"  path={path} body={list(bv.keys())} code={code} msg={cr.get('msg')}")
                    continue
                print(f"  OK path={path} body_keys={list(bv.keys())}")
                print(f"  data_type={type(cr.get('data')).__name__}")
                sample = json.dumps(cr.get("data"), ensure_ascii=False, default=str)
                print(f"  data_snip={sample[:1800]}")
                walk_keys(cr.get("data"), out=key_union)
                for path_k, val in extract_sku_candidates(cr.get("data")):
                    sku_hits[path_k] += 1
                    print(f"  SKU_FIELD {path_k} = {val}")
                ok = True
                break
            if ok:
                break
        if not ok:
            print("  ALL child variants failed")

    print("\n=== KEY UNION (first-level paths count) ===")
    for k, n in key_union.most_common(80):
        print(f"  {n:3d} {k}")
    print("\n=== SKU-like field hits ===")
    for k, n in sku_hits.most_common(40):
        print(f"  {n:3d} {k}")

    # bonus: try multiplatform order list lightly (may 404)
    time.sleep(1.2)
    order_paths = [
        "/api/order/getOrderList.json",
        "/api/order/pageList.json",
        "/api/multiplatform/order/getOrderPageList.json",
        "/api/multiplatform/order/pageList.json",
        "/api/package/getPackagePage.json",
    ]
    print("\n=== order-ish endpoints (smoke) ===")
    for op in order_paths:
        time.sleep(1.0)
        r = post(
            base,
            op,
            cid,
            sec,
            tok,
            {
                "pageNo": "1",
                "pageSize": "5",
                "pageNum": "1",
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
            },
        )
        print(f"  {op} code={r.get('code')} msg={str(r.get('msg') or r.get('raw') or '')[:120]}")
        if r.get("code") == 0:
            d = r.get("data") or {}
            rows_o = d.get("rows") or d.get("list") or []
            print(f"    total={d.get('totalSize')} rows={len(rows_o) if isinstance(rows_o, list) else '?'}")
            if isinstance(rows_o, list) and rows_o and isinstance(rows_o[0], dict):
                print(f"    keys={sorted(rows_o[0].keys())[:40]}")
                for pk, val in extract_sku_candidates(rows_o[0])[:15]:
                    print(f"    SKU_FIELD {pk}={val}")
                print(f"    sample={json.dumps(rows_o[0], ensure_ascii=False)[:900]}")


if __name__ == "__main__":
    main()
