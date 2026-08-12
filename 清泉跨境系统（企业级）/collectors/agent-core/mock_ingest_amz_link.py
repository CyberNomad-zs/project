"""模拟 Amazon 链接日指标上报 → fact_amz_link_daily，验证 Ingest 幂等与 upsert。

用法:
  set QINGQUAN_URL=http://127.0.0.1:8000
  set QINGQUAN_API_KEY=dev-ingest-key
  python collectors/agent-core/mock_ingest_amz_link.py

会写入约 14 天 × 2 个 ASIN，便于后续切片 C 环比扫描有数据。
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qingquan_agent import AgentClient  # noqa: E402

SHOP_ID = "AMZ-DEMO-001"
SHOP_NAME = "Amazon Demo UK"
ASINS = [
    {
        "asin": "B0DEMO0001",
        "seller_sku": "DEMO-SKU-001",
        "title": "Demo Mop Pad",
        # 近两周：前高后低，便于 week 环比触发
        "units_series": [8, 9, 10, 11, 12, 10, 9, 3, 2, 2, 3, 2, 1, 2],
        "price": 12.5,
    },
    {
        "asin": "B0DEMO0002",
        "seller_sku": "DEMO-SKU-002",
        "title": "Demo Storage Box",
        "units_series": [5, 5, 6, 5, 5, 4, 5, 5, 4, 5, 6, 5, 5, 4],
        "price": 22.0,
    },
]


def main() -> None:
    base = os.environ.get("QINGQUAN_URL", "http://127.0.0.1:8000")
    key = os.environ.get("QINGQUAN_API_KEY", "dev-ingest-key")
    client = AgentClient(base, key)

    today = date.today()
    now = datetime.now(timezone.utc).isoformat()
    items: list[dict] = []

    for meta in ASINS:
        series = meta["units_series"]
        n = len(series)
        for i, units in enumerate(series):
            biz = today - timedelta(days=(n - i))
            asin = meta["asin"]
            sales = round(units * float(meta["price"]), 2)
            items.append(
                {
                    "platform": "amazon",
                    "shop_id": SHOP_ID,
                    "shop_name": SHOP_NAME,
                    "biz_date": biz.isoformat(),
                    "collected_at": now,
                    "idempotency_key": f"amz_link_daily:{SHOP_ID}:{asin}:{biz.isoformat()}",
                    "payload": {
                        "asin": asin,
                        "seller_sku": meta["seller_sku"],
                        "title": meta["title"],
                        "units": units,
                        "sales_amount": sales,
                        "currency": "GBP",
                        "fba_fulfillable": 40 - i,
                    },
                    "evidence": {"source_url": "mock://sellfox/amz_link_daily"},
                }
            )

    client.heartbeat("mock-node-amz", meta={"script": "mock_ingest_amz_link"})
    r1 = client.report_batch("amz_link_daily", items)
    # 幂等：同一批再报一次
    r2 = client.report_batch("amz_link_daily", items[:1])

    print("batch first :", {k: r1[k] for k in ("accepted", "duplicated", "failed")})
    if r1.get("failed"):
        fails = [x for x in r1.get("results", []) if x.get("status") == "failed"]
        print("failures sample:", fails[:3])
    print("one second  :", {k: r2[k] for k in ("accepted", "duplicated", "failed")})

    assert r1["failed"] == 0, r1
    assert r1["accepted"] + r1["duplicated"] == len(items)
    assert r2["accepted"] == 0 and r2["duplicated"] == 1
    print(f"OK: ingested {len(items)} amz link-daily rows (idempotency verified)")


if __name__ == "__main__":
    main()
