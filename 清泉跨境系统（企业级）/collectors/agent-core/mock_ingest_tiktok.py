"""模拟 TK 广告上报，验证 Ingest 幂等。

用法:
  set QINGQUAN_URL=http://127.0.0.1:8000
  set QINGQUAN_API_KEY=dev-ingest-key
  python collectors/agent-core/mock_ingest_tiktok.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qingquan_agent import AgentClient  # noqa: E402


def main() -> None:
    base = os.environ.get("QINGQUAN_URL", "http://127.0.0.1:8000")
    key = os.environ.get("QINGQUAN_API_KEY", "dev-ingest-key")
    client = AgentClient(base, key)

    biz = (date.today() - timedelta(days=1)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    store_id = "27501502216807"
    campaign = "拖把7/13"
    item = {
        "platform": "tiktok",
        "shop_id": store_id,
        "shop_name": "Deal to deal",
        "biz_date": biz,
        "collected_at": now,
        "idempotency_key": f"tiktok_ads:{store_id}:{campaign}:{biz}",
        "payload": {
            "campaign_name": campaign,
            "spend": 187.79,
            "orders": 121,
            "roi": 9.9,
            "revenue": 1872.64,
            "row_status": "success",
            "currency": "GBP",
        },
        "evidence": {
            "source_url": "https://seller-uk.tiktok.com/ads-creation/dashboard",
        },
    }

    client.heartbeat("mock-node-dev", meta={"script": "mock_ingest_tiktok"})
    r1 = client.report_batch("tiktok_ads", [item])
    r2 = client.report_batch("tiktok_ads", [item])
    print("first :", r1)
    print("second:", r2)
    assert r1["accepted"] == 1 and r1["duplicated"] == 0
    assert r2["accepted"] == 0 and r2["duplicated"] == 1
    print("OK: idempotency verified")


if __name__ == "__main__":
    main()
