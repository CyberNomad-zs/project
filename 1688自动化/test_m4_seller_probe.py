# -*- coding: utf-8 -*-
"""M4 卖家侧深探：切换卖家身份 → 找发布入口 → 深挖 SDK 实例 → 抓方案页线索。

用法:
  .venv-m4\\Scripts\\python.exe test_m4_seller_probe.py
  .venv-m4\\Scripts\\python.exe test_m4_seller_probe.py --headed
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import Page

from src.publish.probe import INTERESTING_URL_RE, SDK_CDN, APP_KEY, APP_NAME, _brief_headers
from src.publish.session import COOKIE_PATH, ROOT, browser_session, is_logged_in_url, save_cookies

OUT = ROOT / "output" / "_m4"
OUT.mkdir(parents=True, exist_ok=True)

SELLER_CANDIDATES = [
    "https://work.1688.com/home/seller.htm",
    "https://work.1688.com/?_path_=sellerBase/2017sellerbase_home/home",
    "https://work.1688.com/?_path_=sellerBase/sellerbase_home/home",
    "https://seller.1688.com/",
    "https://jywork.1688.com/",
    "https://air.1688.com/app/1688-global/main-site-product-manage/work.htm#/",
    "https://air.1688.com/app/1688-global/main-site-product-manage/work.htm",
    "https://offer.1688.com/offer/manage.htm",
    "https://offer.1688.com/page/offer_manage.htm",
    "https://publish.1688.com/offer/publish.htm",
    "https://sale.1688.com/sale/offer/post/choose_category.htm",
    "https://sale.1688.com/sale/offer/post/fill_product_info.htm",
    "https://fenxiao.1688.com/",
    # 诚信通 / 卖家中心常见
    "https://winport.1688.com/",
    "https://member.1688.com/member/manage_member_info.htm",
]


def attach_sniffer(page: Page, bucket: list) -> None:
    def on_req(req):
        if INTERESTING_URL_RE.search(req.url) or re.search(
            r"seller|publish|offer|product|schema|photobank|category", req.url, re.I
        ):
            bucket.append(
                {
                    "phase": "request",
                    "method": req.method,
                    "url": req.url[:400],
                    "type": req.resource_type,
                }
            )

    def on_resp(resp):
        url = resp.url
        if INTERESTING_URL_RE.search(url) or re.search(
            r"seller|publish|offer|schema|photobank|category|product", url, re.I
        ):
            item = {
                "phase": "response",
                "status": resp.status,
                "url": url[:400],
                "ct": (resp.headers or {}).get("content-type", "")[:80],
            }
            bucket.append(item)

    page.on("request", on_req)
    page.on("response", on_resp)


def page_identity(page: Page) -> dict:
    return page.evaluate(
        """() => {
          const text = (document.body && document.body.innerText || '').slice(0, 1500);
          const title = document.title;
          const isBuyer = /买家工作台/.test(text + title) || /买家工作台/.test(document.body ? document.body.innerHTML.slice(0,5000) : '');
          const isSeller = /卖家工作台|商家工作台|供应商工作台|我是卖家/.test(text + title);
          // 顶部切换按钮
          const switchBtns = Array.from(document.querySelectorAll('a,button,span,div'))
            .filter(el => /切换为卖家|切换为买家|卖家中心|进入卖家/.test((el.innerText||'').trim()))
            .slice(0, 10)
            .map(el => ({
              tag: el.tagName,
              text: (el.innerText||'').trim().slice(0,40),
              href: el.href || el.getAttribute('href') || null,
            }));
          const userBits = Array.from(document.querySelectorAll('[class*="user"],[class*="account"],[class*="nick"]'))
            .map(el => (el.innerText||'').trim())
            .filter(Boolean)
            .slice(0, 8);
          return {
            url: location.href,
            title,
            isBuyer, isSeller,
            switchBtns,
            userBits,
            textHead: text.slice(0, 400),
          };
        }"""
    )


def try_switch_to_seller(page: Page) -> dict:
    """点击「切换为卖家」或导航到卖家工作台。"""
    result: dict[str, Any] = {"tried": []}
    id0 = page_identity(page)
    result["before"] = {
        "url": id0["url"],
        "title": id0["title"],
        "isBuyer": id0["isBuyer"],
        "isSeller": id0["isSeller"],
        "switchBtns": id0["switchBtns"],
    }
    if id0.get("isSeller") and not id0.get("isBuyer"):
        result["already_seller"] = True
        return result

    # 1) 点「切换为卖家」
    selectors = [
        "text=切换为卖家",
        "a:has-text('切换为卖家')",
        "button:has-text('切换为卖家')",
        "[class*='switch']:has-text('卖家')",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            if not loc.is_visible(timeout=1500):
                continue
            result["tried"].append({"click": sel})
            loc.click(timeout=5000)
            page.wait_for_timeout(4000)
            break
        except Exception as e:  # noqa: BLE001
            result["tried"].append({"click": sel, "error": str(e)[:120]})

    id1 = page_identity(page)
    result["after_click"] = {
        "url": id1["url"],
        "title": id1["title"],
        "isBuyer": id1["isBuyer"],
        "isSeller": id1["isSeller"],
        "switchBtns": id1["switchBtns"],
        "textHead": id1.get("textHead"),
    }

    # 2) 若仍是买家，试卖家候选 URL
    if id1.get("isBuyer") or not id1.get("isSeller"):
        for url in SELLER_CANDIDATES[:8]:
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)
                idn = page_identity(page)
                entry = {
                    "url": url,
                    "status": resp.status if resp else None,
                    "final_url": page.url,
                    "title": page.title(),
                    "isBuyer": idn["isBuyer"],
                    "isSeller": idn["isSeller"],
                    "textHead": (idn.get("textHead") or "")[:200],
                }
                result.setdefault("seller_url_tries", []).append(entry)
                if idn.get("isSeller") and not idn.get("isBuyer"):
                    result["seller_reached_via"] = url
                    break
                # 有商品管理/发布字样也算有价值
                if re.search(r"发布商品|商品管理|offer|卖家工作台", idn.get("textHead") or "" + page.title()):
                    result.setdefault("interesting_pages", []).append(entry)
            except Exception as e:  # noqa: BLE001
                result.setdefault("seller_url_tries", []).append(
                    {"url": url, "error": str(e)[:160]}
                )

    result["final"] = page_identity(page)
    return result


def deep_sdk_inspect(page: Page) -> dict:
    """注入 SDK 并用 getSdkInstance 深挖 pcAlgorithmSdk。"""
    out: dict[str, Any] = {}
    try:
        page.evaluate(
            """({appKey, appName}) => {
              window.__1688_OPEN_SDK_CONFIG = { appKey, appName };
            }""",
            {"appKey": APP_KEY, "appName": APP_NAME},
        )
        # 若尚未加载则注入
        has = page.evaluate("() => typeof window.__1688_OPEN_SDK")
        if has == "undefined":
            page.add_script_tag(url=SDK_CDN)
            page.wait_for_timeout(2500)
        out["sdk_type"] = page.evaluate("() => typeof window.__1688_OPEN_SDK")
        out["detail"] = page.evaluate(
            """async () => {
              const r = { steps: [] };
              const sdk = window.__1688_OPEN_SDK;
              if (!sdk) { r.error = 'no_sdk'; return r; }
              r.keys = Object.keys(sdk);
              r.proto = Object.getOwnPropertyNames(Object.getPrototypeOf(sdk) || {}).slice(0, 30);

              // load
              try {
                const loaded = await Promise.race([
                  Promise.resolve(sdk.load({ sdkNameList: ['pcAlgorithmSdk'] })),
                  new Promise((_, rej) => setTimeout(() => rej(new Error('load_timeout')), 8000)),
                ]);
                r.loadResultType = typeof loaded;
                r.loadIsArray = Array.isArray(loaded);
                r.loadKeys = loaded && typeof loaded === 'object' ? Object.keys(loaded) : null;
                r.load0Type = loaded && loaded[0] !== undefined ? typeof loaded[0] : null;
                if (loaded && loaded[0] && typeof loaded[0] === 'object') {
                  r.load0Keys = Object.keys(loaded[0]).slice(0, 50);
                  // 尝试常见方法名
                  const methods = {};
                  for (const k of Object.keys(loaded[0])) {
                    methods[k] = typeof loaded[0][k];
                  }
                  r.load0Methods = methods;
                }
                r.steps.push('load_ok');
              } catch (e) {
                r.loadError = String(e);
                r.steps.push('load_fail');
              }

              // getSdkInstance
              try {
                if (typeof sdk.getSdkInstance === 'function') {
                  const inst = sdk.getSdkInstance('pcAlgorithmSdk');
                  r.instType = typeof inst;
                  if (inst && typeof inst === 'object') {
                    r.instKeys = Object.keys(inst).slice(0, 50);
                    const methods = {};
                    for (const k of Object.keys(inst)) methods[k] = typeof inst[k];
                    r.instMethods = methods;
                    // 也扫 prototype
                    try {
                      r.instProto = Object.getOwnPropertyNames(Object.getPrototypeOf(inst)||{}).slice(0,40);
                    } catch(e) {}
                  } else {
                    r.instValue = String(inst);
                  }
                  r.steps.push('getSdkInstance_ok');
                } else {
                  r.steps.push('no_getSdkInstance');
                }
              } catch (e) {
                r.instError = String(e);
                r.steps.push('getSdkInstance_fail');
              }

              // 全局
              r.globals = {
                pcAlgorithmSdk: typeof window.pcAlgorithmSdk,
                '@alife/1688-open-sdk': typeof window['@alife/1688-open-sdk'],
                PcAlgorithmDebug: typeof window.PcAlgorithmDebug,
              };
              // map
              try {
                r.mapKeys = sdk._sdkInstanceMap ? Object.keys(sdk._sdkInstanceMap) : null;
                if (sdk._sdkInstanceMap) {
                  const mk = {};
                  for (const k of Object.keys(sdk._sdkInstanceMap)) {
                    const v = sdk._sdkInstanceMap[k];
                    mk[k] = { type: typeof v, keys: v && typeof v==='object' ? Object.keys(v).slice(0,30) : null };
                  }
                  r.mapDetail = mk;
                }
              } catch (e) { r.mapError = String(e); }

              return r;
            }"""
        )
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    return out


def scrape_solution_page(page: Page) -> dict:
    """抓开放平台方案页可见文案与链接（API 列表线索）。"""
    url = "https://open.1688.com/solution/solutionDetail.htm?solutionKey=1671675923686"
    out: dict[str, Any] = {"url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        out["final_url"] = page.url
        out["title"] = page.title()
        out["logged_in"] = is_logged_in_url(page.url, page.title())
        # 点各个 tab
        tabs = ["方案概述", "技术方案", "如何接入", "开发人员参考", "API及消息列表", "SDK下载", "API", "消息"]
        tab_results = []
        for t in tabs:
            try:
                loc = page.locator(f"text={t}").first
                if loc.count() and loc.is_visible(timeout=1000):
                    loc.click(timeout=3000)
                    page.wait_for_timeout(1500)
                    text = page.evaluate(
                        "() => (document.body && document.body.innerText || '').slice(0, 4000)"
                    )
                    tab_results.append({"tab": t, "text_head": text[:2000]})
            except Exception as e:  # noqa: BLE001
                tab_results.append({"tab": t, "error": str(e)[:100]})
        out["tabs"] = tab_results
        # 所有链接
        out["links"] = page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]'))
              .map(a => ({text: (a.innerText||'').trim().slice(0,60), href: a.href}))
              .filter(x => /api|sdk|schema|文档|开发|接入|消息|商品|图片|视频|发布/i.test(x.text+' '+x.href))
              .slice(0, 60)"""
        )
        page.screenshot(path=str(OUT / "solution_page.png"), full_page=False)
        # 再抓整页文本关键字
        full = page.evaluate(
            "() => (document.body && document.body.innerText || '').slice(0, 8000)"
        )
        out["keyword_hits"] = sorted(
            set(
                re.findall(
                    r"(pcAlgorithmSdk|alife-open-sdk|Schema|product\.publish|photobank|图片银行|类目|发布商品|alibaba\.[a-zA-Z0-9.]+|com\.alibaba\.[a-zA-Z0-9.]+)",
                    full,
                    flags=re.I,
                )
            )
        )
        out["text_head"] = full[:1500]
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    return out


def collect_nav(page: Page) -> list:
    return page.evaluate(
        """() => {
          const anchors = Array.from(document.querySelectorAll('a[href]'));
          const hit = [];
          for (const a of anchors) {
            const t = (a.innerText || '').trim().replace(/\\s+/g,' ');
            const href = a.href || '';
            if (!href || href.startsWith('javascript')) continue;
            if (/发布|商品|管理|offer|publish|product|卖家|工作台|相册|图片|视频|类目/i.test(t+' '+href)) {
              hit.push({text: t.slice(0,50), href: href.slice(0,250)});
            }
            if (hit.length >= 50) break;
          }
          return hit;
        }"""
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    report: dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "headless": not args.headed,
    }
    network: list = []

    with browser_session(headless=not args.headed, cookie_path=COOKIE_PATH) as page:
        attach_sniffer(page, network)

        page.goto(
            "https://work.1688.com/home/page/index.htm",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(3000)
        report["home_identity"] = page_identity(page)
        page.screenshot(path=str(OUT / "seller_probe_home.png"), full_page=False)

        report["switch"] = try_switch_to_seller(page)
        page.screenshot(path=str(OUT / "seller_probe_after_switch.png"), full_page=False)

        # 保存切换后可能新增的 cookie
        try:
            # browser_session 内部 page.context
            cookies = page.context.cookies()
            save_cookies(cookies, COOKIE_PATH)
            report["cookie_saved"] = len(cookies)
        except Exception as e:  # noqa: BLE001
            report["cookie_saved_error"] = str(e)

        report["nav_after_switch"] = collect_nav(page)
        report["sdk_deep"] = deep_sdk_inspect(page)
        page.screenshot(path=str(OUT / "seller_probe_sdk.png"), full_page=False)

        # 在当前页若已是卖家，再点发布类链接
        publish_hits = []
        for link in report.get("nav_after_switch") or []:
            href = link.get("href") or ""
            text = link.get("text") or ""
            if re.search(r"发布商品|商品管理|发布|新品发布", text) or re.search(
                r"publish|offer.*manage|product-manage|fill_product", href, re.I
            ):
                publish_hits.append(link)
        report["publish_link_candidates"] = publish_hits[:20]

        for i, link in enumerate(publish_hits[:5]):
            href = link["href"]
            try:
                resp = page.goto(href, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
                inv = page_identity(page)
                entry = {
                    "from": link,
                    "status": resp.status if resp else None,
                    "final_url": page.url,
                    "title": page.title(),
                    "identity": inv,
                    "sdk": deep_sdk_inspect(page),
                }
                safe = re.sub(r"[^a-zA-Z0-9]+", "_", urlparse(href).path or "p")[:30]
                page.screenshot(path=str(OUT / f"publish_cand_{i}_{safe}.png"), full_page=False)
                report.setdefault("publish_pages", []).append(entry)
            except Exception as e:  # noqa: BLE001
                report.setdefault("publish_pages", []).append(
                    {"from": link, "error": str(e)[:160]}
                )

        # 方案页
        report["solution"] = scrape_solution_page(page)

        # 再扫一遍剩余卖家候选（若还没到卖家）
        final_id = page_identity(page)
        if final_id.get("isBuyer") or not final_id.get("isSeller"):
            more = []
            for url in SELLER_CANDIDATES:
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=40000)
                    page.wait_for_timeout(2000)
                    idn = page_identity(page)
                    more.append(
                        {
                            "url": url,
                            "status": resp.status if resp else None,
                            "final_url": page.url,
                            "title": page.title()[:80],
                            "isBuyer": idn["isBuyer"],
                            "isSeller": idn["isSeller"],
                            "textHead": (idn.get("textHead") or "")[:180],
                        }
                    )
                except Exception as e:  # noqa: BLE001
                    more.append({"url": url, "error": str(e)[:120]})
            report["all_seller_url_scan"] = more

    report["network_count"] = len(network)
    report["network_sample"] = network[:150]
    # 启发式
    report["summary"] = {
        "home_is_buyer": (report.get("home_identity") or {}).get("isBuyer"),
        "switched_seller": (report.get("switch") or {}).get("final", {}).get("isSeller"),
        "sdk_steps": ((report.get("sdk_deep") or {}).get("detail") or {}).get("steps"),
        "sdk_inst_keys": ((report.get("sdk_deep") or {}).get("detail") or {}).get("instKeys"),
        "sdk_load0_keys": ((report.get("sdk_deep") or {}).get("detail") or {}).get("load0Keys"),
        "map_keys": ((report.get("sdk_deep") or {}).get("detail") or {}).get("mapKeys"),
        "solution_keywords": (report.get("solution") or {}).get("keyword_hits"),
        "publish_candidates": len(report.get("publish_link_candidates") or []),
    }

    path = OUT / "seller_probe_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print("\nswitch.final:", json.dumps((report.get("switch") or {}).get("final"), ensure_ascii=False, indent=2)[:800])
    print("\nsdk_deep.detail keys sample:")
    d = (report.get("sdk_deep") or {}).get("detail") or {}
    print(json.dumps({k: d.get(k) for k in ("steps", "keys", "load0Keys", "load0Methods", "instKeys", "instMethods", "mapKeys", "mapDetail", "loadError", "instError", "globals")}, ensure_ascii=False, indent=2)[:4000])
    print("\nsolution keywords:", report["summary"].get("solution_keywords"))
    print("report:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
