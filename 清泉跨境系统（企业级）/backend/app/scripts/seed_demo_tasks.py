"""灌入跨平台异常任务演示数据（open / in_progress / resolved）。

用法（仓库根目录）:
  $env:DATABASE_URL = "postgresql+asyncpg://qingquan:qingquan@127.0.0.1:5432/qingquan"
  $env:PYTHONPATH = "$PWD\\backend"
  .\\backend\\.venv\\Scripts\\python.exe -m app.scripts.seed_demo_tasks
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text

from app.domain import task_engine
from app.infra.db import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_demo_tasks")

# (platform, anomaly_type, biz_id, title, detail, target_status, shop_external_id)
# target_status: open | in_progress | resolved | cancelled
DEMO_SPECS: list[tuple] = [
    # —— Amazon 环比 / 销售 / 账号 ——
    ("amazon", "link_dod_units_drop", "B0DEMO0001", "[Amazon Demo] B0DEMO0001 日销量环比下降 45%", "上期 12 → 本期 6.6", "open", "AMZ-DEMO-001"),
    ("amazon", "link_wow_units_drop", "B0DEMO0001", "[Amazon Demo] B0DEMO0001 周销量环比下降 70%", "上期 69 → 本期 15", "in_progress", "AMZ-DEMO-001"),
    ("amazon", "link_wow_sales_drop", "B0DEMO0001", "[Amazon Demo] B0DEMO0001 周销售额环比下降 55%", "上期 £800 → 本期 £360", "open", "AMZ-DEMO-001"),
    ("amazon", "link_mom_units_drop", "B0DEMO0002", "[Amazon Demo] B0DEMO0002 月销量环比下降 32%", "上月 150 → 本月 102", "open", "AMZ-DEMO-001"),
    ("amazon", "sales_drop", "B0AX10001", "[Agnis] B0AX10001 销量骤降", "近 3 日销量较上周同窗 -48%", "in_progress", None),
    ("amazon", "stockout_risk", "B0AX10002", "[Agnis] B0AX10002 断货风险", "FBA 可售天数 < 7", "open", None),
    ("amazon", "zero_sales", "B0AX10003", "[Agnis] B0AX10003 连续零销", "连续 5 日 units=0", "open", None),
    ("amazon", "listing_prime", "B0AX10004", "[Agnis] B0AX10004 PRIME 标异常", "前台巡检：PRIME 标缺失", "in_progress", None),
    ("amazon", "listing_image", "B0AX10005", "[Agnis] B0AX10005 主图异常", "主图裂图 / 无法加载", "resolved", None),
    ("amazon", "listing_title", "B0AX10006", "[Agnis] B0AX10006 标题异常", "标题被改 / 违规词", "resolved", None),
    ("amazon", "account_health", "SHOP-PERF-01", "[Amazon] 店铺绩效预警", "迟发率接近阈值", "open", "AMZ-DEMO-001"),
    # —— TikTok 广告 / 运营 ——
    ("tiktok", "low_roi", "拖把7/13", "[Deal to deal] 系列拖把7/13 低 ROI", "ROI 0.8，花费>£100", "in_progress", "27501502216807"),
    ("tiktok", "low_roi", "Kitchen-Mat-A", "[Deal to deal] Kitchen-Mat-A 低 ROI", "ROI 1.1，花费>£80", "open", "27501502216807"),
    ("tiktok", "zero_gmv_spend", "Storage-Sale", "[SHOP INOUT] Storage-Sale 有花费零产出", "Spend>0 GMV=0", "open", "27328767468273"),
    ("tiktok", "campaign_drop", "Pop-Home-01", "[TikTok-Pop] Pop-Home-01 花费突降", "日花费环比 -60%", "open", "27758103898326"),
    ("tiktok", "ads_account", "ADS-ACC-DD", "[Deal to deal] 广告账户异常", "余额不足 / 审核中", "in_progress", "27501502216807"),
    ("tiktok", "low_roi", "Pillow-X", "[SHOP INOUT] Pillow-X 低 ROI 已处理", "已暂停系列", "resolved", "27328767468273"),
    ("tiktok", "product_abnormal", "SKU-TT-88", "[Deal to deal] 商品信息异常", "标题/类目不一致", "open", "27501502216807"),
    # —— Temu 健康 / 下架 / 流量 ——
    ("temu", "listing_off", "GOODS-9001", "[Agnis] GOODS-9001 下架点名", "selectStatus 离开在售", "open", "396706"),
    ("temu", "listing_off", "GOODS-9002", "[HomeCove] GOODS-9002 下架点名", "selectStatus 离开在售", "in_progress", "398202"),
    ("temu", "traffic_watch", "GOODS-9003", "[Agnis] 商品流量待关注增加", "待关注 +12", "open", "396706"),
    ("temu", "traffic_drop", "GOODS-9004", "[Twilight] 流量近期有下降", "下降商品 +8", "open", "398203"),
    ("temu", "on_sale_drop", "MALL-AGNIS", "[Agnis] 在售数量下降", "在售 320 → 298", "in_progress", "396706"),
    ("temu", "listing_off", "GOODS-9005", "[HomeCove] GOODS-9005 下架已恢复", "已重新上架", "resolved", "398202"),
    ("temu", "logistics_abnormal", "PKG-UK-771", "[Agnis] 物流异常包裹", "海外仓迟发", "open", "396706"),
    ("temu", "link_abnormal", "GOODS-9006", "[Twilight] 链接异常", "限流 / 类目风险", "open", "398203"),
    ("temu", "traffic_watch", "GOODS-9007", "[Agnis] 流量待关注已闭环", "已优化主图", "resolved", "396706"),
    ("temu", "on_sale_drop", "MALL-HC", "[HomeCove] 在售波动（取消）", "误报", "cancelled", "398202"),
]


async def _shop_id(db, platform: str, external_id: str | None) -> str | None:
    if not external_id:
        return None
    row = (
        await db.execute(
            text(
                """
                SELECT id::text FROM shop
                WHERE platform = :p AND external_shop_id = :e
                LIMIT 1
                """
            ),
            {"p": platform, "e": external_id},
        )
    ).first()
    return row[0] if row else None


async def _set_status(db, task_id: str, status: str, note: str) -> None:
    now = datetime.now(timezone.utc)
    resolved_at = now if status == "resolved" else None
    await db.execute(
        text(
            """
            UPDATE task
            SET status = :st,
                progress_note = :note,
                updated_at = :now,
                resolved_at = CASE WHEN :st = 'resolved' THEN COALESCE(resolved_at, :now) ELSE resolved_at END
            WHERE id = :id
            """
        ),
        {"st": status, "note": note, "now": now, "id": task_id},
    )
    await db.execute(
        text(
            """
            INSERT INTO task_progress (id, task_id, note, from_status, to_status)
            VALUES (:id, :task_id, :note, 'open', :to_status)
            """
        ),
        {"id": str(uuid4()), "task_id": task_id, "note": note, "to_status": status},
    )


async def run() -> None:
    created = 0
    updated = 0
    async with SessionLocal() as db:
        admin = (
            await db.execute(text("SELECT id::text FROM org_user WHERE username = 'admin' LIMIT 1"))
        ).first()
        owner = admin[0] if admin else None

        for platform, anomaly_type, biz_id, title, detail, target, shop_ext in DEMO_SPECS:
            shop_uuid = await _shop_id(db, platform, shop_ext)
            task = await task_engine.upsert_task_from_anomaly(
                db,
                platform=platform,
                shop_id=shop_uuid,
                anomaly_type=anomaly_type,
                biz_id=biz_id,
                title=title,
                detail=detail,
                payload={"demo": True, "seed": "seed_demo_tasks"},
                owner_user_id=owner,
                severity="warn",
                biz_id_type="asin" if platform == "amazon" else "sku",
            )
            tid = task["id"]
            # upsert 可能把 open 推成 in_progress；按目标状态再校正
            if target == "open":
                await db.execute(
                    text(
                        """
                        UPDATE task SET status = 'open', progress_note = :n, updated_at = now(), resolved_at = NULL
                        WHERE id = :id
                        """
                    ),
                    {"id": tid, "n": detail},
                )
            elif target in ("in_progress", "resolved", "cancelled"):
                note = {
                    "in_progress": f"演示进度：{detail}",
                    "resolved": f"演示闭环：{detail}",
                    "cancelled": f"演示取消：{detail}",
                }[target]
                await _set_status(db, tid, target, note)
            # 打散更新时间便于列表排序更「活」
            hours_ago = created % 48
            await db.execute(
                text("UPDATE task SET updated_at = now() - (:h || ' hours')::interval WHERE id = :id"),
                {"h": str(hours_ago), "id": tid},
            )
            created += 1
            if task.get("status") != "open" or target != "open":
                updated += 1
            logger.info("%s %s %s -> %s", platform, anomaly_type, biz_id, target)

        await db.commit()

        rows = (
            await db.execute(
                text(
                    """
                    SELECT platform, status, COUNT(*)::int
                    FROM task
                    GROUP BY platform, status
                    ORDER BY platform, status
                    """
                )
            )
        ).all()
        logger.info("done specs=%s | distribution:", created)
        for p, s, c in rows:
            logger.info("  %s / %s = %s", p, s, c)


if __name__ == "__main__":
    asyncio.run(run())
