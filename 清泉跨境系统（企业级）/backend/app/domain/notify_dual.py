"""TK 告警双通道：群 webhook + 企业应用 IM 私信。

任一通道失败不影响另一通道；缺配置则 skip 并记日志。
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def notify_dual(
    *,
    title: str,
    lines: list[str],
    settings: Settings | None = None,
    dry_run: bool = False,
    force_notify: bool = True,
) -> dict[str, Any]:
    """发送群 + 私信。

    Returns:
        {
          webhook: sent|skipped|error,
          im: sent|skipped|error,
          any_sent: bool,
          errors: [...]
        }
    """
    cfg = settings or get_settings()
    result: dict[str, Any] = {
        "webhook": "skipped",
        "im": "skipped",
        "any_sent": False,
        "errors": [],
    }
    if dry_run or not force_notify:
        result["webhook"] = "dry_run" if dry_run else "skipped"
        result["im"] = result["webhook"]
        return result

    title_s = str(title or "提醒")[:200]
    body_lines = [str(x) for x in (lines or []) if str(x or "").strip()]
    if not body_lines:
        body_lines = ["(无正文)"]

    notify_wh = bool(getattr(cfg, "tk_notify_webhook", True))
    notify_im = bool(getattr(cfg, "tk_notify_im", True))
    # 兼容旧开关：tk_health_notify_feishu=false 时两路都关
    if not bool(getattr(cfg, "tk_health_notify_feishu", True)):
        notify_wh = False
        notify_im = False

    webhook = str(getattr(cfg, "feishu_bot_webhook_tk_health", "") or "").strip()
    if notify_wh and webhook:
        try:
            from app.adapters.feishu.bot import send_webhook_post

            await send_webhook_post(webhook, title=title_s, lines=body_lines)
            result["webhook"] = "sent"
            result["any_sent"] = True
        except Exception as exc:  # noqa: BLE001
            result["webhook"] = "error"
            result["errors"].append(f"webhook: {exc}")
            logger.warning("notify_dual webhook failed: %s", exc)
    elif notify_wh and not webhook:
        result["webhook"] = "skipped"
        logger.debug("notify_dual webhook skipped: empty FEISHU_BOT_WEBHOOK_TK_HEALTH")

    receive_id = str(
        getattr(cfg, "feishu_im_receive_id", "")
        or getattr(cfg, "feishu_im_user_id_songmin", "")
        or ""
    ).strip()
    id_type = str(getattr(cfg, "feishu_im_receive_id_type", "open_id") or "open_id").strip()
    if notify_im and receive_id:
        try:
            from app.adapters.feishu.im import send_im_post

            await send_im_post(
                receive_id=receive_id,
                title=title_s,
                lines=body_lines,
                receive_id_type=id_type,
            )
            result["im"] = "sent"
            result["any_sent"] = True
        except Exception as exc:  # noqa: BLE001
            result["im"] = "error"
            result["errors"].append(f"im: {exc}")
            logger.warning("notify_dual im failed: %s", exc)
    elif notify_im and not receive_id:
        result["im"] = "skipped"
        logger.info("notify_dual im skipped: FEISHU_IM_RECEIVE_ID empty")

    return result
