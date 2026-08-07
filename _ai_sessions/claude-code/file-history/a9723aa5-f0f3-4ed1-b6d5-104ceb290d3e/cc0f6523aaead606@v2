"""告警：飞书群机器人 webhook（交互卡片）；未配置时仅写日志。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable, Mapping, Optional, Sequence

import requests

log = logging.getLogger(__name__)

# 飞书 header.template 色板
TEMPLATE = {
    "high": "red",       # 严重
    "medium": "orange",  # 需关注
    "warn": "orange",
    "ok": "green",       # 成功/一致
    "info": "blue",      # 一般信息
    "test": "turquoise",
}


def _plain(text: str) -> dict:
    return {"tag": "plain_text", "content": str(text or "")[:100] or " "}


def _md(content: str) -> dict:
    return {"tag": "lark_md", "content": content or " "}


def _div_md(content: str) -> dict:
    return {"tag": "div", "text": _md(content)}


def _hr() -> dict:
    return {"tag": "hr"}


def _note(text: str) -> dict:
    return {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": text}],
    }


def _fields(pairs: Sequence[tuple[str, str]], short: bool = True) -> dict:
    """两列字段区：[(label, value), ...]"""
    fields = []
    for label, value in pairs:
        fields.append({
            "is_short": short,
            "text": _md(f"**{label}**\n{value if value not in (None, '') else '—'}"),
        })
    return {"tag": "div", "fields": fields}


def _bullet_list(items: Iterable[str], limit: int = 20) -> str:
    rows = [str(x).strip() for x in items if str(x).strip()]
    if not rows:
        return "_（无明细）_"
    shown = rows[:limit]
    lines = [f"• {r}" for r in shown]
    if len(rows) > limit:
        lines.append(f"…另有 **{len(rows) - limit}** 条")
    return "\n".join(lines)


def _fmt_summary(summary: Mapping) -> str:
    """{'OK':434,'SELLFOX_NOT_SUBMITTED':2} → 可读行。"""
    if not summary:
        return "—"
    order = [
        "OK",
        "TRACKING_MISMATCH",
        "CARRIER_MISMATCH",
        "WMS_MISSING",
        "WMS_MISSING_BLACKCAT",
        "WMS_MISSING_UNKNOWN_CH",
        "WMS_QUERY_ERROR",
        "WMS_NOT_SHIPPED",
        "WMS_NO_TRACKING",
        "SELLFOX_NOT_SUBMITTED",
    ]
    labels = {
        "OK": "一致",
        "TRACKING_MISMATCH": "运单不一致",
        "CARRIER_MISMATCH": "承运不一致",
        "WMS_MISSING": "WMS 查无(昇新)",
        "WMS_MISSING_BLACKCAT": "WMS 查无(黑猫)",
        "WMS_MISSING_UNKNOWN_CH": "WMS 查无(未知渠道)",
        "WMS_QUERY_ERROR": "WMS 查询异常",
        "WMS_NOT_SHIPPED": "WMS 未出库",
        "WMS_NO_TRACKING": "WMS 无运单",
        "SELLFOX_NOT_SUBMITTED": "赛狐漏提交",
    }
    parts = []
    seen = set()
    for k in order:
        if k in summary:
            parts.append(f"{labels.get(k, k)} **{summary[k]}**")
            seen.add(k)
    for k, v in summary.items():
        if k not in seen:
            parts.append(f"{labels.get(k, k)} **{v}**")
    return " · ".join(parts)


class Notifier:
    def __init__(self, feishu_webhook="", customer_name=""):
        self.webhook = (feishu_webhook or "").strip()
        self.customer = (customer_name or "").strip()
        self.prefix = f"[sellfox-bridge/{self.customer}] " if self.customer else ""
        # 直连飞书，避免系统代理干扰
        self._http = requests.Session()
        self._http.trust_env = False

    # ---------- 底层发送 ----------

    def _post(self, payload: dict) -> bool:
        if not self.webhook:
            return False
        try:
            r = self._http.post(self.webhook, json=payload, timeout=10)
            if r.status_code != 200:
                log.error("飞书 HTTP %s: %s", r.status_code, (r.text or "")[:200])
                return False
            try:
                body = r.json()
            except Exception:
                return True
            # 自定义机器人成功多为 {"StatusCode":0,...} 或 {"code":0,...}
            code = body.get("code")
            status = body.get("StatusCode", body.get("statusCode"))
            if code not in (None, 0) or (status is not None and status != 0):
                log.error("飞书业务失败: %s", body)
                return False
            return True
        except Exception as e:
            log.error("飞书发送失败: %s", e)
            return False

    def _send_text(self, text: str) -> bool:
        """兜底纯文本（卡片失败时回退）。"""
        return self._post({
            "msg_type": "text",
            "content": {"text": self.prefix + text},
        })

    def send_card(
        self,
        title: str,
        elements: list,
        *,
        template: str = "blue",
        subtitle: str = "",
    ) -> bool:
        """发送交互卡片。template: red/orange/green/blue/turquoise/yellow/..."""
        header = {
            "title": _plain(title),
            "template": template or "blue",
        }
        if subtitle:
            header["subtitle"] = _plain(subtitle)

        # 统一页脚
        els = list(elements)
        els.append(_hr())
        foot = "sellfox-bridge"
        if self.customer:
            foot += f" · {self.customer}"
        foot += f" · {datetime.now().strftime('%m-%d %H:%M')}"
        els.append(_note(foot))

        card = {
            "config": {"wide_screen_mode": True},
            "header": header,
            "elements": els,
        }
        ok = self._post({"msg_type": "interactive", "card": card})
        if not ok:
            # 卡片失败时降级纯文本，避免告警丢失
            plain_bits = [title]
            if subtitle:
                plain_bits.append(subtitle)
            for el in elements:
                if el.get("tag") == "div" and "text" in el:
                    plain_bits.append(el["text"].get("content", ""))
                elif el.get("tag") == "div" and "fields" in el:
                    for f in el["fields"]:
                        plain_bits.append(f.get("text", {}).get("content", ""))
            return self._send_text("\n".join(x for x in plain_bits if x))
        return True

    # ---------- 对外 API ----------

    def warn(self, text: str) -> bool:
        """兼容旧调用：流水线/对账的简单告警 → 橙色卡片。"""
        log.warning("ALERT: %s", text)
        if not self.webhook:
            return False
        title = "流水线告警"
        # 从文案猜一下级别色
        t = str(text or "")
        if any(k in t for k in ("严重", "不一致", "查无", "失败", "异常")):
            template = TEMPLATE["high"]
            title = "⚠️ 流水线告警"
        else:
            template = TEMPLATE["warn"]
            title = "流水线需关注"
        return self.send_card(
            title,
            [_div_md(t)],
            template=template,
            subtitle=self.customer or "",
        )

    def info(self, text: str):
        """一般信息：默认只写日志，不推飞书（降噪）。需要推群用 warn / success / card。"""
        log.info("NOTIFY: %s", text)

    def success(self, text: str, title: str = "完成") -> bool:
        log.info("NOTIFY-OK: %s", text)
        if not self.webhook:
            return False
        return self.send_card(
            f"✅ {title}",
            [_div_md(text)],
            template=TEMPLATE["ok"],
            subtitle=self.customer or "",
        )

    def test(self, text: str = "飞书连通测试 OK") -> bool:
        """连通测试用青绿卡片。"""
        return self.send_card(
            "连通测试",
            [
                _div_md(f"**状态**  正常\n**说明**  {text}"),
                _fields([
                    ("客户", self.customer or "—"),
                    ("通道", "自定义机器人 Webhook"),
                ]),
            ],
            template=TEMPLATE["test"],
            subtitle="sellfox-bridge",
        )

    def recon_alert(
        self,
        *,
        total: int,
        days: int,
        highs: Sequence[Mapping],
        mediums: Sequence[Mapping] = (),
        summary: Optional[Mapping] = None,
    ) -> bool:
        """对账结果卡片：有 high → 红卡；仅 medium → 橙卡。"""
        highs = list(highs or [])
        mediums = list(mediums or [])
        summary = dict(summary or {})

        if highs:
            template = TEMPLATE["high"]
            title = f"⚠️ 对账严重异常 · {len(highs)} 条"
            level_label = "严重"
        elif mediums:
            template = TEMPLATE["medium"]
            title = f"对账需关注 · {len(mediums)} 条"
            level_label = "关注"
        else:
            template = TEMPLATE["ok"]
            title = "对账全部一致"
            level_label = "正常"

        log.warning(
            "RECON-CARD: total=%s high=%s medium=%s",
            total, len(highs), len(mediums),
        )
        if not self.webhook:
            return False

        elements = [
            _fields([
                ("客户", self.customer or "—"),
                ("范围", f"近 {days} 天 · 共 {total} 单"),
                ("级别", level_label),
                ("严重 / 关注", f"{len(highs)} / {len(mediums)}"),
            ]),
        ]

        if summary:
            elements.append(_hr())
            elements.append(_div_md(f"**分类统计**\n{_fmt_summary(summary)}"))

        if highs:
            details = [r.get("detail") or r.get("sn") or str(r) for r in highs]
            elements.append(_hr())
            elements.append(_div_md(f"**严重异常**\n{_bullet_list(details, limit=15)}"))

        if mediums and not highs:
            # 仅 medium 时展开明细；有 high 时 medium 只在统计里体现，避免刷屏
            details = [r.get("detail") or r.get("sn") or str(r) for r in mediums]
            elements.append(_hr())
            elements.append(_div_md(f"**需关注**\n{_bullet_list(details, limit=15)}"))
        elif mediums and highs:
            elements.append(
                _div_md(f"_另有 {len(mediums)} 条中等关注项，详见 recon 日志/JSON_")
            )

        return self.send_card(title, elements, template=template, subtitle="赛狐 ↔ WMS 对账")
