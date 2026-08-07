# -*- coding: utf-8 -*-
"""M4 · 浏览器会话：加载/刷新 1688 登录 cookie，用 Playwright 承载页面(后续注入 JS SDK)。

第一步：验证 config/1688_cookies.json 的登录态是否还有效（文档风险点#3 cookie过期）。
第二步：半自动刷新 cookie（有头浏览器扫码/账密登录后回写）。
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
COOKIE_PATH = ROOT / "config" / "1688_cookies.json"
DEFAULT_HOME = "https://work.1688.com/home/page/index.htm"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 登录页特征：落到这些域名/路径视为未登录
_LOGIN_MARKERS = ("login.taobao.com", "login.1688.com", "/member/signin", "/member/login")


def load_cookies(path: Path = COOKIE_PATH) -> list:
    """把浏览器扩展导出的 cookie 转成 Playwright 格式。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for c in raw:
        pc = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".1688.com"),
            "path": c.get("path", "/"),
            "secure": bool(c.get("secure", True)),
            "httpOnly": bool(c.get("httpOnly", False)),
        }
        # Playwright sameSite 取值: Strict | Lax | None
        ss = c.get("sameSite")
        if isinstance(ss, str):
            ss_map = {
                "no_restriction": "None",
                "unspecified": "Lax",
                "lax": "Lax",
                "strict": "Strict",
                "none": "None",
            }
            mapped = ss_map.get(ss.lower(), ss)
            if mapped in ("Strict", "Lax", "None"):
                pc["sameSite"] = mapped
        exp = c.get("expirationDate") or c.get("expires")
        if isinstance(exp, (int, float)) and exp > 0:
            pc["expires"] = float(exp)
        out.append(pc)
    return out


def save_cookies(cookies: list, path: Path = COOKIE_PATH) -> Path:
    """把 Playwright cookies 回写为扩展导出风格 JSON，供下次 load_cookies 使用。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for c in cookies:
        item = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".1688.com"),
            "path": c.get("path", "/"),
            "secure": bool(c.get("secure", True)),
            "httpOnly": bool(c.get("httpOnly", False)),
            "session": "expires" not in c,
        }
        if "expires" in c and c["expires"]:
            item["expirationDate"] = float(c["expires"])
        ss = c.get("sameSite")
        if ss:
            # 扩展侧常见 lower / no_restriction
            item["sameSite"] = {
                "None": "no_restriction",
                "Lax": "lax",
                "Strict": "strict",
            }.get(ss, str(ss).lower())
        out.append(item)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def is_login_url(url: str, title: str = "") -> bool:
    u = (url or "").lower()
    t = (title or "").lower()
    if "login" in t and "work" not in u:
        return True
    return any(m in u for m in _LOGIN_MARKERS)


def is_logged_in_url(url: str, title: str = "") -> bool:
    return not is_login_url(url, title)


@contextmanager
def browser_session(
    headless: bool = True,
    cookies: bool = True,
    cookie_path: Path = COOKIE_PATH,
) -> Iterator[Page]:
    """开一个带 1688 登录态的浏览器页面。用法: with browser_session() as page: ..."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=UA,
            locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        if cookies and Path(cookie_path).exists():
            ctx.add_cookies(load_cookies(cookie_path))
        page = ctx.new_page()
        try:
            yield page
        finally:
            ctx.close()
            browser.close()


def check_login(
    url: str = DEFAULT_HOME,
    shot: Optional[Path] = None,
    headless: bool = True,
    cookie_path: Path = COOKIE_PATH,
) -> dict:
    """打开卖家工作台，判断登录态是否有效。"""
    result: dict = {}
    with browser_session(headless=headless, cookie_path=cookie_path) as page:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        final_url = page.url
        title = page.title()
        logged_in = is_logged_in_url(final_url, title)
        result = {
            "start_url": url,
            "final_url": final_url,
            "title": title,
            "logged_in": logged_in,
        }
        if shot:
            shot = Path(shot)
            shot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shot), full_page=False)
            result["screenshot"] = str(shot)
    return result


def ensure_seller_workbench(page: Page, wait_ms: int = 4000) -> dict:
    """若在买家工作台，点击「切为卖家 / 切换为卖家」进入卖家工作台。

    实测 UI 文案是「切为卖家」（非「切换为卖家」）。
    注意：个人号切卖家后会弹「当前非企业账号」，需企业卖家 cookie。
    """
    info: dict = {"switched": False}
    try:
        title = page.title()
        url = page.url
        info["before"] = {"url": url, "title": title}
    except Exception as e:  # noqa: BLE001
        info["before_error"] = str(e)
        return info

    # 已是卖家
    try:
        body = page.evaluate(
            "() => (document.body && document.body.innerText || '').slice(0, 800)"
        )
    except Exception:
        body = ""
    if ("卖家工作台" in (page.title() or "") or "商家工作台" in body) and "买家工作台" not in (
        page.title() or ""
    ):
        info["already_seller"] = True
        info["after"] = {"url": page.url, "title": page.title()}
        return info

    selectors = [
        "text=切为卖家",
        "text=切换为卖家",
        "a:has-text('切为卖家')",
        "a:has-text('切换为卖家')",
        "button:has-text('切为卖家')",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            if not loc.is_visible(timeout=1200):
                continue
            loc.click(timeout=5000)
            page.wait_for_timeout(wait_ms)
            info["switched"] = True
            info["clicked"] = sel
            break
        except Exception as e:  # noqa: BLE001
            info.setdefault("click_errors", []).append({sel: str(e)[:120]})

    # 若仍在买家，直接 goto 卖家首页 path
    try:
        title2 = page.title()
        if "买家" in title2 or not info.get("switched"):
            page.goto(
                "https://work.1688.com/?_path_=sellerPro/sellberBaseNew_Index/seller2018IndexPage",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(2500)
            info["forced_seller_url"] = True
    except Exception as e:  # noqa: BLE001
        info["force_error"] = str(e)

    info["after"] = {"url": page.url, "title": page.title()}
    try:
        text = page.evaluate(
            "() => (document.body && document.body.innerText || '').slice(0, 600)"
        )
        info["non_enterprise"] = "非企业账号" in (text or "")
        info["text_head"] = (text or "")[:300]
    except Exception:
        pass
    return info


def interactive_login(
    target_url: str = DEFAULT_HOME,
    cookie_path: Path = COOKIE_PATH,
    timeout_sec: int = 300,
    shot: Optional[Path] = None,
) -> dict:
    """有头浏览器打开登录页，等人扫码/账密登录后，把 cookie 回写到 cookie_path。

    成功条件：最终 URL 离开 login.*，落在 work.1688.com / 1688 卖家域。
    """
    cookie_path = Path(cookie_path)
    started = time.time()
    result: dict = {
        "ok": False,
        "cookie_path": str(cookie_path),
        "timeout_sec": timeout_sec,
    }

    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx: BrowserContext = browser.new_context(
            user_agent=UA,
            locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        # 尽量带上旧 cookie（部分可能仍有效）；失效则用户重新登
        if cookie_path.exists():
            try:
                ctx.add_cookies(load_cookies(cookie_path))
            except Exception as e:  # noqa: BLE001
                result["preload_cookie_error"] = str(e)

        page = ctx.new_page()
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        # 若已登录直接成功
        if is_logged_in_url(page.url, page.title()):
            cookies = ctx.cookies()
            save_cookies(cookies, cookie_path)
            result.update(
                {
                    "ok": True,
                    "already_logged_in": True,
                    "final_url": page.url,
                    "title": page.title(),
                    "cookie_count": len(cookies),
                    "seconds": round(time.time() - started, 1),
                }
            )
            if shot:
                shot = Path(shot)
                shot.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shot), full_page=False)
                result["screenshot"] = str(shot)
            ctx.close()
            browser.close()
            return result

        print("=" * 60)
        print("请在弹出的浏览器窗口完成 1688 登录（扫码或账密）")
        print(f"目标页: {target_url}")
        print(f"最长等待: {timeout_sec}s；登录成功后会自动保存 cookie")
        print("=" * 60)

        deadline = time.time() + timeout_sec
        last_url = page.url
        while time.time() < deadline:
            try:
                cur = page.url
                title = page.title()
            except Exception:
                # 页面可能导航中
                page.wait_for_timeout(500)
                continue
            if cur != last_url:
                print(f"[nav] {cur}")
                last_url = cur
            if is_logged_in_url(cur, title) and "work.1688.com" in cur:
                # 再等一下让登录跳转落稳、cookie 写全
                page.wait_for_timeout(2500)
                # 有时会停在中间跳转页，再 goto 一次工作台
                if "work.1688.com" not in page.url or is_login_url(page.url, page.title()):
                    page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(2000)
                if is_logged_in_url(page.url, page.title()):
                    cookies = ctx.cookies()
                    # 至少要有 1688 域 cookie
                    domains = {c.get("domain", "") for c in cookies}
                    if any("1688" in d for d in domains):
                        save_cookies(cookies, cookie_path)
                        result.update(
                            {
                                "ok": True,
                                "already_logged_in": False,
                                "final_url": page.url,
                                "title": page.title(),
                                "cookie_count": len(cookies),
                                "domains": sorted(domains),
                                "seconds": round(time.time() - started, 1),
                            }
                        )
                        if shot:
                            shot = Path(shot)
                            shot.parent.mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(shot), full_page=False)
                            result["screenshot"] = str(shot)
                        ctx.close()
                        browser.close()
                        return result
            page.wait_for_timeout(1000)

        # 超时
        result.update(
            {
                "ok": False,
                "error": "login_timeout",
                "final_url": page.url,
                "title": page.title(),
                "seconds": round(time.time() - started, 1),
            }
        )
        if shot:
            shot = Path(shot)
            shot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shot), full_page=False)
            result["screenshot"] = str(shot)
        ctx.close()
        browser.close()
    return result
