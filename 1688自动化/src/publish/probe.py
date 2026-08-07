# -*- coding: utf-8 -*-
"""M4 · 发布页 / JS SDK 探针。

目标（进度记录优先级#1）：
1. 导航到卖家工作台与候选「发布商品/商品管理」页
2. 监听网络：alife-open-sdk / pcAlgorithmSdk / 开放平台相关请求
3. 尝试在已登录页面注入官方 JS SDK，观察 load 行为
4. 汇总证据，辅助判定发布模式：浏览器直发 vs SDK 出 token + 后端 API

本脚本只做只读探测，不提交商品。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from playwright.sync_api import Page, Request, Response

from .session import (
    COOKIE_PATH,
    DEFAULT_HOME,
    ROOT,
    browser_session,
    check_login,
    is_logged_in_url,
)

OUT_DIR = ROOT / "output" / "_m4"

# 候选入口（实测哪个能开、谁加载 SDK）
CANDIDATE_URLS = [
    DEFAULT_HOME,
    "https://work.1688.com/",
    # 商品管理/发布常见入口（会随改版变化，靠导航+关键词兜底）
    "https://offer.1688.com/page/offerlist.htm",
    "https://publish.1688.com/",
    "https://sale.1688.com/sale/offer/post/fill_product_info.htm",
    "https://air.1688.com/app/1688-global/main-site-product-manage/work.htm",
    # 开放平台方案页（API 列表 / SDK 说明，需登录 open）
    "https://open.1688.com/solution/solutionDetail.htm?solutionKey=1671675923686",
    "https://open.1688.com/",
]

# 网络/脚本关键字（命中即记录）
INTERESTING_URL_RE = re.compile(
    r"(alife-open-sdk|pcAlgorithmSdk|open-sdk|fuwu-assets|"
    r"gw\.api\.alibaba|open\.1688\.com|product\.publish|schema|"
    r"category|photobank|imagebank|video\.upload|offer\.publish|"
    r"alibaba\.product|com\.alibaba|"
    r"work\.1688\.com|offer\.1688\.com|publish\.1688\.com|"
    r"air\.1688\.com|sale\.1688\.com)",
    re.I,
)

SDK_CDN = "https://o.alicdn.com/fuwu-assets/alife-open-sdk/index.js"
APP_KEY = "9901201"
APP_NAME = "易之来商品自动发布"


def _brief_headers(h: dict) -> dict:
    keep = {}
    for k, v in (h or {}).items():
        lk = k.lower()
        if lk in (
            "content-type",
            "content-length",
            "x-requested-with",
            "referer",
            "origin",
            "authorization",
            "cookie",
        ):
            if lk == "cookie":
                keep[k] = f"<redacted len={len(v)}>"
            elif lk == "authorization":
                keep[k] = f"<redacted len={len(v)}>"
            else:
                keep[k] = v[:200] if isinstance(v, str) else v
    return keep


def _attach_network_sniffer(page: Page, bucket: list) -> None:
    def on_request(req: Request) -> None:
        url = req.url
        if not INTERESTING_URL_RE.search(url):
            return
        bucket.append(
            {
                "phase": "request",
                "method": req.method,
                "url": url[:500],
                "resource_type": req.resource_type,
                "headers": _brief_headers(req.headers),
                "post_data_preview": (req.post_data or "")[:300] if req.method in ("POST", "PUT") else None,
            }
        )

    def on_response(resp: Response) -> None:
        url = resp.url
        if not INTERESTING_URL_RE.search(url):
            return
        item: dict[str, Any] = {
            "phase": "response",
            "status": resp.status,
            "url": url[:500],
            "content_type": (resp.headers or {}).get("content-type", ""),
        }
        # 对 SDK/小 JSON 尝试摘一点 body 关键字
        try:
            ct = item["content_type"]
            if "javascript" in ct or "json" in ct or "text" in ct:
                body = resp.text()
                if body:
                    # 不落全量，只留线索
                    keys = []
                    for kw in (
                        "pcAlgorithmSdk",
                        "__1688_OPEN_SDK",
                        "load",
                        "schema",
                        "publish",
                        "token",
                        "sign",
                        "appKey",
                    ):
                        if kw in body:
                            keys.append(kw)
                    item["body_keywords"] = keys
                    item["body_len"] = len(body)
                    if "alife-open-sdk" in url or "pcAlgorithm" in body[:2000]:
                        item["body_head"] = body[:400]
        except Exception as e:  # noqa: BLE001
            item["body_error"] = str(e)[:120]
        bucket.append(item)

    page.on("request", on_request)
    page.on("response", on_response)


def _page_script_inventory(page: Page) -> dict:
    """页面上已有的 script src + 全局窗口对象线索。"""
    return page.evaluate(
        """() => {
          const scripts = Array.from(document.scripts).map(s => ({
            src: s.src || null,
            has_text: !!(s.textContent && s.textContent.trim().length),
            text_len: (s.textContent || '').length,
          }));
          const interesting_src = scripts
            .map(s => s.src)
            .filter(Boolean)
            .filter(u => /alife|open-sdk|algorithm|1688|alicdn|publish|schema/i.test(u));
          const globals = {};
          for (const k of [
            '__1688_OPEN_SDK', '__1688_OPEN_SDK_CONFIG',
            'pcAlgorithmSdk', 'Ali1688', 'ALIFE',
            '__NEXT_DATA__', 'g_config',
          ]) {
            try { globals[k] = (typeof window[k]); } catch (e) { globals[k] = 'err'; }
          }
          // 扫一层 window 键名
          const winKeys = Object.keys(window).filter(k =>
            /1688|sdk|algorithm|publish|schema|offer/i.test(k)
          ).slice(0, 80);
          return {
            title: document.title,
            url: location.href,
            script_count: scripts.length,
            interesting_src,
            globals,
            winKeys,
            text_sample: (document.body && document.body.innerText || '').slice(0, 500),
          };
        }"""
    )


def _try_inject_sdk(page: Page, wait_ms: int = 8000) -> dict:
    """按交接文档注入 alife-open-sdk，观察是否可 load pcAlgorithmSdk。"""
    result: dict[str, Any] = {"injected": False}
    try:
        # 配置 + 脚本注入
        page.evaluate(
            """({appKey, appName}) => {
              window.__1688_OPEN_SDK_CONFIG = { appKey, appName };
              window.__M4_SDK_EVENTS = [];
            }""",
            {"appKey": APP_KEY, "appName": APP_NAME},
        )
        page.add_script_tag(url=SDK_CDN)
        page.wait_for_timeout(2000)
        result["injected"] = True
        result["config"] = page.evaluate("() => window.__1688_OPEN_SDK_CONFIG || null")
        result["sdk_global_type"] = page.evaluate(
            "() => typeof window.__1688_OPEN_SDK"
        )
        # 尝试 load
        load_ret = page.evaluate(
            """async () => {
              const out = { hasSdk: typeof window.__1688_OPEN_SDK };
              if (typeof window.__1688_OPEN_SDK === 'undefined') {
                out.error = 'SDK_GLOBAL_MISSING';
                // 有些包挂到别的名字
                out.alt = {
                  alife: typeof window.alife,
                  ALIFE: typeof window.ALIFE,
                  OpenSdk: typeof window.OpenSdk,
                };
                return out;
              }
              try {
                const sdk = window.__1688_OPEN_SDK;
                out.keys = Object.keys(sdk || {}).slice(0, 40);
                out.sdkType = typeof sdk;
                if (sdk && typeof sdk.load === 'function') {
                  out.loadType = 'function';
                  try {
                    const r = sdk.load({ sdkNameList: ['pcAlgorithmSdk'] });
                    out.loadReturnType = typeof r;
                    if (r && typeof r.then === 'function') {
                      out.loadAwait = await Promise.race([
                        r.then(v => ({ok:true, valueType: typeof v, keys: v && typeof v==='object' ? Object.keys(v).slice(0,30) : null})),
                        new Promise(res => setTimeout(() => res({ok:false, error:'load_timeout'}), 6000)),
                      ]);
                    } else {
                      out.loadSync = {
                        valueType: typeof r,
                        keys: r && typeof r === 'object' ? Object.keys(r).slice(0, 30) : null,
                      };
                    }
                  } catch (e) {
                    out.loadError = String(e);
                  }
                } else {
                  out.loadType = typeof (sdk && sdk.load);
                }
                // load 后看 pcAlgorithmSdk
                out.pcAlgorithmSdk = typeof window.pcAlgorithmSdk;
                if (typeof window.pcAlgorithmSdk !== 'undefined') {
                  try {
                    out.pcKeys = Object.keys(window.pcAlgorithmSdk || {}).slice(0, 40);
                  } catch (e) { out.pcKeysError = String(e); }
                }
              } catch (e) {
                out.error = String(e);
              }
              return out;
            }"""
        )
        result["load"] = load_ret
        page.wait_for_timeout(max(0, wait_ms - 2000))
        result["post_globals"] = page.evaluate(
            """() => {
              const g = {};
              for (const k of Object.keys(window)) {
                if (/1688|sdk|algorithm|open/i.test(k)) g[k] = typeof window[k];
              }
              return g;
            }"""
        )
    except Exception as e:  # noqa: BLE001
        result["error"] = str(e)
    return result


def _find_nav_links(page: Page) -> list:
    """从工作台抓含 发布/商品 的链接，供后续候选。"""
    try:
        return page.evaluate(
            """() => {
              const anchors = Array.from(document.querySelectorAll('a[href]'));
              const hit = [];
              for (const a of anchors) {
                const t = (a.innerText || a.textContent || '').trim().replace(/\\s+/g, ' ');
                const href = a.href || '';
                if (!href || href.startsWith('javascript')) continue;
                if (/发布|商品管理|商品列表|offer|publish|product/i.test(t + ' ' + href)) {
                  hit.push({ text: t.slice(0, 60), href: href.slice(0, 300) });
                }
                if (hit.length >= 40) break;
              }
              return hit;
            }"""
        )
    except Exception as e:  # noqa: BLE001
        return [{"error": str(e)}]


def probe_url(page: Page, url: str, network: list, inject: bool = False) -> dict:
    item: dict[str, Any] = {"url": url, "ok": False}
    before = len(network)
    t0 = time.time()
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        item["status"] = resp.status if resp else None
        item["final_url"] = page.url
        item["title"] = page.title()
        item["logged_in"] = is_logged_in_url(page.url, page.title())
        item["inventory"] = _page_script_inventory(page)
        item["nav_links"] = _find_nav_links(page) if "work.1688.com" in page.url else []
        if inject and item["logged_in"]:
            item["sdk_inject"] = _try_inject_sdk(page)
        item["ok"] = True
    except Exception as e:  # noqa: BLE001
        item["error"] = str(e)
        try:
            item["final_url"] = page.url
            item["title"] = page.title()
        except Exception:
            pass
    item["seconds"] = round(time.time() - t0, 1)
    item["network_events"] = network[before:]
    return item


def run_probe(
    headless: bool = True,
    out_dir: Path = OUT_DIR,
    cookie_path: Path = COOKIE_PATH,
    extra_urls: Optional[list] = None,
) -> dict:
    """主入口：登录校验 → 多 URL 探测 → 写 report。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cookie_path": str(cookie_path),
        "headless": headless,
    }

    login = check_login(
        shot=out_dir / "login_check.png",
        headless=headless,
        cookie_path=cookie_path,
    )
    report["login"] = login
    if not login.get("logged_in"):
        report["error"] = "not_logged_in"
        report["hint"] = "先运行: .venv-m4/Scripts/python.exe refresh_cookies.py"
        (out_dir / "probe_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return report

    urls = list(CANDIDATE_URLS)
    if extra_urls:
        urls.extend(extra_urls)

    network: list = []
    pages_out: list = []
    discovered_links: list = []

    with browser_session(headless=headless, cookie_path=cookie_path) as page:
        _attach_network_sniffer(page, network)

        # 1) 工作台 + 抓导航链接
        home = probe_url(page, DEFAULT_HOME, network, inject=False)
        pages_out.append(home)
        if home.get("nav_links"):
            discovered_links.extend(home["nav_links"])
        page.screenshot(path=str(out_dir / "home.png"), full_page=False)

        # 把导航里看起来像发布/商品管理的 href 追加探测
        extra = []
        for link in discovered_links:
            href = (link or {}).get("href") or ""
            if not href.startswith("http"):
                continue
            host = urlparse(href).netloc
            if any(h in host for h in ("1688.com", "alibaba.com", "taobao.com")):
                text = (link.get("text") or "")
                if re.search(r"发布|商品管理|发布商品|新品|offer", text, re.I) or re.search(
                    r"publish|offer|product-manage|post", href, re.I
                ):
                    extra.append(href)
        # 去重保序
        seen = set(urls)
        for u in extra:
            if u not in seen:
                urls.append(u)
                seen.add(u)

        # 2) 其余候选（工作台已探过可跳）
        for i, url in enumerate(urls):
            if url.rstrip("/") in (
                DEFAULT_HOME.rstrip("/"),
                "https://work.1688.com",
            ) and i > 0:
                # work 根已覆盖
                if url.rstrip("/") == "https://work.1688.com":
                    continue
            if url == DEFAULT_HOME:
                continue
            # 开放平台页 + 工作台相关页尝试 inject 一次即可
            do_inject = any(
                k in url
                for k in (
                    "solutionDetail",
                    "publish.1688",
                    "fill_product",
                    "product-manage",
                    "offerlist",
                )
            )
            item = probe_url(page, url, network, inject=do_inject)
            pages_out.append(item)
            safe = re.sub(r"[^a-zA-Z0-9]+", "_", urlparse(url).path or "root")[:40]
            try:
                page.screenshot(
                    path=str(out_dir / f"page_{i}_{safe}.png"), full_page=False
                )
                item["screenshot"] = f"page_{i}_{safe}.png"
            except Exception:
                pass
            if item.get("nav_links"):
                discovered_links.extend(item["nav_links"])

        # 3) 在工作台空白稳定页再强制 inject 一次（文档路径）
        try:
            page.goto(DEFAULT_HOME, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            report["force_inject_on_home"] = _try_inject_sdk(page)
            page.screenshot(path=str(out_dir / "sdk_inject_home.png"), full_page=False)
        except Exception as e:  # noqa: BLE001
            report["force_inject_on_home"] = {"error": str(e)}

    report["pages"] = pages_out
    report["discovered_links"] = discovered_links[:80]
    report["network_event_count"] = len(network)
    report["network_sample"] = network[:200]
    report["analysis"] = analyze_probe(report)

    out_path = out_dir / "probe_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def analyze_probe(report: dict) -> dict:
    """从探针结果提炼发布模式线索（启发式，非最终结论）。"""
    evidence = []
    mode_scores = {
        "browser_sdk_direct": 0,
        "sdk_token_then_backend": 0,
        "unknown": 0,
    }

    # SDK 脚本是否自然出现
    natural_sdk = False
    inject_ok = False
    for p in report.get("pages") or []:
        inv = p.get("inventory") or {}
        for src in inv.get("interesting_src") or []:
            if "alife-open-sdk" in (src or "") or "pcAlgorithm" in (src or ""):
                natural_sdk = True
                evidence.append(f"页面自然加载 SDK 脚本: {src}")
        if (p.get("sdk_inject") or {}).get("injected"):
            load = (p.get("sdk_inject") or {}).get("load") or {}
            if load.get("hasSdk") == "object" or load.get("keys"):
                inject_ok = True
                evidence.append(f"注入 SDK 成功 @ {p.get('final_url')}")
            if load.get("loadAwait", {}).get("ok") or load.get("loadSync"):
                mode_scores["browser_sdk_direct"] += 1
                evidence.append("sdk.load() 可调用")
            if load.get("pcAlgorithmSdk") == "object":
                mode_scores["browser_sdk_direct"] += 2
                evidence.append("pcAlgorithmSdk 全局可用")

    fi = report.get("force_inject_on_home") or {}
    if fi.get("injected") and (fi.get("load") or {}).get("hasSdk") != "undefined":
        inject_ok = True
        evidence.append("工作台强制注入 SDK 有响应")
        load = fi.get("load") or {}
        if load.get("pcAlgorithmSdk") == "object":
            mode_scores["browser_sdk_direct"] += 2
        if "token" in json.dumps(load, ensure_ascii=False).lower():
            mode_scores["sdk_token_then_backend"] += 2
            evidence.append("load 返回中出现 token 字样")

    # 网络：是否有开放平台 API 直调
    api_like = []
    for ev in report.get("network_sample") or []:
        url = ev.get("url") or ""
        if re.search(r"gw\.api\.alibaba|open\.1688\.com/api|param2/1/com\.alibaba", url, re.I):
            api_like.append(url[:200])
            mode_scores["sdk_token_then_backend"] += 1
        if "alife-open-sdk" in url:
            natural_sdk = True
            mode_scores["browser_sdk_direct"] += 1

    if api_like:
        evidence.append(f"观察到开放平台/API 风格请求 {len(api_like)} 条")

    if not natural_sdk and not inject_ok:
        mode_scores["unknown"] += 3
        evidence.append("未观察到 SDK 自然加载，注入也未成功（或未登录目标页）")

    # 粗判
    best = max(mode_scores, key=mode_scores.get)
    if mode_scores[best] == 0:
        best = "unknown"

    return {
        "natural_sdk_seen": natural_sdk,
        "inject_ok": inject_ok,
        "mode_scores": mode_scores,
        "tentative_mode": best,
        "evidence": evidence,
        "api_like_urls": api_like[:20],
        "note": "tentative_mode 为启发式结论，需结合 open 方案页「开发人员参考」与一次真实发布抓包最终确认。",
    }
