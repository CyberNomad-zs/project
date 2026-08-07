# -*- coding: utf-8 -*-
"""
飞书（Feishu/Lark）运行汇总通知。支持两种方式，自动择优：
  · 方式A【群自定义机器人 Webhook】(推荐、最简单)：在飞书群加"自定义机器人"，把 Webhook 地址
    填进 secrets.FEISHU["webhook"] 即可，无需 app_id/secret/token。
  · 方式B【企业自建应用】：填 app_id/app_secret/receive_id，走 im/v1/messages 发到指定群或个人。
  两者都配了则优先用 Webhook。

用途：每次运行 / 每轮循环结束，发一张"运行汇总"卡片，让在飞书里就能看到本次
      空跑/真跑、各渠道结果、成功/失败数、失败订单、耗时。

设计原则：
  · 只依赖标准库（urllib/hmac/hashlib/base64），无新增第三方依赖。
  · 完全容错：网络/配置/接口任何异常都只记一条日志，绝不影响发货主流程。
  · 未配置或 enable=False 时静默跳过。

配置：secrets.FEISHU（见 secrets.py），也可用环境变量覆盖（优先）：
  HWC_FEISHU_WEBHOOK / HWC_FEISHU_WEBHOOK_SECRET               （方式A）
  HWC_FEISHU_APP_ID / _APP_SECRET / _RECEIVE_ID / _RECEIVE_ID_TYPE（方式B）
  HWC_FEISHU_LEVEL(all|fail_only) / HWC_FEISHU_ENABLE(0=关) / HWC_FEISHU_BASE_URL

自测：命令行 `python notify.py`（或双击 测试飞书.bat）会发一条连通测试卡片。
"""
import os
import json
import time
import hmac
import hashlib
import base64
import urllib.request
import urllib.parse

try:
    import secrets as _secrets   # 本项目根目录下的 secrets.py（非标准库 secrets）
except Exception:
    _secrets = None


# ---------------- 配置 ----------------
def _cfg():
    """合并 secrets.FEISHU 与环境变量（环境变量优先），返回统一 dict。"""
    base = {}
    if _secrets is not None:
        base = dict(getattr(_secrets, "FEISHU", {}) or {})

    def pick(env_key, cfg_key, default=None):
        v = os.environ.get(env_key)
        if v is not None and v != "":
            return v
        return base.get(cfg_key, default)

    return {
        "enable":          pick("HWC_FEISHU_ENABLE", "enable", True),
        "level":           pick("HWC_FEISHU_LEVEL", "level", "all"),   # all=每次都发；fail_only=仅失败/异常发
        # 方式A：群自定义机器人 Webhook
        "webhook":         pick("HWC_FEISHU_WEBHOOK", "webhook", ""),
        "webhook_secret":  pick("HWC_FEISHU_WEBHOOK_SECRET", "webhook_secret", ""),
        # 方式B：企业自建应用
        "app_id":          pick("HWC_FEISHU_APP_ID", "app_id", ""),
        "app_secret":      pick("HWC_FEISHU_APP_SECRET", "app_secret", ""),
        "receive_id":      pick("HWC_FEISHU_RECEIVE_ID", "receive_id", ""),
        "receive_id_type": pick("HWC_FEISHU_RECEIVE_ID_TYPE", "receive_id_type", "chat_id"),
        "base_url":        pick("HWC_FEISHU_BASE_URL", "base_url", "https://open.feishu.cn"),
    }


def _truthy(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() not in ("0", "false", "no", "off", "")


def _use_webhook(cfg):
    return bool(cfg.get("webhook"))


def _is_enabled(cfg):
    if not _truthy(cfg.get("enable", True)):
        return False
    if _use_webhook(cfg):
        return True
    return bool(cfg.get("app_id") and cfg.get("app_secret") and cfg.get("receive_id"))


def _log():
    """延迟拿 core.log（避免 import 期循环依赖）；拿不到就退化为 print。"""
    try:
        from core import log
        return log
    except Exception:
        return lambda m: print(m)


# ---------------- HTTP：直连优先、环境代理兜底 ----------------
# 国内部署机直连 open.feishu.cn 最稳；若机器只能经代理出网，则回退走系统/环境代理。
# （实测某些本地代理对飞书的 HTTPS 隧道不稳，会 SSL EOF，故直连优先。）
_openers = {"direct": None, "proxy": None}


def _urlopen(req, timeout=10):
    if _openers["direct"] is None:
        _openers["direct"] = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        _openers["proxy"] = urllib.request.build_opener()   # 读取 HTTP(S)_PROXY 环境变量
    try:
        return _openers["direct"].open(req, timeout=timeout)
    except Exception:
        return _openers["proxy"].open(req, timeout=timeout)


# ---------------- 方式A：Webhook ----------------
def _gen_sign(timestamp, secret):
    """飞书自定义机器人签名校验：key = f'{timestamp}\\n{secret}'，对空串做 HMAC-SHA256 后 base64。"""
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _send_webhook(cfg, *, card=None, text=None):
    if card is not None:
        body = {"msg_type": "interactive", "card": card}
    else:
        body = {"msg_type": "text", "content": {"text": text}}
    secret = cfg.get("webhook_secret")
    if secret:
        ts = str(int(time.time()))
        body["timestamp"] = ts
        body["sign"] = _gen_sign(ts, secret)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(cfg["webhook"], data=data,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with _urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------- 方式B：企业自建应用 ----------------
_token = {"value": "", "exp": 0.0}
_TOKEN_ERRS = (99991663, 99991661, 99991664, 99991665)   # token 失效相关错误码


def _get_token(cfg):
    now = time.time()
    if _token["value"] and now < _token["exp"] - 60:
        return _token["value"]
    url = cfg["base_url"].rstrip("/") + "/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]}).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with _urlopen(req, timeout=10) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if resp.get("code") != 0:
        raise RuntimeError(f"tenant_access_token 失败: code={resp.get('code')} msg={resp.get('msg')}")
    _token["value"] = resp["tenant_access_token"]
    _token["exp"] = now + float(resp.get("expire", 7200))
    return _token["value"]


def _send_app(cfg, *, card=None, text=None):
    token = _get_token(cfg)
    if card is not None:
        msg_type, content_obj = "interactive", card
    else:
        msg_type, content_obj = "text", {"text": text}
    url = (cfg["base_url"].rstrip("/") + "/open-apis/im/v1/messages?receive_id_type="
           + urllib.parse.quote(cfg["receive_id_type"]))
    payload = {"receive_id": cfg["receive_id"], "msg_type": msg_type,
               "content": json.dumps(content_obj, ensure_ascii=False)}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json; charset=utf-8"})
    with _urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------- 统一发送 ----------------
def _resp_ok(resp):
    """飞书成功响应：新版 code==0；旧版自定义机器人可能是 StatusCode==0。"""
    if not isinstance(resp, dict):
        return False
    return resp.get("code") == 0 or resp.get("StatusCode") == 0


def _emit(card=None, text=None):
    """统一发送入口：容错，返回 True/False。任何异常都不外抛。"""
    cfg = _cfg()
    if not _is_enabled(cfg):
        return False
    log = _log()
    use_webhook = _use_webhook(cfg)
    try:
        if use_webhook:
            resp = _send_webhook(cfg, card=card, text=text)
        else:
            resp = _send_app(cfg, card=card, text=text)
            if resp.get("code") in _TOKEN_ERRS:      # token 失效，清缓存重试一次
                _token["value"] = ""
                resp = _send_app(cfg, card=card, text=text)
        if _resp_ok(resp):
            return True
        log(f"[飞书] 发送失败 resp={resp}")
    except Exception as e:
        log(f"[飞书] 发送异常（已忽略，不影响主流程）: {e}")
    return False


# ---------------- 卡片构建 ----------------
def _card(title, template, rows, note=None, detail=None):
    """构建飞书交互卡片。
    rows: [(label, value), ...] 渲染为双列字段；detail: 追加富文本段（失败明细）；note: 底部灰字。"""
    elements = []
    if rows:
        fields = [{"is_short": True,
                   "text": {"tag": "lark_md", "content": f"**{label}**\n{value}"}}
                  for label, value in rows]
        elements.append({"tag": "div", "fields": fields})
    if detail:
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": detail}})
    if note:
        elements.append({"tag": "note", "elements": [{"tag": "lark_md", "content": note}]})
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": template,
                   "title": {"tag": "plain_text", "content": title}},
        "elements": elements,
    }


def _fmt_failures(failures, max_groups=8, max_orders=15):
    """把失败留存 list 渲染成飞书 lark_md 明细。项形如
    {'stage','channel','account','orders':[...], 'reason'}。无失败返回 None。"""
    if not failures:
        return None
    lines = ["**⚠️ 失败明细（需人工跟进）**"]
    for x in failures[:max_groups]:
        orders = x.get("orders") or []
        shown = ", ".join(str(o) for o in orders[:max_orders])
        more = f" …等 {len(orders)} 单" if len(orders) > max_orders else ""
        acct = x.get("account") or "-"
        lines.append(f"• **[{x.get('stage', '')}]** 渠道={x.get('channel', '-')} 账号={acct}\n"
                     f"　原因：{x.get('reason', '')}\n"
                     f"　订单：{shown or '（无单号）'}{more}")
    if len(failures) > max_groups:
        lines.append(f"…其余 {len(failures) - max_groups} 组略")
    return "\n".join(lines)


# ---------------- 对外：运行汇总 ----------------
def notify_shipping(*, run_id, dry_run, failures, elapsed_sec, channels, cycle=None):
    """发货主流程 / 发货循环的每次运行汇总。cycle 非空表示是循环的第 N 轮。"""
    cfg = _cfg()
    if not _is_enabled(cfg):
        return False
    failures = failures or []
    fail_orders = sum(len(x.get("orders") or []) for x in failures)
    ok = (fail_orders == 0 and len(failures) == 0)
    if ok and str(cfg.get("level", "all")).lower() == "fail_only":
        return False   # 配成"仅失败才发"且本次全成功 → 跳过

    mode = "空跑（演练）" if dry_run else "真跑 🔴"
    title = "📦 海外仓发货 · " + (f"循环第 {cycle} 轮" if cycle else "运行结束")
    if ok:
        color = "grey" if dry_run else "green"
        result = "✅ 无失败"
    else:
        color = "red"
        result = f"⚠️ 失败 {len(failures)} 组 / {fail_orders} 单"
    rows = [
        ("模式", mode),
        ("结果", result),
        ("渠道", f"{channels} 个"),
        ("耗时", f"{float(elapsed_sec):.1f}s"),
        ("RUN_ID", f"{run_id}" + (f" · 第{cycle}轮" if cycle else "")),
    ]
    detail = _fmt_failures(failures)
    note = "海外仓自动化 · 运行汇总（每次运行推送一次）"
    return _emit(card=_card(title, color, rows, note=note, detail=detail))


def notify_status(*, run_id, cycle, res, elapsed_sec=None):
    """跟踪号更新循环（status_update_loop）的每轮汇总。res 形如
    {'total','got','fail'} 或 {'error': '...'}。"""
    cfg = _cfg()
    if not _is_enabled(cfg):
        return False
    res = res or {}
    err = res.get("error")
    ok = not err
    if ok and str(cfg.get("level", "all")).lower() == "fail_only":
        return False

    title = "🔄 海外仓 · 跟踪号更新" + (f" 第 {cycle} 轮" if cycle else "")
    if err:
        color = "red"
        rows = [("结果", "❌ 失败"), ("原因", str(err))]
    else:
        color = "green"
        rows = [("结果", "✅ 完成"),
                ("共", str(res.get("total", "-"))),
                ("已获取", str(res.get("got", "-"))),
                ("失败", str(res.get("fail", "-")))]
    rows.append(("RUN_ID", f"{run_id}" + (f" · 第{cycle}轮" if cycle else "")))
    if elapsed_sec is not None:
        rows.append(("耗时", f"{float(elapsed_sec):.1f}s"))
    note = "海外仓自动化 · 跟踪号更新汇总"
    return _emit(card=_card(title, color, rows, note=note))


def notify_text(text):
    """发一条纯文本消息（备用）。"""
    return _emit(text=str(text))


def notify_test():
    """发一条连通测试卡片。返回 True/False。"""
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    card = _card("✅ 海外仓自动化 · 飞书连通测试", "green",
                 [("状态", "配置正确，之后每次运行都会收到汇总"), ("时间", now)],
                 note="这是一条测试消息，可忽略。")
    return _emit(card=card)


def list_chats():
    """[方式B专用] 列出机器人所在的群（用于获取 chat_id）。返回原始接口 data。"""
    cfg = _cfg()
    token = _get_token(cfg)
    url = cfg["base_url"].rstrip("/") + "/open-apis/im/v1/chats?page_size=100"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with _urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------- 自测 CLI ----------------
if __name__ == "__main__":
    cfg = _cfg()
    if _use_webhook(cfg):
        print("[飞书] 使用【群自定义机器人 Webhook】方式，发送测试卡片...")
        ok = notify_test()
        print("飞书测试发送：", "成功 [OK]" if ok else
              "失败 [FAIL]（若机器人开了'签名校验'请填 webhook_secret；若设了'自定义关键词'需含该词）")
        raise SystemExit(0 if ok else 1)

    if not (cfg["app_id"] and cfg["app_secret"]):
        print("[飞书] 未配置：请在 secrets.py 的 FEISHU 填 webhook（方式A）或 app_id/app_secret（方式B）。")
        raise SystemExit(1)
    if not cfg["receive_id"]:
        print("[飞书] 已配 app 但未填 receive_id。下面列出机器人所在的群，把目标群 chat_id 回填到 secrets.FEISHU：")
        try:
            data = list_chats()
            items = ((data.get("data") or {}).get("items")) or []
            if not items:
                print("  （机器人还没被拉进任何群。请先把应用/机器人加入目标群，再重试。）")
            for it in items:
                print(f"  群名={it.get('name')}  chat_id={it.get('chat_id')}")
        except Exception as e:
            print("  列群失败：", e)
        raise SystemExit(0)
    ok = notify_test()
    print("飞书测试发送：", "成功 [OK]" if ok else "失败 [FAIL]（检查权限/是否已把应用拉进群/receive_id）")
