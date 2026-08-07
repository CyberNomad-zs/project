#!/usr/bin/env python3
"""Smoke test: get token + pull 1 page productAnalyze V2."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import ensure_data_dir, get_settings
from app.clients.sellfox import SellfoxClient, SellfoxError
from app.store.db import Database


def main() -> int:
    settings = get_settings()
    ensure_data_dir(settings)
    if not settings.has_sellfox:
        print("ERROR: 请在 .env 配置 SELLFOX_CLIENT_ID / SELLFOX_CLIENT_SECRET")
        return 2

    day = (date.today() - timedelta(days=1)).isoformat()
    db = Database(settings.db_path)
    try:
        with SellfoxClient(settings, db) as client:
            token = client.get_access_token()
            print(f"OK token: {token[:8]}...{token[-4:]} (len={len(token)})")
            body = {
                "pageNo": "1",
                "pageSize": "5",
                "dimType": "1",
                "subType": "0",
                "startDate": day,
                "endDate": day,
                "compareTypeList": ["1"],
                "fieldModules": [
                    "PRODUCT_INFO",
                    "SALE_INFO",
                    "SESSION_PERFORMANCE_INFO",
                    "AD_INFO",
                ],
                "isNewOrMovingOrInStock": "0",
            }
            data = client.product_analyze_v2_page(body)
            page = data.get("data") or {}
            rows = page.get("rows") or []
            print(
                f"OK productAnalyze V2 date={day} "
                f"totalSize={page.get('totalSize')} sample_rows={len(rows)}"
            )
            if rows:
                sample = rows[0]
                keys = sorted(sample.keys())
                print(f"sample keys ({len(keys)}): {keys[:40]}{'...' if len(keys) > 40 else ''}")
                out = ROOT / "data" / "snapshots" / f"smoke_sample_{day}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(
                    json.dumps(sample, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"wrote {out}")
            return 0
    except SellfoxError as e:
        print(f"SELLFOX ERROR [{e.code}] {e.message}")
        if e.payload:
            print(json.dumps(e.payload, ensure_ascii=False, indent=2)[:2000])
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
