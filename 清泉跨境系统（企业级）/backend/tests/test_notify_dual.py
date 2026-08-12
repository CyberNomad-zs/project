"""notify_dual 单元测试（mock 通道）。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.domain import notify_dual


def test_notify_dual_skips_empty_config():
    cfg = SimpleNamespace(
        tk_notify_webhook=True,
        tk_notify_im=True,
        tk_health_notify_feishu=True,
        feishu_bot_webhook_tk_health="",
        feishu_im_receive_id="",
        feishu_im_user_id_songmin="",
        feishu_im_receive_id_type="open_id",
    )

    async def _run():
        return await notify_dual.notify_dual(
            title="t",
            lines=["a"],
            settings=cfg,
            dry_run=False,
        )

    res = asyncio.get_event_loop().run_until_complete(_run())
    assert res["webhook"] == "skipped"
    assert res["im"] == "skipped"
    assert res["any_sent"] is False


def test_notify_dual_dry_run():
    cfg = SimpleNamespace(
        tk_notify_webhook=True,
        tk_notify_im=True,
        tk_health_notify_feishu=True,
        feishu_bot_webhook_tk_health="https://example.com",
        feishu_im_receive_id="ou_x",
        feishu_im_user_id_songmin="",
        feishu_im_receive_id_type="open_id",
    )

    async def _run():
        return await notify_dual.notify_dual(
            title="t",
            lines=["a"],
            settings=cfg,
            dry_run=True,
        )

    res = asyncio.get_event_loop().run_until_complete(_run())
    assert res["webhook"] == "dry_run"
    assert res["any_sent"] is False


def test_notify_dual_master_off():
    cfg = SimpleNamespace(
        tk_notify_webhook=True,
        tk_notify_im=True,
        tk_health_notify_feishu=False,
        feishu_bot_webhook_tk_health="https://example.com",
        feishu_im_receive_id="ou_x",
        feishu_im_user_id_songmin="",
        feishu_im_receive_id_type="open_id",
    )

    async def _run():
        return await notify_dual.notify_dual(
            title="t",
            lines=["a"],
            settings=cfg,
            dry_run=False,
        )

    res = asyncio.get_event_loop().run_until_complete(_run())
    assert res["webhook"] == "skipped"
    assert res["im"] == "skipped"
