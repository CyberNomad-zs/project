"""模拟 Amazon 店铺日经营上报 → fact_amz_shop_daily，验证 Ingest 幂等。

用法:
  set QINGQUAN_URL=http://127.0.0.1:8000
  set QINGQUAN_API_KEY=dev-ingest-key
  python collectors/agent-core/mock_ingest_amz_shop.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qingquan_agent import AgentClient  # noqa: E402

SHOPS = [
    {"shop_id": "AMZ-DEMO-001", "shop_name": "Amazon Demo UK", "currency": "GBP"},
    {"shop_id": "AMZ-DEMO-002", "shop_name": "Amazon Demo DE", "currency": "EUR"},
]


def main() -> None:
    base = os.environ.get("QINGQUAN_URL", "http://127.0.0.1:8000")
    key = os.environ.get("QINGQUAN_API_KEY", "dev-ingest-key")
    client = AgentClient(base, key)

    today = date.today()
    now = datetime.now(timezone.utc).isoformat()
    items: list[dict] = []

    for shop in SHOPS:
        for i in range(14, 0, -1):
            biz = today - timedelta(days=i)
            # 简单波形，便于仪表盘折线
            base_sales = 8000 + (14 - i) * 120 + (hash(shop["shop_id"]) % 500)
            ad_spend = round(base_sales * 0.14, 2)
            ad_sales = round(base_sales * 0.48, 2)
            orders = 180 + (14 - i) * 3
            sales = round(base_sales + (i % 3) * 80, 2)
            items.append(
                {
                    "platform": "amazon",
                    "shop_id": shop["shop_id"],
                    "shop_name": shop["shop_name"],
                    "biz_date": biz.isoformat(),
                    "collected_at": now,
                    "idempotency_key": f"amz_shop_daily:{shop['shop_id']}:{biz.isoformat()}",
                    "payload": {
                        "marketplace": "UK" if shop["currency"] == "GBP" else "DE",
                        "currency": shop["currency"],
                        "sales_amount": sales,
                        "orders_cnt": orders,
                        "units": orders + 20,
                        "sessions": orders * 12,
                        "add_to_cart": orders * 2,
                        "ad_spend": ad_spend,
                        "ad_sales": ad_sales,
                        "acos": round(ad_spend / ad_sales, 4) if ad_sales else None,
                        # 净利润/ROI 口径未定：样例可空或占位
                        "net_profit": None,
                        "roi": None,
                        "row_status": "success",
                    },
                    "evidence": {"source_url": "mock://sellfox/amz_shop_daily"},
                }
            )

    # 附带几条风险告警（T6）
    risk_items = [
        {
            "platform": "amazon",
            "shop_id": SHOPS[0]["shop_id"],
            "shop_name": SHOPS[0]["shop_name"],
            "biz_date": (today - timedelta(days=1)).isoformat(),
            "collected_at": now,
            "idempotency_key": f"amz_risk:{SHOPS[0]['shop_id']}:B0DEMO0001:acos:{(today - timedelta(days=1)).isoformat()}",
            "payload": {
                "alert_key": f"amazon:{SHOPS[0]['shop_id']}:B0DEMO0001:ACoS超标:{(today - timedelta(days=1)).isoformat()}",
                "object_ref": "B0DEMO0001",
                "risk_type": "ACoS超标",
                "priority": "P1",
                "summary": "活动样例 ACoS 47% 超阈值 30%",
                "metric_snapshot": "ACoS 47% / 阈值 30%",
                "status": "open",
                "owner_name": "运营样例",
            },
            "evidence": {"source_url": "mock://rules/amz_risk"},
        },
        {
            "platform": "amazon",
            "shop_id": SHOPS[0]["shop_id"],
            "shop_name": SHOPS[0]["shop_name"],
            "biz_date": (today - timedelta(days=1)).isoformat(),
            "collected_at": now,
            "idempotency_key": f"amz_risk:{SHOPS[0]['shop_id']}:B0DEMO0002:stockout:{(today - timedelta(days=1)).isoformat()}",
            "payload": {
                "alert_key": f"amazon:{SHOPS[0]['shop_id']}:B0DEMO0002:断货:{(today - timedelta(days=1)).isoformat()}",
                "object_ref": "B0DEMO0002",
                "risk_type": "断货",
                "priority": "P0",
                "summary": "FBA 可售 2，可售天数 3",
                "metric_snapshot": "DOS=3",
                "status": "open",
            },
            "evidence": {"source_url": "mock://rules/amz_risk"},
        },
    ]

    client.heartbeat("mock-node-amz-shop", meta={"script": "mock_ingest_amz_shop"})
    r1 = client.report_batch("amz_shop_daily", items)
    r2 = client.report_batch("amz_shop_daily", items[:1])
    rr = client.report_batch("amz_risk_alert", risk_items)

    print("shop first :", {k: r1[k] for k in ("accepted", "duplicated", "failed")})
    if r1.get("failed"):
        fails = [x for x in r1.get("results", []) if x.get("status") == "failed"]
        print("shop failures sample:", fails[:3])
    print("shop second:", {k: r2[k] for k in ("accepted", "duplicated", "failed")})
    print("risk      :", {k: rr[k] for k in ("accepted", "duplicated", "failed")})
    if rr.get("failed"):
        fails = [x for x in rr.get("results", []) if x.get("status") == "failed"]
        print("risk failures sample:", fails[:3])

    assert r1["failed"] == 0, r1
    assert r1["accepted"] + r1["duplicated"] == len(items)
    assert r2["accepted"] == 0 and r2["duplicated"] == 1
    assert rr["failed"] == 0, rr
    print(f"OK: shop_daily={len(items)} rows, risk={len(risk_items)} rows")


if __name__ == "__main__":
    main()
