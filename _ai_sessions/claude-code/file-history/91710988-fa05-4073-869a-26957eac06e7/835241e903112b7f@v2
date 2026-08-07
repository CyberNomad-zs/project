"""TK 达人表现异常：从联盟窗口快照生成 anomaly task。

规则（P3.3 · ③ 达人表现）：
  - creator_invest_no_sale       有已采投入（预计佣金）无成交
  - creator_gmv_drop             达人归因 GMV 较上一窗口下降 ≥ 阈值
  - affiliate_creators_sold_drop 店级动销达人数较上一窗口下降 ≥ 阈值
  - creator_refund_high          达人退款/GMV 超阈

语义：biz_date 是窗口锚点；对比同一 creator/shop 在更早 biz_date 的最近一条快照。
禁止把「近 7 天」拆成 7 日再环比。
投入：仅 est_commission；投流/寄样金额暂不采，禁止当 0 判「无投入」。

跳过：测试店名；基线过低；无 creator_id。
幂等：dedupe = tiktok:{shop_ext}:{creator_id|shop}:{code}
异常域：object_type=creator（任务台筛「达人表现」）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.domain import tk_anomaly


def _f(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _drop_ratio(curr: float | None, prev: float | None) -> float | None:
    """返回环比下降比例 (prev-curr)/prev；上涨或无法算返回 None。"""
    if curr is None or prev is None:
        return None
    if prev <= 0:
        return None
    if curr >= prev:
        return None
    return (prev - curr) / prev


def _priority_for_drop(ratio: float, *, p0_ratio: float = 0.5) -> str:
    if ratio >= p0_ratio:
        return "P0"
    if ratio >= 0.2:
        return "P1"
    return "P2"


def _handle_short(handle: str | None, n: int = 24) -> str:
    t = (handle or "").strip()
    if not t:
        return ""
    return t if len(t) <= n else t[: n - 1] + "…"


def _is_test_shop(shop_name: str | None) -> bool:
    low = (shop_name or "").strip().lower()
    return "schema-tk-smoke" in low or low.startswith("[test]")


def classify_creator_row(
    curr: dict[str, Any],
    prev: dict[str, Any] | None,
    *,
    gmv_drop_ratio: float,
    min_gmv_base: float,
    min_commission_invest: float,
    refund_ratio: float,
    min_gmv_for_refund: float,
    p0_drop_ratio: float = 0.5,
) -> list[dict[str, Any]]:
    """达人行：有投入无成交 / GMV 骤降 / 退款异常。"""
    shop_ext = str(curr.get("shop_external_id") or "").strip()
    creator_id = str(curr.get("creator_id") or "").strip()
    if not shop_ext or not creator_id:
        return []

    shop_name = str(curr.get("shop_name") or shop_ext).strip()
    if _is_test_shop(shop_name):
        return []

    handle = str(
        curr.get("creator_handle") or curr.get("creator_name") or creator_id
    ).strip()
    handle_bit = _handle_short(handle) or creator_id
    currency = curr.get("currency") or (prev or {}).get("currency") or "GBP"
    biz = curr.get("biz_date")
    window = curr.get("window_label") or "近7天"

    curr_gmv = _f(curr.get("gmv")) or 0.0
    curr_units = _f(curr.get("order_units")) or 0.0
    curr_orders = _f(curr.get("orders_cnt")) or 0.0
    curr_comm = _f(curr.get("est_commission"))
    curr_refund = _f(curr.get("refund_amount")) or 0.0
    sold_flag = curr.get("sold_flag")
    if sold_flag is None:
        sold_flag = curr_gmv > 0 or curr_units > 0

    hits: list[dict[str, Any]] = []

    # —— 有投入无成交：仅用已采 est_commission；投流/寄样金额不参与 ——
    if (
        curr_comm is not None
        and curr_comm >= min_commission_invest
        and (not sold_flag)
        and curr_gmv <= 0
        and curr_units <= 0
    ):
        metric = (
            f"est_commission={curr_comm:.2f} gmv=0 order_units=0 "
            f"sold_flag={sold_flag} window={window} creator_id={creator_id}"
        )
        detail = (
            f"{biz} 达人 {handle_bit} 预计佣金 {curr_comm:.2f}{currency} "
            f"但归因 GMV/成交件均为 0（投入阈值≥{min_commission_invest:.2f}；"
            f"投流/寄样金额暂不采）"
        )
        hits.append(
            {
                "anomaly_code": "creator_invest_no_sale",
                "priority": "P1",
                "summary": f"达人有投入无成交 · {shop_name} · {handle_bit}",
                "metric_snapshot": metric,
                "detail": detail,
                "current_value": curr_comm,
                "current_value_label": "预计佣金",
                "compare_value": 0.0,
                "compare_value_label": "归因GMV",
                "change_magnitude_label": "有投入无成交",
                "description": f"{detail} | {metric}",
            }
        )

    # —— 退款异常：不依赖 prev ——
    if (
        curr_gmv >= min_gmv_for_refund
        and curr_refund > 0
        and refund_ratio > 0
        and (curr_refund / curr_gmv) >= refund_ratio
    ):
        rr = (curr_refund / curr_gmv) * 100
        metric = (
            f"refund={curr_refund:.2f} gmv={curr_gmv:.2f} refund_ratio={rr:.1f}% "
            f"currency={currency} creator_id={creator_id}"
        )
        detail = (
            f"{biz} 达人 {handle_bit} 退款 {curr_refund:.2f}{currency} / "
            f"GMV {curr_gmv:.2f} = {rr:.1f}%（阈值 {refund_ratio * 100:.0f}%）"
        )
        hits.append(
            {
                "anomaly_code": "creator_refund_high",
                "priority": "P2" if rr < 80 else "P1",
                "summary": f"达人退款异常 · {shop_name} · {handle_bit}",
                "metric_snapshot": metric,
                "detail": detail,
                "current_value": curr_refund,
                "current_value_label": "退款金额",
                "compare_value": curr_gmv,
                "compare_value_label": "归因GMV",
                "change_magnitude": rr,
                "change_magnitude_label": "退款/GMV%",
                "description": f"{detail} | {metric}",
            }
        )

    if not prev:
        return hits

    prev_biz = prev.get("biz_date")
    prev_gmv = _f(prev.get("gmv"))
    # curr gmv 字段缺失时按 0 与 prev 比
    curr_gmv_raw = _f(curr.get("gmv"))
    if curr.get("gmv") is None and prev_gmv is not None:
        gmv_ratio = _drop_ratio(0.0, prev_gmv)
        curr_gmv_cmp = 0.0
    else:
        gmv_ratio = _drop_ratio(curr_gmv_raw, prev_gmv)
        curr_gmv_cmp = curr_gmv_raw if curr_gmv_raw is not None else 0.0

    if (
        gmv_ratio is not None
        and prev_gmv is not None
        and prev_gmv >= min_gmv_base
        and gmv_ratio >= gmv_drop_ratio
    ):
        pri = _priority_for_drop(gmv_ratio, p0_ratio=p0_drop_ratio)
        pct = gmv_ratio * 100
        metric = (
            f"gmv={curr_gmv_cmp:.2f} prev_gmv={prev_gmv:.2f} drop={pct:.1f}% "
            f"currency={currency} prev_date={prev_biz} creator_id={creator_id}"
        )
        detail = (
            f"{biz} 达人 {handle_bit} 归因 GMV {curr_gmv_cmp:.2f}{currency} "
            f"较上一窗 {prev_biz} {prev_gmv:.2f} 下降 {pct:.1f}% "
            f"（阈值 {gmv_drop_ratio * 100:.0f}%）"
        )
        hits.append(
            {
                "anomaly_code": "creator_gmv_drop",
                "priority": pri,
                "summary": f"达人归因GMV骤降 · {shop_name} · {handle_bit}",
                "metric_snapshot": metric,
                "detail": detail,
                "current_value": curr_gmv_cmp,
                "current_value_label": "归因GMV",
                "compare_value": prev_gmv,
                "compare_value_label": "上一窗归因GMV",
                "change_magnitude": pct,
                "change_magnitude_label": "环比下降%",
                "needs_boss_decision": pri == "P0",
                "description": f"{detail} | {metric}",
            }
        )

    return hits


def classify_shop_affiliate_pair(
    curr: dict[str, Any],
    prev: dict[str, Any] | None,
    *,
    creators_sold_drop_ratio: float,
    min_creators_sold_base: float,
    p0_drop_ratio: float = 0.5,
) -> list[dict[str, Any]]:
    """店级联盟窗：动销达人数下降。"""
    shop_ext = str(curr.get("shop_external_id") or "").strip()
    if not shop_ext or not prev:
        return []
    shop_name = str(curr.get("shop_name") or shop_ext).strip()
    if _is_test_shop(shop_name):
        return []

    biz = curr.get("biz_date")
    prev_biz = prev.get("biz_date")
    window = curr.get("window_label") or "近7天"
    curr_sold = _f(curr.get("creators_sold"))
    prev_sold = _f(prev.get("creators_sold"))
    ratio = _drop_ratio(curr_sold, prev_sold)
    if (
        ratio is None
        or prev_sold is None
        or prev_sold < min_creators_sold_base
        or ratio < creators_sold_drop_ratio
    ):
        return []

    pri = _priority_for_drop(ratio, p0_ratio=p0_drop_ratio)
    pct = ratio * 100
    metric = (
        f"creators_sold={curr_sold} prev={prev_sold} drop={pct:.1f}% "
        f"window={window} prev_date={prev_biz}"
    )
    detail = (
        f"{biz} 店 {shop_name} 动销达人 {curr_sold:.0f} "
        f"较上一窗 {prev_biz} {prev_sold:.0f} 下降 {pct:.1f}% "
        f"（阈值 {creators_sold_drop_ratio * 100:.0f}%）"
    )
    return [
        {
            "anomaly_code": "affiliate_creators_sold_drop",
            "priority": pri,
            "summary": f"动销达人数下降 · {shop_name}",
            "metric_snapshot": metric,
            "detail": detail,
            "current_value": float(curr_sold) if curr_sold is not None else None,
            "current_value_label": "动销达人数",
            "compare_value": float(prev_sold) if prev_sold is not None else None,
            "compare_value_label": "上一窗动销达人",
            "change_magnitude": pct,
            "change_magnitude_label": "环比下降%",
            "needs_boss_decision": pri == "P0",
            "description": f"{detail} | {metric}",
        }
    ]


@dataclass
class AffiliateEvalStats:
    biz_date: str
    scanned_creators: int = 0
    scanned_shops: int = 0
    hit_invest_no_sale: int = 0
    hit_gmv_drop: int = 0
    hit_creators_sold_drop: int = 0
    hit_refund_high: int = 0
    created_or_updated: int = 0
    skipped: int = 0
    missing_prev: int = 0
    errors: list[str] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "biz_date": self.biz_date,
            "scanned": self.scanned_creators + self.scanned_shops,
            "scanned_creators": self.scanned_creators,
            "scanned_shops": self.scanned_shops,
            "hit_invest_no_sale": self.hit_invest_no_sale,
            "hit_gmv_drop": self.hit_gmv_drop,
            "hit_creators_sold_drop": self.hit_creators_sold_drop,
            "hit_refund_high": self.hit_refund_high,
            "created_or_updated": self.created_or_updated,
            "skipped": self.skipped,
            "missing_prev": self.missing_prev,
            "errors": self.errors[:20],
            "samples": self.samples[:10],
        }


async def resolve_affiliate_biz_date(db: AsyncSession, biz_date: date | None) -> date:
    if biz_date:
        return biz_date
    row = (
        await db.execute(
            text(
                """
                SELECT GREATEST(
                    (SELECT MAX(biz_date) FROM tk.fact_tiktok_affiliate_creator_daily),
                    (SELECT MAX(biz_date) FROM tk.fact_tiktok_affiliate_daily)
                )
                """
            )
        )
    ).first()
    if row and row[0]:
        return row[0]
    return datetime.now(timezone.utc).date()


async def fetch_creator_daily_rows(
    db: AsyncSession,
    *,
    biz_date: date,
    shop_external_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["biz_date = :biz_date"]
    params: dict[str, Any] = {"biz_date": biz_date}
    if shop_external_id:
        clauses.append("shop_external_id = :shop_external_id")
        params["shop_external_id"] = shop_external_id
    rows = (
        await db.execute(
            text(
                f"""
                SELECT
                    id::text,
                    shop_id::text,
                    shop_external_id,
                    shop_name,
                    biz_date,
                    window_label,
                    creator_id,
                    creator_name,
                    creator_handle,
                    gmv,
                    order_units,
                    orders_cnt,
                    refund_amount,
                    refund_units,
                    est_commission,
                    video_cnt,
                    live_cnt,
                    product_sold,
                    samples_shipped,
                    video_views,
                    cvr,
                    sold_flag,
                    currency,
                    source_url
                FROM tk.fact_tiktok_affiliate_creator_daily
                WHERE {' AND '.join(clauses)}
                ORDER BY gmv DESC NULLS LAST, est_commission DESC NULLS LAST, creator_id
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_prev_creator_daily_map(
    db: AsyncSession,
    *,
    biz_date: date,
    keys: list[tuple[str, str, str]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """keys = (shop_external_id, window_label, creator_id)。"""
    if not keys:
        return {}
    shops = sorted({k[0] for k in keys})
    rows = (
        await db.execute(
            text(
                """
                SELECT DISTINCT ON (shop_external_id, window_label, creator_id)
                    id::text,
                    shop_id::text,
                    shop_external_id,
                    shop_name,
                    biz_date,
                    window_label,
                    creator_id,
                    creator_name,
                    creator_handle,
                    gmv,
                    order_units,
                    orders_cnt,
                    refund_amount,
                    refund_units,
                    est_commission,
                    sold_flag,
                    currency,
                    source_url
                FROM tk.fact_tiktok_affiliate_creator_daily
                WHERE shop_external_id = ANY(:shops)
                  AND biz_date < :biz_date
                ORDER BY shop_external_id, window_label, creator_id, biz_date DESC
                """
            ),
            {"shops": shops, "biz_date": biz_date},
        )
    ).mappings().all()
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    want = set(keys)
    for r in rows:
        k = (
            str(r["shop_external_id"]),
            str(r["window_label"] or "近7天"),
            str(r["creator_id"]),
        )
        if k in want:
            out[k] = dict(r)
    return out


async def fetch_shop_affiliate_rows(
    db: AsyncSession,
    *,
    biz_date: date,
    shop_external_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["biz_date = :biz_date"]
    params: dict[str, Any] = {"biz_date": biz_date}
    if shop_external_id:
        clauses.append("shop_external_id = :shop_external_id")
        params["shop_external_id"] = shop_external_id
    rows = (
        await db.execute(
            text(
                f"""
                SELECT
                    id::text,
                    shop_id::text,
                    shop_external_id,
                    shop_name,
                    biz_date,
                    window_label,
                    gmv_affiliate,
                    order_units,
                    refund_amount,
                    video_cnt,
                    live_cnt,
                    creators_published,
                    creators_sold,
                    est_commission,
                    currency,
                    source_url
                FROM tk.fact_tiktok_affiliate_daily
                WHERE {' AND '.join(clauses)}
                ORDER BY creators_sold DESC NULLS LAST, shop_external_id
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_prev_shop_affiliate_map(
    db: AsyncSession,
    *,
    biz_date: date,
    keys: list[tuple[str, str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """keys = (shop_external_id, window_label)。"""
    if not keys:
        return {}
    shops = sorted({k[0] for k in keys})
    rows = (
        await db.execute(
            text(
                """
                SELECT DISTINCT ON (shop_external_id, window_label)
                    id::text,
                    shop_id::text,
                    shop_external_id,
                    shop_name,
                    biz_date,
                    window_label,
                    gmv_affiliate,
                    creators_published,
                    creators_sold,
                    est_commission,
                    currency,
                    source_url
                FROM tk.fact_tiktok_affiliate_daily
                WHERE shop_external_id = ANY(:shops)
                  AND biz_date < :biz_date
                ORDER BY shop_external_id, window_label, biz_date DESC
                """
            ),
            {"shops": shops, "biz_date": biz_date},
        )
    ).mappings().all()
    out: dict[tuple[str, str], dict[str, Any]] = {}
    want = set(keys)
    for r in rows:
        k = (str(r["shop_external_id"]), str(r["window_label"] or "近7天"))
        if k in want:
            out[k] = dict(r)
    return out


async def evaluate_affiliate_anomalies(
    db: AsyncSession,
    *,
    biz_date: date | None = None,
    shop_external_id: str | None = None,
    project_center_task: bool = True,
    dry_run: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """扫描联盟达人/店级窗口事实并写入/更新 ③ 达人表现类异常任务。"""
    cfg = settings or get_settings()
    day = await resolve_affiliate_biz_date(db, biz_date)
    stats = AffiliateEvalStats(biz_date=day.isoformat())

    gmv_drop_ratio = float(cfg.tk_affiliate_gmv_drop_ratio)
    min_gmv_base = float(cfg.tk_affiliate_min_gmv_base)
    min_commission = float(cfg.tk_affiliate_min_commission_invest)
    refund_ratio = float(cfg.tk_affiliate_refund_ratio)
    min_gmv_refund = float(cfg.tk_affiliate_min_gmv_for_refund)
    creators_sold_drop = float(cfg.tk_affiliate_creators_sold_drop_ratio)
    min_creators_sold = float(cfg.tk_affiliate_min_creators_sold_base)
    p0_drop_ratio = float(cfg.tk_affiliate_p0_drop_ratio)

    # —— 达人行 ——
    creators = await fetch_creator_daily_rows(
        db, biz_date=day, shop_external_id=shop_external_id
    )
    stats.scanned_creators = len(creators)
    c_keys = [
        (
            str(r.get("shop_external_id") or "").strip(),
            str(r.get("window_label") or "近7天"),
            str(r.get("creator_id") or "").strip(),
        )
        for r in creators
        if r.get("shop_external_id") and r.get("creator_id")
    ]
    prev_creators = await fetch_prev_creator_daily_map(db, biz_date=day, keys=c_keys)

    for row in creators:
        shop_ext = str(row.get("shop_external_id") or "").strip()
        creator_id = str(row.get("creator_id") or "").strip()
        window = str(row.get("window_label") or "近7天")
        if not shop_ext or not creator_id:
            stats.skipped += 1
            continue

        key = (shop_ext, window, creator_id)
        prev = prev_creators.get(key)
        if not prev:
            stats.missing_prev += 1

        hits = classify_creator_row(
            row,
            prev,
            gmv_drop_ratio=gmv_drop_ratio,
            min_gmv_base=min_gmv_base,
            min_commission_invest=min_commission,
            refund_ratio=refund_ratio,
            min_gmv_for_refund=min_gmv_refund,
            p0_drop_ratio=p0_drop_ratio,
        )
        if not hits:
            stats.skipped += 1
            continue

        for hit in hits:
            code = hit["anomaly_code"]
            if code == "creator_invest_no_sale":
                stats.hit_invest_no_sale += 1
            elif code == "creator_gmv_drop":
                stats.hit_gmv_drop += 1
            elif code == "creator_refund_high":
                stats.hit_refund_high += 1

            sample = {
                "shop_external_id": shop_ext,
                "shop_name": row.get("shop_name"),
                "creator_id": creator_id,
                "anomaly_code": code,
                "priority": hit["priority"],
                "metric_snapshot": hit["metric_snapshot"],
                "domain": "达人表现",
            }
            if dry_run:
                stats.samples.append(sample)
                stats.created_or_updated += 1
                continue
            try:
                task = await tk_anomaly.create_anomaly_task(
                    db,
                    anomaly_code=code,
                    summary=hit["summary"],
                    shop_id=row.get("shop_id"),
                    shop_external_id=shop_ext,
                    shop_name=row.get("shop_name"),
                    object_ref=creator_id,
                    object_type="creator",
                    product_name=row.get("creator_name") or row.get("creator_handle"),
                    priority=hit["priority"],
                    progress_note=hit["detail"],
                    metric_snapshot=hit["metric_snapshot"],
                    biz_date=day,
                    dedupe_key=f"tiktok:{shop_ext}:{creator_id}:{code}",
                    source_url=row.get("source_url"),
                    project_center_task=project_center_task,
                    current_value=hit.get("current_value"),
                    current_value_label=hit.get("current_value_label"),
                    compare_value=hit.get("compare_value"),
                    compare_value_label=hit.get("compare_value_label"),
                    change_magnitude=hit.get("change_magnitude"),
                    change_magnitude_label=hit.get("change_magnitude_label"),
                    needs_boss_decision=hit.get("needs_boss_decision"),
                    description=hit.get("description"),
                )
                sample["task_id"] = task.get("id")
                sample["task_key"] = task.get("task_key")
                sample["status"] = task.get("status")
                stats.samples.append(sample)
                stats.created_or_updated += 1
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"{shop_ext}/{creator_id}/{code}: {exc}")

    # —— 店级动销达人 ——
    shops = await fetch_shop_affiliate_rows(
        db, biz_date=day, shop_external_id=shop_external_id
    )
    stats.scanned_shops = len(shops)
    s_keys = [
        (
            str(r.get("shop_external_id") or "").strip(),
            str(r.get("window_label") or "近7天"),
        )
        for r in shops
        if r.get("shop_external_id")
    ]
    prev_shops = await fetch_prev_shop_affiliate_map(db, biz_date=day, keys=s_keys)

    for row in shops:
        shop_ext = str(row.get("shop_external_id") or "").strip()
        window = str(row.get("window_label") or "近7天")
        if not shop_ext:
            stats.skipped += 1
            continue
        prev = prev_shops.get((shop_ext, window))
        if not prev:
            stats.missing_prev += 1
        hits = classify_shop_affiliate_pair(
            row,
            prev,
            creators_sold_drop_ratio=creators_sold_drop,
            min_creators_sold_base=min_creators_sold,
            p0_drop_ratio=p0_drop_ratio,
        )
        if not hits:
            stats.skipped += 1
            continue
        for hit in hits:
            code = hit["anomaly_code"]
            stats.hit_creators_sold_drop += 1
            sample = {
                "shop_external_id": shop_ext,
                "shop_name": row.get("shop_name"),
                "creator_id": None,
                "anomaly_code": code,
                "priority": hit["priority"],
                "metric_snapshot": hit["metric_snapshot"],
                "domain": "达人表现",
            }
            if dry_run:
                stats.samples.append(sample)
                stats.created_or_updated += 1
                continue
            try:
                task = await tk_anomaly.create_anomaly_task(
                    db,
                    anomaly_code=code,
                    summary=hit["summary"],
                    shop_id=row.get("shop_id"),
                    shop_external_id=shop_ext,
                    shop_name=row.get("shop_name"),
                    object_ref=shop_ext,
                    object_type="creator",
                    priority=hit["priority"],
                    progress_note=hit["detail"],
                    metric_snapshot=hit["metric_snapshot"],
                    biz_date=day,
                    dedupe_key=f"tiktok:{shop_ext}:shop:{code}",
                    source_url=row.get("source_url"),
                    project_center_task=project_center_task,
                    current_value=hit.get("current_value"),
                    current_value_label=hit.get("current_value_label"),
                    compare_value=hit.get("compare_value"),
                    compare_value_label=hit.get("compare_value_label"),
                    change_magnitude=hit.get("change_magnitude"),
                    change_magnitude_label=hit.get("change_magnitude_label"),
                    needs_boss_decision=hit.get("needs_boss_decision"),
                    description=hit.get("description"),
                )
                sample["task_id"] = task.get("id")
                sample["task_key"] = task.get("task_key")
                sample["status"] = task.get("status")
                stats.samples.append(sample)
                stats.created_or_updated += 1
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"{shop_ext}/shop/{code}: {exc}")

    return {
        **stats.as_dict(),
        "thresholds": {
            "gmv_drop_ratio": gmv_drop_ratio,
            "min_gmv_base": min_gmv_base,
            "min_commission_invest": min_commission,
            "refund_ratio": refund_ratio,
            "min_gmv_for_refund": min_gmv_refund,
            "creators_sold_drop_ratio": creators_sold_drop,
            "min_creators_sold_base": min_creators_sold,
            "p0_drop_ratio": p0_drop_ratio,
        },
        "dry_run": dry_run,
        "domain": "达人表现",
        "note": "投入仅预计佣金；投流/寄样金额暂不采；窗口快照非日均摊",
    }
