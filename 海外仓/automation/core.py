# -*- coding: utf-8 -*-
"""
公共基础：浏览器/会话管理 + 日志。
- 使用持久化 profile（同一浏览器上下文同时持有 ERP 与 WMS 的登录态）。
- ERP：复用 profile 中的登录态（由 capture/erp_manual_login.py 手动登录一次得到）。
- WMS：每次运行用账号自动登录（无验证码）。
"""
import os, time, datetime, json
import config, secrets

LOGIN_URL_WMS = "http://193.112.93.60:9999/login.html"
INDEX_WMS = "http://193.112.93.60:9999/index.html"
ORDERINFO_WMS = "http://193.112.93.60:9999/orderInfo/page/orderInfo.html"


# ---------------- 日志 ----------------
def _ts():
    # 环境禁用无参 datetime.now()，用 time.time 转本地时间字符串
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))


# 本次进程的运行标识：串起同一次执行产生的所有日志行与结构化事件，便于事后对账。
RUN_ID = time.strftime("%Y%m%d-%H%M%S", time.localtime(time.time()))


class Logger:
    """三合一日志：
    1) 控制台打印（gbk 兜底，不因 emoji 崩）；
    2) 人类可读文本日志 logs/run_YYYYMMDD.log（带 [级别]）；
    3) 结构化审计流水 logs/events_YYYYMMDD.jsonl（一行一 JSON，供对账/统计）。
    兼容旧用法 log("...")；新增 log.info/warn/error 与 log.event(stage=..., ...)。"""

    def __init__(self, name="run"):
        day = time.strftime("%Y%m%d", time.localtime(time.time()))
        self.path = os.path.join(config.LOG_DIR, f"{name}_{day}.log")
        self.event_path = os.path.join(config.LOG_DIR, f"events_{day}.jsonl")

    @staticmethod
    def _infer_level(msg):
        m = str(msg)
        if any(k in m for k in ("[ERROR]", "报错", "崩溃", "异常退出", "Traceback")):
            return "ERROR"
        if any(k in m for k in ("[WARN]", "[!]", "⚠", "失败", "未找到", "未定位", "超时", "无法")):
            return "WARN"
        return "INFO"

    def __call__(self, msg, level=None):
        level = level or self._infer_level(msg)
        line = f"[{_ts()}] [{level}] {msg}"
        try:
            print(line)
        except UnicodeEncodeError:
            # 控制台(gbk)打不出的字符(如 emoji)用 replace 兜底，不中断运行
            import sys
            enc = (sys.stdout.encoding or "gbk")
            print(line.encode(enc, "replace").decode(enc, "replace"))
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def info(self, msg):
        self(msg, "INFO")

    def warn(self, msg):
        self(msg, "WARN")

    def error(self, msg):
        self(msg, "ERROR")

    def event(self, stage, **fields):
        """记录一条结构化审计事件（写 jsonl，并回显一行人类可读日志）。
        典型 stage：物流下单 / WMS改快递方 / WMS批量发货 / WMS发货汇总 / 获取跟踪号 / 运行开始 / 运行结束。
        fields 常见：channel, shop, account, courier, count, success, fail, orders(list) 等。"""
        rec = {"ts": _ts(), "run_id": RUN_ID,
               "dry_run": getattr(config, "DRY_RUN", None),
               "stage": stage}
        rec.update(fields)
        # 回显人类可读行（订单号列表压缩显示，避免刷屏）
        parts = []
        for k, v in fields.items():
            if isinstance(v, (list, tuple)):
                v = f"[{len(v)}条]" if len(v) > 6 else list(v)
            parts.append(f"{k}={v}")
        self(f"[事件] {stage} " + " ".join(parts))
        try:
            with open(self.event_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def begin_run(self, kind, **fields):
        self.info("=" * 60)
        self.event("运行开始", kind=kind, dry_run=getattr(config, "DRY_RUN", None), **fields)
        return time.time()

    def end_run(self, kind, start_ts=None, **fields):
        if start_ts is not None:
            fields["elapsed_sec"] = round(time.time() - start_ts, 1)
        self.event("运行结束", kind=kind, **fields)
        self.info("=" * 60)


log = Logger()


# ---------------- 浏览器 ----------------
def open_context(p):
    """启动持久化浏览器上下文（ERP 用）。窗口最大化，便于人工盯屏。"""
    ctx = p.chromium.launch_persistent_context(
        config.BROWSER_PROFILE,
        headless=config.HEADLESS,
        no_viewport=True,
        args=["--start-maximized", "--no-sandbox"],
        ignore_https_errors=True,
    )
    return ctx


def open_wms_browser(p):
    """启动 WMS 独立 browser（与 ERP 持久 profile 分开，防多账号串会话）。
    带 --start-maximized：有头模式下窗口启动即最大化，方便看快递方/偏远筛选。
    headless 下无窗口，参数无害。"""
    return p.chromium.launch(
        headless=config.HEADLESS,
        args=["--start-maximized", "--no-sandbox"],
    )


def new_wms_context(wms_browser):
    """给 WMS 开一个干净 context：不限制 viewport，让页面跟着真实窗口尺寸走。
    Playwright 默认 viewport=1280x720 会把页面钉死在小画布上，即使窗口已最大化，
    快递方/偏远列仍挤在中间、手动放大也卡顿看不见——这就是用户 2026-07-21 反馈的原因。"""
    return wms_browser.new_context(
        ignore_https_errors=True,
        no_viewport=True,
    )


def maximize_page(page):
    """把 page 所在浏览器窗口最大化（CDP）。有头模式便于人工盯屏；headless 跳过。
    失败不抛，不阻塞主流程（部分环境 CDP 拿不到 windowId）。"""
    if config.HEADLESS:
        return
    try:
        session = page.context.new_cdp_session(page)
        win = session.send("Browser.getWindowForTarget")
        window_id = win.get("windowId") if isinstance(win, dict) else None
        if window_id is not None:
            session.send("Browser.setWindowBounds", {
                "windowId": window_id,
                "bounds": {"windowState": "maximized"},
            })
    except Exception as e:
        log(f"[浏览器] 窗口最大化失败（可忽略）: {e}")


# 用户点窗口「×」/进程被杀时，Playwright 抛出的典型文案（大小写不敏感子串匹配）
# 刻意不用过宽的 "protocol error"/"econnreset"：那些也会出现在瞬时网络毛刺上，
# 误判成关窗会无谓重启浏览器。真关窗几乎总会带 target/browser/context closed。
_BROWSER_DEAD_MARKERS = (
    "target closed",
    "target page, context or browser has been closed",
    "browser has been closed",
    "browser closed",
    "context closed",
    "context or browser has been closed",
    "connection closed while reading from the driver",
    "has been closed",
    "page crashed",
    "browser has disconnected",
    "browser disconnected",
)


def is_browser_dead_error(err):
    """判断异常是否因浏览器/页面被关掉（用户点 ×、崩溃、进程被杀）。
    这类错误不是业务失败，循环应重启浏览器后继续，而不是整段退出。"""
    if err is None:
        return False
    s = str(err).lower()
    return any(m in s for m in _BROWSER_DEAD_MARKERS)


def page_alive(page):
    """page 是否仍可用。已关/连接断返回 False。"""
    if page is None:
        return False
    try:
        if page.is_closed():
            return False
        # 轻触一次，避免 is_closed 还没跟上用户刚点 × 的情况
        _ = page.url
        return True
    except Exception as e:
        return not is_browser_dead_error(e)  # 非关窗类异常偏保守当还活着


def browser_alive(browser_or_ctx):
    """Browser / BrowserContext 是否仍可用。"""
    if browser_or_ctx is None:
        return False
    try:
        if hasattr(browser_or_ctx, "is_connected"):
            # Browser
            return bool(browser_or_ctx.is_connected())
        if hasattr(browser_or_ctx, "browser"):
            # BrowserContext：看底层 browser；persistent context 的 browser 可能为 None
            b = browser_or_ctx.browser
            if b is not None and hasattr(b, "is_connected"):
                return bool(b.is_connected())
        # 兜底：看 pages 能否访问
        _ = browser_or_ctx.pages
        return True
    except Exception:
        return False


def safe_close(obj, label=""):
    """安静关闭 page/context/browser，已死也不抛。"""
    if obj is None:
        return
    try:
        obj.close()
    except Exception as e:
        if label:
            log(f"[浏览器] 关闭{label}时忽略: {e}")


def reopen_erp(p, old_ctx=None, old_page=None):
    """ERP 持久化 context 被关掉后重新打开。
    返回 (ctx, page)。先尽量关旧的（释放 profile 锁），再 launch_persistent_context。
    调用方应再 ensure_erp / wait_for_erp_relogin 确认会话。"""
    safe_close(old_page, "旧ERP page")
    safe_close(old_ctx, "旧ERP context")
    # Windows 上 profile 锁偶发未立刻释放，稍等再开
    time.sleep(1.5)
    log("[浏览器] ERP 窗口已关/失效 → 重新启动持久化浏览器…")
    ctx = open_context(p)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        maximize_page(page)
    except Exception:
        pass
    log("[浏览器] ERP 浏览器已重启")
    return ctx, page


def reopen_wms_browser(p, old_browser=None):
    """WMS 独立 browser 被关掉后重新 launch。返回新 browser。"""
    safe_close(old_browser, "旧WMS browser")
    time.sleep(0.8)
    log("[浏览器] WMS 浏览器已关/失效 → 重新启动…")
    b = open_wms_browser(p)
    log("[浏览器] WMS 浏览器已重启")
    return b


def ensure_browsers(p, ctx, page, wms_browser=None, need_wms=True):
    """循环里统一的「浏览器还活着吗」检查 + 必要时重启。
    返回 (ctx, page, wms_browser, restarted)。
    restarted=True 时调用方应重新 ensure_erp / 等重登，再跑下一轮业务。
    need_wms=False 时不碰 WMS（如 status_update_loop 只用 ERP）。
    """
    restarted = False
    erp_dead = (not page_alive(page)) or (not browser_alive(ctx))
    if erp_dead:
        log("[浏览器] 检测到 ERP 浏览器已关闭（可能被手动点 ×），准备重启并续跑")
        ctx, page = reopen_erp(p, old_ctx=ctx, old_page=page)
        restarted = True
        # ERP 重启后 WMS 往往也一起被用户关掉，或残留半死状态，顺带重建更稳
        if need_wms:
            wms_browser = reopen_wms_browser(p, old_browser=wms_browser)
    elif need_wms and (not browser_alive(wms_browser)):
        log("[浏览器] 检测到 WMS 浏览器已关闭，准备重启")
        wms_browser = reopen_wms_browser(p, old_browser=wms_browser)
        restarted = True
    return ctx, page, wms_browser, restarted


def recover_after_browser_dead(p, ctx, page, wms_browser=None, need_wms=True, err=None):
    """业务轮次因关窗异常失败后的恢复入口。
    1) 重启死掉的 ERP(/WMS) 浏览器
    2) 校验/等待 ERP 登录（profile 会话多半还在；失效则同窗口等重登）
    返回 (ctx, page, wms_browser, ok)。ok=False 表示重登超时，循环应退出。
    """
    if err is not None:
        log(f"[浏览器] 捕获关窗/断连异常: {err}")
    ctx, page, wms_browser, _ = ensure_browsers(
        p, ctx, page, wms_browser=wms_browser, need_wms=need_wms
    )
    # 重启后确认会话
    try:
        if ensure_erp(page):
            log("[浏览器] 重启后 ERP 会话仍有效，继续循环")
            return ctx, page, wms_browser, True
    except Exception as e:
        log(f"[浏览器] 重启后 ensure_erp 异常: {e}")
    log("[浏览器] 重启后会话无效，打开登录页等待重登…")
    if wait_for_erp_relogin(page):
        return ctx, page, wms_browser, True
    return ctx, page, wms_browser, False


def safe_goto(page, url, tries=4, wait_until="domcontentloaded"):
    last = None
    for _ in range(tries):
        try:
            page.goto(url, wait_until=wait_until, timeout=40000)
            return True
        except Exception as e:
            last = e
            time.sleep(2)
    log(f"[WARN] 打开失败 {url}: {last}")
    return False


# ---------------- WMS 登录 ----------------
def wms_current_account(page):
    """读页面顶部 'Hi，XXX' 里 XXX（当前登录账号的显示名）。读不到返回 ''。
    显示名可能是登录名(黑猫=JMCAT)也可能是店铺中文名(金猫=金猫商贸)，故正则要兼容中文。
    多账号若共用一个 context，仅凭'没跳回登录页'不能保证已切到目标账号
    （实测 2026-07-10：先登黑猫 JMCAT 再登金猫 JMSM，页面仍显示 Hi，JMCAT）。"""
    try:
        return (page.evaluate(r"""() => {
          let acc='';
          document.querySelectorAll('*').forEach(e=>{
            if(e.children.length || e.offsetParent===null) return;
            const m=(e.innerText||'').trim().match(/Hi[，,]\s*(.+)$/);
            if(m) acc=m[1].trim();
          });
          return acc;
        }""") or "").strip()
    except Exception:
        return ""


def wms_login(page, account):
    """account: {'shop','login','password'}。返回是否成功。
    ⚠️ WMS 多账号共用同一 context 时，第二次登录不会覆盖旧账号会话（实测：黑猫→金猫仍读黑猫）。
    根治靠调用方给 WMS 用独立 context（见 wms.ship_shop）；这里再加一道兜底：
    成功判定不只看'没跳回 login.html'，还要校验页面当前账号 == 目标账号。"""
    safe_goto(page, LOGIN_URL_WMS)
    time.sleep(1.5)
    try:
        page.fill("#loginName", account["login"])
        page.fill("#loginPwd", account["password"])
        page.click("#loginSubmit")
    except Exception as e:
        log(f"[WMS] 填写登录表单失败: {e}")
        return False
    time.sleep(5)
    # 校验①：能打开首页未跳回登录；校验②：页面当前账号确实是目标账号（防会话串）
    safe_goto(page, INDEX_WMS)
    time.sleep(3)
    cur = wms_current_account(page)
    expect = account.get("display") or account["login"]
    url_ok = "login.html" not in (page.url or "")
    # 显示名与期望互相包含即视为同一账号（黑猫=JMCAT、金猫=金猫商贸）
    acc_ok = bool(cur) and (expect in cur or cur in expect)
    ok = url_ok and acc_ok
    extra = ""
    if not acc_ok:
        extra = f"（⚠️页面当前账号={cur or '读不到'}，期望含 {expect}：会话串了/登录未生效）"
    log(f"[WMS] 登录 {account['shop']}({account['login']}) => {'成功' if ok else '失败'}{extra}")
    return ok


# ---------------- ERP 会话校验 / 保活 ----------------
# isLogin 纯 API 探测：网络抖动时旧代码 except→False，会误判掉线整段退出。
# 且只 ping 接口往往**不续期** cookie；等待期需要真实页面活动才能把会话撑住。

ERP_ISLOGIN_URL = "https://www.sellfox.com/api/isLogin.json"
ERP_LOGIN_URL = "https://www.sellfox.com/amzup-web-main/login.html"
ERP_ORDER_SHIP_URL = getattr(
    config, "ERP_URL",
    "https://www.sellfox.com/amzup-web-main/web/orderShip/index.html",
)

# 保活间隔（秒）：旧版 240s，日志里常在第一次/第二次 ping 就「会话失效」退出
KEEPALIVE_SEC = 120
# 明确掉线后，同窗口等待用户重登的最长时间（秒）
RELOGIN_WAIT_SEC = 1800
RELOGIN_POLL_SEC = 20


def erp_probe_login(page, retries=3, pause=1.5):
    """探测 ERP 登录态。
    返回：'ok' 已登录 | 'expired' 明确未登录 | 'error' 网络/解析失败（**不等于**掉线）。
    """
    last_err = None
    for i in range(max(1, retries)):
        try:
            r = page.request.get(
                "%s?reqTime=%d" % (ERP_ISLOGIN_URL, int(time.time() * 1000)),
                timeout=15000,
            )
            if r.status != 200:
                last_err = "HTTP %s" % r.status
                time.sleep(pause)
                continue
            body = r.json()
            # 赛狐常见：{"data": true/false} 或 data 为对象
            data = body.get("data") if isinstance(body, dict) else None
            if data is True or data is False:
                return "ok" if data else "expired"
            if data in (None, 0, "", []):
                # 部分响应用 code/success
                if isinstance(body, dict) and body.get("code") in (401, 403, "401", "403"):
                    return "expired"
                if isinstance(body, dict) and body.get("success") is False and "login" in str(body).lower():
                    return "expired"
                # data 为空更接近未登录
                return "expired"
            return "ok"
        except Exception as e:
            last_err = e
            time.sleep(pause)
    log("[ERP] isLogin 探测异常（按网络抖动处理，不判掉线）: %s" % last_err)
    return "error"


def erp_is_logged_in(page):
    """兼容旧调用：仅在明确未登录时返回 False；网络错误偏保守返回 True，避免误杀循环。"""
    st = erp_probe_login(page)
    if st == "expired":
        return False
    if st == "error":
        # 二次确认：真实打开订单页，URL 若被踢回 login 才算掉线
        try:
            ok = erp_keepalive(page, quiet=True)
            return ok
        except Exception:
            return True
    return True


def erp_keepalive(page, quiet=False):
    """用真实页面活动续期会话（比单纯 isLogin 更有效）。
    成功返回 True；明确掉线返回 False。
    """
    try:
        # 先轻量 API；成功且已登录时再轻触业务页续 cookie
        st = erp_probe_login(page, retries=2)
        if st == "expired":
            if not quiet:
                log("[ERP] 保活：isLogin 明确未登录")
            return False
        # 真实导航续期（即使 isLogin error 也尝试）
        if not safe_goto(page, ERP_ORDER_SHIP_URL, tries=2):
            if st == "ok":
                # API 说还在，goto 失败当网络问题
                if not quiet:
                    log("[ERP] 保活：订单页打开失败，但 isLogin=ok，继续")
                return True
            if not quiet:
                log("[ERP] 保活：订单页打开失败且 isLogin 不确定")
            return True  # 不因网络杀循环
        time.sleep(1.2)
        url = (page.url or "").lower()
        if "login" in url and "orderShip" not in url and "ordership" not in url:
            if not quiet:
                log("[ERP] 保活：被重定向到登录页，会话已失效")
            return False
        # 再 ping 一次确认
        st2 = erp_probe_login(page, retries=2)
        if st2 == "expired":
            if not quiet:
                log("[ERP] 保活后 isLogin 仍为未登录")
            return False
        if not quiet:
            log("[ERP] 保活 OK（页面活动续期）")
        return True
    except Exception as e:
        if not quiet:
            log("[ERP] 保活异常（不判掉线）: %s" % e)
        return True


def wait_with_keepalive(page, seconds, keepalive_sec=None):
    """等待 seconds 秒，其间定期真实保活。
    返回 True=会话仍可用；False=明确掉线（调用方可 wait_for_erp_relogin）。
    """
    keepalive_sec = int(keepalive_sec or KEEPALIVE_SEC)
    waited = 0.0
    seconds = float(seconds)
    while waited < seconds:
        chunk = min(float(keepalive_sec), seconds - waited)
        time.sleep(chunk)
        waited += chunk
        if not erp_keepalive(page):
            # 再确认一次，避免偶发误判
            time.sleep(2)
            if not erp_keepalive(page, quiet=True):
                st = erp_probe_login(page, retries=3)
                if st == "expired":
                    return False
                # error：继续等，不退出
                log("[ERP] 保活二次确认仍不确定，继续等待（不退出）")
                continue
    return True


def wait_for_erp_relogin(page, timeout_sec=None, poll_sec=None):
    """会话明确失效后：同窗口打开登录页，等待用户完成验证码/滑块登录。
    成功返回 True；超时返回 False。
    这样循环不必整进程退出，也避免 profile 被占用时无法另开 erp_manual_login。
    """
    timeout_sec = int(timeout_sec if timeout_sec is not None else RELOGIN_WAIT_SEC)
    poll_sec = int(poll_sec if poll_sec is not None else RELOGIN_POLL_SEC)
    log("[ERP] 会话失效 → 打开登录页，请在本浏览器窗口内重新登录（验证码/滑块）。"
        "最长等待 %d 分钟。" % (timeout_sec // 60))
    try:
        safe_goto(page, ERP_LOGIN_URL, tries=3)
    except Exception as e:
        log("[ERP] 打开登录页失败: %s" % e)
    try:
        import notify
        notify.notify_shipping(
            run_id=RUN_ID, dry_run=getattr(config, "DRY_RUN", True),
            failures=[{
                "stage": "ERP会话",
                "channel": "-",
                "account": "",
                "orders": [],
                "reason": "ERP 会话失效，已打开登录页，请在自动化浏览器窗口内重新登录后循环将自动继续。",
            }],
            elapsed_sec=0.0, channels=0)
    except Exception:
        pass

    deadline = time.time() + timeout_sec
    n = 0
    while time.time() < deadline:
        time.sleep(poll_sec)
        n += 1
        st = erp_probe_login(page, retries=2)
        if st == "ok":
            # 再确认能进业务页
            if erp_keepalive(page, quiet=True):
                log("[ERP] 重新登录成功，继续循环")
                return True
        if n % 3 == 0:
            left = int(deadline - time.time())
            log("[ERP] 仍未检测到登录（剩余约 %ds），请完成滑块/验证码…" % max(0, left))
            # 保持停在登录相关页，便于用户操作
            try:
                url = (page.url or "").lower()
                if "login" not in url:
                    safe_goto(page, ERP_LOGIN_URL, tries=1)
            except Exception:
                pass
    log("[ERP] 等待重登超时。请稍后手动登录后再启动脚本。")
    return False


def ensure_erp(page):
    """确保 ERP 已登录（复用 profile 会话）。未登录则提示需手动登录。"""
    safe_goto(page, ERP_LOGIN_URL)
    time.sleep(2)
    st = erp_probe_login(page, retries=3)
    if st == "ok" or (st == "error" and erp_keepalive(page, quiet=True)):
        log("[ERP] 会话有效")
        return True
    log("[ERP] 会话已失效！请先运行： python capture/erp_manual_login.py 重新登录一次。")
    return False
