# -*- coding: utf-8 -*-
"""
发货流水线 - 定时循环（每 5 分钟一次）。
每轮：按渠道逐个闭环 —— ERP 该渠道物流下单 -> WMS 对应账号改快递方+批量发货，
      失败订单留存到 logs/failures_*.txt 并日志提醒。

⚠️ 真实动作：config.DRY_RUN=False 时会真实下单+发货。请确认后再常驻。
   config.DRY_RUN=True 时只空跑演练（不真发），可先这样观察几轮。

会话：空闲易过期；轮间用真实页面保活。网络抖动不杀循环；明确掉线同窗口等重登。
浏览器：用户点窗口「×」关掉后，循环会自动重启浏览器并续跑（会话仍在 profile 里则无需重登）。

用法：
    1) 先手动登录一次：  python capture/erp_manual_login.py
    2) 启动循环：        python shipping_loop.py
    Ctrl+C 停止。掉线时请在自动化浏览器窗口内重登。
"""
import time
import config, core, rules, notify
from core import (
    log, erp_is_logged_in, wait_with_keepalive, wait_for_erp_relogin,
    is_browser_dead_error, ensure_browsers, recover_after_browser_dead, safe_close,
)
from run_shipping import run_pipeline
from playwright.sync_api import sync_playwright

INTERVAL = 300   # 两轮之间目标间隔（秒）= 5 分钟（以“每轮开始”为准；单轮超时则连续跑）
KEEPALIVE = core.KEEPALIVE_SEC


def _log(msg):
    log(f"[发货循环] {msg}")


def main():
    _log(f"启动，目标间隔 {INTERVAL}s（{INTERVAL//60} 分钟）  DRY_RUN={config.DRY_RUN}  保活={KEEPALIVE}s")
    if not config.DRY_RUN:
        _log("⚠️ 真实发货模式：每轮会真实下单+发货！")
    with sync_playwright() as p:
        ctx = core.open_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if not core.ensure_erp(page):
            _log("ERP 会话无效。请先： python capture/erp_manual_login.py  再启动本脚本。")
            safe_close(ctx); return

        # WMS 用独立 browser（每店铺一个干净 context），与 ERP 持久 context 分开，避免账号串会话。
        wms_browser = core.open_wms_browser(p)
        cycle = 0
        try:
            while True:
                cycle += 1
                # 每轮开始先看浏览器还在不在（用户可能在空闲期点了 ×）
                try:
                    ctx, page, wms_browser, restarted = ensure_browsers(
                        p, ctx, page, wms_browser=wms_browser, need_wms=True
                    )
                except Exception as e:
                    _log(f"重启浏览器失败: {e}")
                    break
                if restarted:
                    if not core.ensure_erp(page):
                        _log("浏览器重启后会话失效，等待同窗口重登…")
                        if not wait_for_erp_relogin(page):
                            break

                if not erp_is_logged_in(page):
                    _log("会话失效，等待同窗口重登…")
                    if not wait_for_erp_relogin(page):
                        break
                start = time.time()
                _log(f"===== 第 {cycle} 轮开始 =====")
                try:
                    fails = run_pipeline(page, wms_browser, report=(cycle == 1))
                    _log(f"第 {cycle} 轮结束，失败留存 {len(fails)} 组")
                    notify.notify_shipping(run_id=core.RUN_ID, dry_run=config.DRY_RUN,
                                           failures=fails, elapsed_sec=round(time.time() - start, 1),
                                           channels=len(rules.CHANNEL_ORDER), cycle=cycle)
                except Exception as e:
                    _log(f"第 {cycle} 轮异常: {e}")
                    notify.notify_shipping(
                        run_id=core.RUN_ID, dry_run=config.DRY_RUN,
                        failures=[{"stage": "发货循环异常", "channel": "-", "account": "",
                                   "orders": [], "reason": str(e)}],
                        elapsed_sec=round(time.time() - start, 1),
                        channels=len(rules.CHANNEL_ORDER), cycle=cycle)
                    if is_browser_dead_error(e):
                        _log("判定为浏览器被关闭，自动重启并续跑…")
                        ctx, page, wms_browser, ok = recover_after_browser_dead(
                            p, ctx, page, wms_browser=wms_browser, need_wms=True, err=e
                        )
                        if not ok:
                            break
                        continue
                    if not erp_is_logged_in(page):
                        _log("会话失效，等待同窗口重登…")
                        if not wait_for_erp_relogin(page):
                            break

                elapsed = time.time() - start
                wait = INTERVAL - elapsed
                if wait > 0:
                    _log(f"本轮耗时 {int(elapsed)}s，等待 {int(wait)}s 后进入下一轮（其间保活）")
                    try:
                        alive = wait_with_keepalive(page, wait, keepalive_sec=KEEPALIVE)
                    except Exception as e:
                        if is_browser_dead_error(e):
                            _log("保活期浏览器被关闭，自动重启…")
                            ctx, page, wms_browser, ok = recover_after_browser_dead(
                                p, ctx, page, wms_browser=wms_browser, need_wms=True, err=e
                            )
                            if not ok:
                                break
                            continue
                        raise
                    if not alive:
                        _log("保活期会话失效，等待同窗口重登…")
                        if not wait_for_erp_relogin(page):
                            break
                else:
                    _log(f"本轮耗时 {int(elapsed)}s ≥ {INTERVAL}s，立即进入下一轮")
        finally:
            safe_close(wms_browser, "WMS browser")
            safe_close(ctx, "ERP context")


if __name__ == "__main__":
    main()
