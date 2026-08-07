#!/usr/bin/env python3
"""只读探测：赛狐 OpenAPI 拉 Temu 跨境父体列表，统计 selectStatus 分布。

用途：判断能否用赛狐做「下架监测」数据源（不发货、不写状态、不告警）。

用法：
  python probe_temu_products.py --config config/config.g2-3shops.yaml
  python probe_temu_products.py --config config/config.g2-3shops.yaml --max-pages 5
  python probe_temu_products.py --config config/config.g2-3shops.yaml --shop 396706

安全：只打印计数与状态分布，不打印 client_secret；样本商品名截断。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

# 允许直接 python probe_temu_products.py
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.clients.sellfox import SellfoxClient, SellfoxError  # noqa: E402

# 与项目说明一致：金猫三店
DEFAULT_SHOP_NAMES = {
    "396706": "Agnis",
    "398202": "HomeCove",
    "398203": "Twilight Cove",
}


def load_cfg(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_ymd(s: str):
    from datetime import datetime

    return datetime.strptime(s, "%Y-%m-%d").date()


def _iter_windows(start_date: str, end_date: str, max_span_days: int = 30):
    """赛狐约束：起止间隔不超过 30 天。倒序从 end 往前滑窗。"""
    from datetime import timedelta

    end = _parse_ymd(end_date)
    start = _parse_ymd(start_date)
    if start > end:
        start, end = end, start
    cur_end = end
    while cur_end >= start:
        cur_start = max(start, cur_end - timedelta(days=max_span_days - 1))
        yield cur_start.isoformat(), cur_end.isoformat()
        cur_end = cur_start - timedelta(days=1)


def fetch_window_pages(
    client: SellfoxClient,
    shop_ids: list[str],
    page_size: int,
    max_pages: int,
    date_type: str,
    start_date: str,
    end_date: str,
):
    """单窗口内分页。"""
    all_rows = []
    page_no = 1
    total_size = None
    total_page = None
    while page_no <= max_pages:
        data = client.temu_cross_parent_page(
            page_no=page_no,
            page_size=page_size,
            shop_ids=shop_ids,
            date_type=date_type,
            start_date=start_date,
            end_date=end_date,
        )
        if data is None:
            break
        if isinstance(data, dict):
            rows = data.get("rows") or data.get("list") or []
            if total_size is None:
                total_size = data.get("totalSize")
                total_page = data.get("totalPage")
        elif isinstance(data, list):
            rows = data
        else:
            rows = []
        all_rows.extend(rows)
        if not rows:
            break
        if total_size is not None and len(all_rows) >= int(total_size):
            break
        if total_page is not None and page_no >= int(total_page):
            break
        if len(rows) < page_size:
            break
        page_no += 1
    return all_rows, {
        "window": f"{start_date}~{end_date}",
        "pages_fetched": min(page_no, max_pages),
        "totalSize": total_size,
        "totalPage": total_page,
        "row_count": len(all_rows),
    }


def fetch_all_parents(
    client: SellfoxClient,
    shop_ids: list[str],
    page_size: int,
    max_pages: int,
    date_type: str = "createDate",
    start_date: str = "2020-01-01",
    end_date: str | None = None,
):
    """按 ≤30 天窗口滑窗 + 分页拉父体；按 parentId/skcId 去重。"""
    from datetime import date as _date

    end = end_date or _date.today().isoformat()
    all_rows = []
    seen = set()
    windows_meta = []
    for w_start, w_end in _iter_windows(start_date, end, 30):
        rows, meta = fetch_window_pages(
            client, shop_ids, page_size, max_pages, date_type, w_start, w_end
        )
        windows_meta.append(meta)
        for r in rows:
            if not isinstance(r, dict):
                continue
            key = str(r.get("parentId") or r.get("skcId") or id(r))
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(r)
        print(f"  window {w_start}~{w_end}: +{meta['row_count']} (unique total {len(all_rows)})")
    return all_rows, {
        "windows": len(windows_meta),
        "windows_detail": windows_meta[:20],  # 防过长
        "row_count": len(all_rows),
        "unique_keys": len(seen),
        "date_type": date_type,
        "range": f"{start_date}~{end}",
    }


def summarize(rows: list[dict], shop_names: dict[str, str]) -> dict:
    by_shop_status = defaultdict(Counter)  # shopId -> Counter(selectStatus)
    by_status = Counter()
    samples = defaultdict(list)  # selectStatus -> few samples
    missing_status = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("shopId") or r.get("shop_id") or "?")
        st = r.get("selectStatus")
        if st is None or st == "":
            st = r.get("status")  # 兜底
            if st is None or st == "":
                missing_status += 1
                st = "<empty>"
        st = str(st)
        by_shop_status[sid][st] += 1
        by_status[st] += 1
        if len(samples[st]) < 3:
            samples[st].append(
                {
                    "shopId": sid,
                    "shopName": shop_names.get(sid) or r.get("shopName") or "",
                    "parentId": r.get("parentId"),
                    "skcId": r.get("skcId"),
                    "productName": str(r.get("productName") or "")[:40],
                    "selectStatus": st,
                    "trusteeship": r.get("trusteeship"),
                    "keys": sorted(r.keys())[:20],
                }
            )
    return {
        "by_status": dict(by_status),
        "by_shop_status": {k: dict(v) for k, v in by_shop_status.items()},
        "missing_status": missing_status,
        "samples": {k: v for k, v in samples.items()},
        "field_union": sorted({k for r in rows if isinstance(r, dict) for k in r.keys()}),
    }


def main():
    ap = argparse.ArgumentParser(description="探测赛狐 Temu 跨境父体 selectStatus")
    ap.add_argument(
        "--config",
        default=str(ROOT / "config" / "config.g2-3shops.yaml"),
        help="含 sellfox client 与 shop_whitelist 的 yaml",
    )
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--max-pages", type=int, default=50, help="防死循环上限")
    ap.add_argument(
        "--shop",
        action="append",
        dest="shops",
        help="只查指定 shopId，可多次；默认用配置白名单",
    )
    ap.add_argument(
        "--try-local",
        action="store_true",
        help="额外试一次本土店父体接口（半托管通常无数据）",
    )
    ap.add_argument(
        "--date-type",
        default="createDate",
        help="日期类型，文档示例 createDate；也可试 updateDate",
    )
    ap.add_argument(
        "--start-date",
        default=None,
        help="yyyy-MM-dd；默认=今天往前 lookback-days（接口单窗最多30天，脚本会滑窗）",
    )
    ap.add_argument("--end-date", default=None, help="默认今天")
    ap.add_argument(
        "--lookback-days",
        type=int,
        default=180,
        help="未指定 start-date 时，从今天往前推多少天（滑窗覆盖）",
    )
    ap.add_argument("-o", "--out", help="把完整汇总 JSON 写到文件（不含密钥）")
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    sf = cfg.get("sellfox") or {}
    run = cfg.get("run") or {}
    shop_ids = args.shops or [str(s) for s in (run.get("shop_whitelist") or [])]
    if not shop_ids:
        print("ERROR: 无 shopId（配置 run.shop_whitelist 或 --shop）", file=sys.stderr)
        sys.exit(2)
    if not sf.get("client_id") or not sf.get("client_secret"):
        print("ERROR: 配置缺少 sellfox.client_id / client_secret", file=sys.stderr)
        sys.exit(2)

    client = SellfoxClient(
        base_url=sf.get("base_url") or "https://openapi.sellfox.com",
        client_id=str(sf["client_id"]),
        client_secret=str(sf["client_secret"]),
    )

    shop_names = dict(DEFAULT_SHOP_NAMES)
    print("=== 赛狐 Temu 跨境父体探测（只读）===")
    print(f"shops: {[(s, shop_names.get(s, '?')) for s in shop_ids]}")
    from datetime import date, timedelta

    end_date = args.end_date or date.today().isoformat()
    if args.start_date:
        start_date = args.start_date
    else:
        start_date = (date.today() - timedelta(days=max(1, args.lookback_days))).isoformat()

    print(
        f"pageSize={args.page_size} maxPages/window={args.max_pages} "
        f"dateType={args.date_type} {start_date}~{end_date} (30d windows)"
    )

    report = {"shops": shop_ids, "cross_border": None, "local": None, "error": None}

    try:
        rows, meta = fetch_all_parents(
            client,
            shop_ids,
            args.page_size,
            args.max_pages,
            date_type=args.date_type,
            start_date=start_date,
            end_date=end_date,
        )
        summary = summarize(rows, shop_names)
        report["cross_border"] = {"meta": meta, **summary}
        print("\n--- 跨境店 getParentPageList ---")
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        print("selectStatus 全局分布:")
        print(json.dumps(summary["by_status"], ensure_ascii=False, indent=2))
        print("按店分布:")
        for sid, ctr in summary["by_shop_status"].items():
            print(f"  {sid} ({shop_names.get(sid, '?')}): {dict(ctr)}")
        print(f"缺 selectStatus 条数: {summary['missing_status']}")
        print("字段并集:", ", ".join(summary["field_union"][:40]))
        print("各状态样本（最多 3 条/状态）:")
        print(json.dumps(summary["samples"], ensure_ascii=False, indent=2))

        # 粗判：是否像能做下架 diff
        statuses = set(summary["by_status"].keys()) - {"<empty>"}
        if not rows:
            print("\n判定: 无数据 — 可能未授权 Temu 到赛狐、无多平台商品权限、或 shopId 不对")
        elif summary["missing_status"] == len(rows):
            print("\n判定: 有列表但无 selectStatus — 不能直接做下架 diff，需看其它字段或换接口")
        elif len(statuses) >= 2:
            print(
                f"\n判定: 有 ≥2 种 selectStatus ({sorted(statuses)}) — "
                "可继续标定「在售/下架」枚举后做集合 diff"
            )
        else:
            print(
                f"\n判定: 仅见状态 {sorted(statuses)} — "
                "需对照后台已下架商品是否出现在列表/状态值是否变化"
            )

    except SellfoxError as e:
        report["error"] = str(e)
        print(f"\n跨境接口失败: {e}", file=sys.stderr)
        print(
            "常见原因: IP 白名单(40005)、token/权限不足、多平台 Temu 模块未开通",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        report["error"] = repr(e)
        print(f"\n异常: {e}", file=sys.stderr)
        sys.exit(1)

    if args.try_local:
        print("\n--- 额外：本土店父体（半托管通常空）---")
        try:
            data = client.temu_local_parent_page(
                page_no=1, page_size=20, shop_ids=shop_ids
            )
            report["local"] = data
            print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        except SellfoxError as e:
            print(f"本土接口: {e}")

    if args.out:
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n已写入 {args.out}")

    print("\n完成。")


if __name__ == "__main__":
    main()
