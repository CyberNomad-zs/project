# -*- coding: utf-8 -*-
"""
订单状态更新 - 定时循环（每 10 分钟一次）。
操作：ERP 三方仓 > 待更新 > 全选 > 手动更新 > 读「获取完成 共N 已获取X 失败Y」。
不分渠道（全部渠道），只拉取/更新跟踪状态，不发货，安全。

会话：空闲易过期，有真实页面活动才续期。等待期用 core.wait_with_keepalive（订单页导航+探测）。
      网络抖动不杀循环；明确掉线则同窗口等重登。
浏览器：用户点窗口「×」关掉后，循环会自动重启浏览器并续跑（会话仍在 profile 里则无需重登）。

用法：
    1) 先手动登录一次：  python capture/erp_manual_login.py
    2) 启动定时循环：    python status_update_loop.py
    Ctrl+C 停止。掉线时请在自动化浏览器窗口内重登。
"""
import time
import config, core, erp, notify
from core import (
    log, erp_is_logged_in, wait_with_keepalive, wait_for_erp_relogin,
    is_browser_dead_error, ensure_browsers, recover_after_browser_dead, safe_close,
)
from playwright.sync_api import sync_playwright

INTERVAL = 600        # 两次状态更新间隔（秒）= 10 分钟
KEEPALIVE = core.KEEPALIVE_SEC
_last = [0]


def _log(msg):
    log(f"[状态更新] {msg}")


def main():
    core.log.begin_run("状态更新循环", interval_sec=INTERVAL, keepalive_sec=KEEPALIVE)
    _log(f"启动 RUN_ID={core.RUN_ID}，间隔 {INTERVAL}s（{INTERVAL//60} 分钟），保活 {KEEPALIVE}s")
    with sync_playwright() as p:
        ctx = core.open_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if not core.ensure_erp(page):
            _log("ERP 会话无效。请先： python capture/erp_manual_login.py  再启动本脚本。")
            safe_close(ctx); return

        cycle = 0
        try:
            while True:
                cycle += 1
                # 每轮开始先看浏览器还在不在（用户可能在空闲期点了 ×）
                try:
                    ctx, page, _, restarted = ensure_browsers(
                        p, ctx, page, wms_browser=None, need_wms=False
                    )
                except Exception as e:
                    _log(f"重启浏览器失败: {e}")
                    break
                if restarted:
                    if not core.ensure_erp(page):
                        _log("浏览器重启后会话失效，等待同窗口重登…")
                        if not wait_for_erp_relogin(page):
                            break

                cstart = time.time()
                try:
                    res = erp.update_order_status(page)
                    if res.get("error"):
                        _log(f"第{cycle}轮 失败: {res['error']}")
                    else:
                        _log(f"第{cycle}轮 完成: 共{res.get('total')} 已获取{res.get('got')} 失败{res.get('fail')}")
                    notify.notify_status(run_id=core.RUN_ID, cycle=cycle, res=res,
                                         elapsed_sec=round(time.time() - cstart, 1))
                except Exception as e:
                    _log(f"第{cycle}轮 异常: {e}")
                    notify.notify_status(run_id=core.RUN_ID, cycle=cycle,
                                         res={"error": f"异常: {e}"},
                                         elapsed_sec=round(time.time() - cstart, 1))
                    if is_browser_dead_error(e):
                        _log("判定为浏览器被关闭，自动重启并续跑…")
                        ctx, page, _, ok = recover_after_browser_dead(
                            p, ctx, page, wms_browser=None, need_wms=False, err=e
                        )
                        if not ok:
                            break
                        continue
                    if not erp_is_logged_in(page):
                        _log("会话失效，等待同窗口重登…")
                        if not wait_for_erp_relogin(page):
                            break

                try:
                    alive = wait_with_keepalive(page, INTERVAL, keepalive_sec=KEEPALIVE)
                except Exception as e:
                    if is_browser_dead_error(e):
                        _log("保活期浏览器被关闭，自动重启…")
                        ctx, page, _, ok = recover_after_browser_dead(
                            p, ctx, page, wms_browser=None, need_wms=False, err=e
                        )
                        if not ok:
                            break
                        continue
                    raise
                if not alive:
                    _log("保活期会话失效，等待同窗口重登…")
                    if not wait_for_erp_relogin(page):
                        break
        finally:
            safe_close(ctx, "ERP context")


if __name__ == "__main__":
    main()
