# -*- coding: utf-8 -*-
"""
全流程发货 - 定时循环（默认每 30 分钟一轮）。
每轮跑【完整一条龙】(= run_shipping.run_full_once)：
  ① ERP 按渠道物流下单 -> ② WMS 对应账号改快递方+批量发货
  -> ③ 三方仓待更新拉跟踪号 -> ④ 成功标签确认发货（扣库存+提交平台，不可逆）
失败订单留存到 logs/failures_*.txt 并日志提醒；每轮发一张运行汇总卡片到飞书。

与另外两个循环的区别：
  · shipping_loop.py  只做 ①②（下单+发货），不收尾。
  · status_update_loop.py 只做 ③（拉跟踪号）。
  · 本脚本 = 全流程一条龙常驻，含 ④确认发货。

⚠️ 真实动作：config.DRY_RUN=False 时每轮会【真实下单 + 发货 + 确认发货(扣库存/提交平台，不可逆)】。
   config.DRY_RUN=True 时只空跑演练（走筛选/统计，不真下单/发货/确认），可先这样观察几轮。
   真跑请用启动器或：PowerShell 里  $env:HWC_DRY_RUN='0'; python full_loop.py

会话：ERP 空闲约 10 分钟可能过期，有真实页面活动才续期。
      两轮之间每 KEEPALIVE 秒做一次「订单页导航 + isLogin」保活（不再只 ping 接口）。
      网络抖动不判掉线；明确失效时同窗口打开登录页等你重登，尽量不整进程退出。
浏览器：用户点窗口「×」关掉后，循环会自动重启浏览器并续跑（会话仍在 profile 里则无需重登）。

用法：
    1) 先手动登录一次：  python capture/erp_manual_login.py
    2) 启动全流程循环：  python full_loop.py        （Ctrl+C 停止）
    若弹出登录页：在自动化浏览器窗口内完成验证码/滑块即可继续。
"""
import time
import config, core, rules, notify, erp
from core import (
    log, erp_is_logged_in, wait_with_keepalive, wait_for_erp_relogin,
    is_browser_dead_error, ensure_browsers, recover_after_browser_dead, safe_close,
)
from run_shipping import run_full_once
from playwright.sync_api import sync_playwright

INTERVAL = 1800   # 两轮之间目标间隔（秒）= 30 分钟（以“每轮开始”计时；单轮超时则跑完立即下一轮）
KEEPALIVE = core.KEEPALIVE_SEC  # 默认 120s：真实页面保活


def _log(msg):
    log(f"[全流程循环] {msg}")


def _recover_session(page):
    """明确掉线后等重登；成功返回 True。"""
    _log("检测到 ERP 会话失效，进入同窗口重登等待…")
    if wait_for_erp_relogin(page):
        return True
    _log("重登等待超时，退出循环。请登录后重新启动 full_loop。")
    return False


def main():
    core.log.begin_run("全流程循环", interval_sec=INTERVAL, channels=len(rules.CHANNEL_ORDER))
    _log(f"启动 RUN_ID={core.RUN_ID}，目标间隔 {INTERVAL}s（{INTERVAL//60} 分钟）  DRY_RUN={config.DRY_RUN}  保活={KEEPALIVE}s")
    if not config.DRY_RUN:
        _log("⚠️ 真实模式：每轮会【真实下单 + 发货 + 确认发货(扣库存/提交平台，不可逆)】！")

    with sync_playwright() as p:
        ctx = core.open_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if not core.ensure_erp(page):
            _log("ERP 会话无效。请先： python capture/erp_manual_login.py  再启动本脚本。")
            notify.notify_shipping(
                run_id=core.RUN_ID, dry_run=config.DRY_RUN,
                failures=[{"stage": "启动检查", "channel": "-", "account": "", "orders": [],
                           "reason": "ERP 会话失效，全流程循环未启动。请重新登录后再启动。"}],
                elapsed_sec=0.0, channels=len(rules.CHANNEL_ORDER))
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
                        if not _recover_session(page):
                            break

                if not erp_is_logged_in(page):
                    if not _recover_session(page):
                        break
                start = time.time()
                _log(f"===== 第 {cycle} 轮开始（下单→发货→拉跟踪号→确认发货）=====")
                try:
                    fails = run_full_once(page, wms_browser, report=(cycle == 1)) or []
                    _log(f"第 {cycle} 轮结束，失败留存 {len(fails)} 组")
                    notify.notify_shipping(run_id=core.RUN_ID, dry_run=config.DRY_RUN,
                                           failures=fails, elapsed_sec=round(time.time() - start, 1),
                                           channels=len(rules.CHANNEL_ORDER), cycle=cycle)
                except Exception as e:
                    _log(f"第 {cycle} 轮异常: {e}")
                    notify.notify_shipping(
                        run_id=core.RUN_ID, dry_run=config.DRY_RUN,
                        failures=[{"stage": "全流程循环异常", "channel": "-", "account": "",
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
                        if not _recover_session(page):
                            break

                elapsed = time.time() - start
                wait = INTERVAL - elapsed
                if wait > 0:
                    _log(f"本轮耗时 {int(elapsed)}s，等待 {int(wait)}s 后进入下一轮（其间每 {KEEPALIVE}s 真实保活）")
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
                        if not _recover_session(page):
                            break
                else:
                    _log(f"本轮耗时 {int(elapsed)}s ≥ {INTERVAL}s，立即进入下一轮")
        finally:
            safe_close(wms_browser, "WMS browser")
            safe_close(ctx, "ERP context")


if __name__ == "__main__":
    main()
