#!/usr/bin/env python3
"""生成集团总览 + 各店静态仪表盘 HTML。

用法:
  python scripts/build_dashboard.py
  python scripts/build_dashboard.py --date 2026-07-21
  python scripts/build_dashboard.py --open   # Windows 打开 index.html
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import ensure_data_dir, get_settings
from app.dashboard.data import build_group_payload, build_shop_payload, latest_biz_date
from app.dashboard.render import write_dashboard_site
from app.store.db import Database
from app.sync.shops import list_canonical_shops_from_db


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 ASIN 健康度仪表盘静态页")
    parser.add_argument("--date", dest="biz_date", default=None, help="业务日 YYYY-MM-DD")
    parser.add_argument(
        "--out",
        default="",
        help="输出目录，默认 data/dashboard",
    )
    parser.add_argument("--open", action="store_true", help="生成后打开 index.html")
    parser.add_argument("--trend-days", type=int, default=7)
    args = parser.parse_args()

    settings = get_settings()
    ensure_data_dir(settings)
    db = Database(settings.db_path)
    day = args.biz_date or latest_biz_date(db)
    if not day:
        print("ERROR: asin_daily 无数据，请先 sync")
        return 2

    out_dir = Path(args.out) if args.out else Path(settings.data_dir) / "dashboard"
    print(f"biz_date={day}")
    print(f"out={out_dir}")

    group = build_group_payload(db, biz_date=day, trend_days=args.trend_days)
    shops = list_canonical_shops_from_db()
    shop_payloads = [
        build_shop_payload(db, s, biz_date=day, trend_days=args.trend_days)
        for s in shops
    ]
    paths = write_dashboard_site(out_dir, group, shop_payloads)
    print(f"written {len(paths)} files")
    print(f"  index: {out_dir / 'index.html'}")
    for s in shops:
        slug = s.replace(" ", "_")
        print(f"  shop:  {out_dir / f'shop_{slug}.html'}")

    if args.open:
        url = (out_dir / "index.html").resolve().as_uri()
        webbrowser.open(url)
        print(f"opened {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
