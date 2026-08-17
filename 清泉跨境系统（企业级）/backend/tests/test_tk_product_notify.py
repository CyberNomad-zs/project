"""商品断货/库存异常的通知（notify_dual）测试。

不连 DB：monkeypatch fetch_product_rows / _open_exists / create_anomaly_task / notify_dual，
验证 (a) 断货命中时 notify_dual 被调且 lines 含「商品ID：{pid}」；
(b) _open_exists=True 时不 notify；(c) notify=False 时不 notify；(d) dry_run 不实发但统计 notified。
"""

from __future__ import annotations

import pytest

import app.domain.tk_product_rules as mod
from app.domain.tk_product_rules import evaluate_product_anomalies


class _FakeDB:
    """evaluate_product_anomalies 只把 db 透传给 fetch_product_rows / _open_exists /
    create_anomaly_task，全部被 monkeypatch 接管，db 本身无需真实。"""

    pass


def _row(pid: str, *, stock: float, status: str = "active", name: str = "测商品") -> dict:
    return {
        "id": "rid-" + pid,
        "shop_id": "sid-1",
        "shop_external_id": "27501502216807",
        "shop_name": "Deal to deal",
        "product_id": pid,
        "product_name": name,
        "seller_sku": "SKU-" + pid,
        "status": status,
        "stock_qty": stock,
        "price": 9.9,
        "currency": "GBP",
        "sales_qty": 3,
        "source_url": "https://shop.tiktok.com/product/" + pid,
        "updated_at": None,
    }


@pytest.mark.asyncio
async def test_stockout_notifies_with_product_id(monkeypatch):
    """断货命中：notify_dual 被调，lines 含「商品ID：{pid}」，title 含「断货」。"""
    captured = {}

    async def _fake_fetch(db, *, shop_external_id=None):
        return [_row("1729719490635012272", stock=0)]

    async def _fake_open_exists(db, dedupe_key):
        return False  # 新异常，未闭环

    async def _fake_create(db, **kw):
        return {"id": "task-1", "task_key": "TK1", "status": "open"}

    async def _fake_notify(*, title, lines, settings=None, dry_run=False, force_notify=True):
        captured["title"] = title
        captured["lines"] = lines
        return {"webhook": "sent", "im": "sent", "any_sent": True, "errors": []}

    monkeypatch.setattr(mod, "fetch_product_rows", _fake_fetch)
    monkeypatch.setattr(mod, "_open_exists", _fake_open_exists)
    monkeypatch.setattr(mod.tk_anomaly, "create_anomaly_task", _fake_create)

    # notify_dual 在 evaluate 函数内 from app.domain.notify_dual import——patch 源模块符号
    import app.domain.notify_dual as nd

    monkeypatch.setattr(nd, "notify_dual", _fake_notify)

    res = await evaluate_product_anomalies(
        _FakeDB(), notify=True, dry_run=False, settings=mod.get_settings()
    )

    assert res["hit_stockout"] == 1
    assert res["notified"] == 1
    assert "断货" in captured["title"]
    # 关键：lines 含商品ID 行，且值=product_id
    pid_line = [ln for ln in captured["lines"] if ln.startswith("商品ID：")]
    assert pid_line == ["商品ID：1729719490635012272"]
    # 链接行保留 source_url
    link_line = [ln for ln in captured["lines"] if ln.startswith("链接：")]
    assert link_line == ["链接：https://shop.tiktok.com/product/1729719490635012272"]


@pytest.mark.asyncio
async def test_no_notify_when_already_open(monkeypatch):
    """_open_exists=True（未闭环已存在）→ 不 notify，notify_skipped 计数。"""
    called = {"notify": False}

    async def _fake_fetch(db, *, shop_external_id=None):
        return [_row("p1", stock=0)]

    async def _fake_open_exists(db, dedupe_key):
        return True  # 已存在未闭环

    async def _fake_create(db, **kw):
        return {"id": "t", "task_key": "k", "status": "open"}

    async def _fake_notify(*, title, lines, settings=None, dry_run=False, force_notify=True):
        called["notify"] = True
        return {"any_sent": True}

    monkeypatch.setattr(mod, "fetch_product_rows", _fake_fetch)
    monkeypatch.setattr(mod, "_open_exists", _fake_open_exists)
    monkeypatch.setattr(mod.tk_anomaly, "create_anomaly_task", _fake_create)
    import app.domain.notify_dual as nd

    monkeypatch.setattr(nd, "notify_dual", _fake_notify)

    res = await evaluate_product_anomalies(
        _FakeDB(), notify=True, dry_run=False, settings=mod.get_settings()
    )

    assert called["notify"] is False
    assert res["notified"] == 0
    assert res["notify_skipped"] == 1


@pytest.mark.asyncio
async def test_no_notify_when_disabled(monkeypatch):
    """notify=False → 即使新异常也不 notify。"""
    called = {"notify": False}

    async def _fake_fetch(db, *, shop_external_id=None):
        return [_row("p1", stock=0)]

    async def _fake_open_exists(db, dedupe_key):
        return False

    async def _fake_create(db, **kw):
        return {"id": "t", "task_key": "k", "status": "open"}

    async def _fake_notify(*, title, lines, settings=None, dry_run=False, force_notify=True):
        called["notify"] = True
        return {"any_sent": True}

    monkeypatch.setattr(mod, "fetch_product_rows", _fake_fetch)
    monkeypatch.setattr(mod, "_open_exists", _fake_open_exists)
    monkeypatch.setattr(mod.tk_anomaly, "create_anomaly_task", _fake_create)
    import app.domain.notify_dual as nd

    monkeypatch.setattr(nd, "notify_dual", _fake_notify)

    res = await evaluate_product_anomalies(
        _FakeDB(), notify=False, dry_run=False, settings=mod.get_settings()
    )

    assert called["notify"] is False
    assert res["notified"] == 0
    assert res["notify_skipped"] == 1


@pytest.mark.asyncio
async def test_dry_run_counts_notified_without_sending(monkeypatch):
    """dry_run：不实写任务、不实发通知，但 will_notify 命中时统计 notified。"""
    called = {"create": False, "notify": False}

    async def _fake_fetch(db, *, shop_external_id=None):
        return [_row("p1", stock=0), _row("p2", stock=4)]

    async def _fake_open_exists(db, dedupe_key):
        return False

    async def _fake_create(db, **kw):
        called["create"] = True
        return {"id": "t", "task_key": "k", "status": "open"}

    async def _fake_notify(*, title, lines, settings=None, dry_run=False, force_notify=True):
        called["notify"] = True
        return {"any_sent": True}

    monkeypatch.setattr(mod, "fetch_product_rows", _fake_fetch)
    monkeypatch.setattr(mod, "_open_exists", _fake_open_exists)
    monkeypatch.setattr(mod.tk_anomaly, "create_anomaly_task", _fake_create)
    import app.domain.notify_dual as nd

    monkeypatch.setattr(nd, "notify_dual", _fake_notify)

    res = await evaluate_product_anomalies(
        _FakeDB(), notify=True, dry_run=True, settings=mod.get_settings()
    )

    assert called["create"] is False  # dry_run 不建任务
    assert called["notify"] is False  # dry_run 不实发
    # 断货 + 低库存两条都 will_notify
    assert res["notified"] == 2
    assert res["hit_stockout"] == 1
    assert res["hit_stock_low"] == 1
    # sample 带 will_notify 字段
    assert all("will_notify" in s for s in res["samples"])


@pytest.mark.asyncio
async def test_stock_low_notifies_with_title_low(monkeypatch):
    """库存不足命中：title 含「库存不足」。"""
    captured = {}

    async def _fake_fetch(db, *, shop_external_id=None):
        return [_row("p1", stock=4)]

    async def _fake_open_exists(db, dedupe_key):
        return False

    async def _fake_create(db, **kw):
        return {"id": "t", "task_key": "k", "status": "open"}

    async def _fake_notify(*, title, lines, settings=None, dry_run=False, force_notify=True):
        captured["title"] = title
        return {"any_sent": True}

    monkeypatch.setattr(mod, "fetch_product_rows", _fake_fetch)
    monkeypatch.setattr(mod, "_open_exists", _fake_open_exists)
    monkeypatch.setattr(mod.tk_anomaly, "create_anomaly_task", _fake_create)
    import app.domain.notify_dual as nd

    monkeypatch.setattr(nd, "notify_dual", _fake_notify)

    res = await evaluate_product_anomalies(
        _FakeDB(), notify=True, dry_run=False, settings=mod.get_settings()
    )

    assert res["hit_stock_low"] == 1
    assert res["notified"] == 1
    assert "库存不足" in captured["title"]
