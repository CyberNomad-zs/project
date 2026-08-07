#!/usr/bin/env python3
"""只读探测：赛狐 OpenAPI 是否能拉到 TikTok 商品 / 利润报表。

用途：
  1) 确认当前 App + IP 白名单能否调 TK 接口
  2) 摸清账号下是否绑定了 TK 店、返回字段长什么样
  3) 为清泉 TK 驾驶舱评估「赛狐能补什么」

不做：发货写操作、WMS 调用、写飞书、打印 secret。

用法（在已加赛狐 IP 白名单的机器上）：
  python probe_tiktok.py --config config/config.g2-3shops.yaml
  python probe_tiktok.py --client-id 368233 --client-secret <secret>
  python probe_tiktok.py --config config/config.g2-3shops.yaml --shop 12345 --shop 67890
  python probe_tiktok.py --config config/config.g2-3shops.yaml --only products
  python probe_tiktok.py --config config/config.g2-3shops.yaml --only report -o logs/tk_probe.json

常见失败：
  code=40005  → 出口 IP 不在白名单（本机直连，勿走代理）
  无数据/空 rows → 账号未绑 TK 店，或 shopId 不是 TK 店，或模块未开通
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.clients.sellfox import SellfoxClient, SellfoxError  # noqa: E402


def load_cfg(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _safe_rows(data) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("rows") or data.get("list") or data.get("records") or []
    return []


def _meta(data) -> dict:
    if not isinstance(data, dict):
        return {"raw_type": type(data).__name__}
    return {
        "pageNo": data.get("pageNo") or data.get("pageNum"),
        "pageSize": data.get("pageSize"),
        "totalPage": data.get("totalPage"),
        "totalSize": data.get("totalSize"),
        "row_count": len(_safe_rows(data)),
        "extra_keys": sorted(
            k
            for k in data.keys()
            if k
            not in {
                "pageNo",
                "pageNum",
                "pageSize",
                "totalPage",
                "totalSize",
                "rows",
                "list",
                "records",
            }
        ),
    }


def _sample_rows(rows: list, n: int = 3) -> list:
    out = []
    for r in rows[:n]:
        if not isinstance(r, dict):
            out.append({"_type": type(r).__name__, "_preview": str(r)[:120]})
            continue
        # 截断长字段，避免日志爆炸 / 误带隐私
        item = {}
        for k, v in r.items():
            if isinstance(v, str) and len(v) > 80:
                item[k] = v[:80] + "…"
            elif isinstance(v, list) and len(v) > 8:
                item[k] = v[:8] + ["…"]
            else:
                item[k] = v
        out.append(item)
    return out


def _field_union(rows: list) -> list:
    keys = set()
    for r in rows:
        if isinstance(r, dict):
            keys.update(r.keys())
    return sorted(keys)


def call_named(label: str, fn, report: dict):
    print(f"\n=== {label} ===")
    entry = {"ok": False, "error": None, "meta": None, "fields": [], "samples": []}
    try:
        data = fn()
        rows = _safe_rows(data)
        entry["ok"] = True
        entry["meta"] = _meta(data)
        entry["fields"] = _field_union(rows)
        entry["samples"] = _sample_rows(rows)
        # 粗分布：状态类字段
        for status_key in ("tkStatus", "status", "matchStatus", "shopType", "statementStatus"):
            vals = [str(r.get(status_key)) for r in rows if isinstance(r, dict) and r.get(status_key) not in (None, "")]
            if vals:
                entry.setdefault("distributions", {})[status_key] = dict(Counter(vals))
        print(json.dumps({k: entry[k] for k in ("ok", "meta", "fields", "distributions") if k in entry}, ensure_ascii=False, indent=2))
        if entry["samples"]:
            print("samples:")
            print(json.dumps(entry["samples"], ensure_ascii=False, indent=2))
        else:
            print("(no rows)")
    except SellfoxError as e:
        entry["error"] = str(e)
        print(f"FAIL SellfoxError: {e}")
        if "40005" in str(e) or "白名单" in str(e):
            print("→ IP 白名单问题：换已加白机器，或把本机出口 IP 报给赛狐加白；session.trust_env=False 已强制直连")
    except Exception as e:
        entry["error"] = repr(e)
        print(f"FAIL {type(e).__name__}: {e}")
    report[label] = entry
    return entry


def resolve_credentials(args) -> tuple[str, str, str]:
    base_url = "https://openapi.sellfox.com"
    client_id = args.client_id
    client_secret = args.client_secret
    if args.config:
        cfg = load_cfg(args.config)
        sf = cfg.get("sellfox") or {}
        base_url = sf.get("base_url") or base_url
        client_id = client_id or sf.get("client_id")
        client_secret = client_secret or sf.get("client_secret")
        # 可选：从配置白名单带 shop（多半是 Temu，仅作 fallback）
        if not args.shops:
            run = cfg.get("run") or {}
            wl = run.get("shop_whitelist") or []
            if wl:
                print(
                    f"注意: 未传 --shop，将使用配置 shop_whitelist={wl} "
                    f"（多为 Temu；TK 探测可能空，建议显式传 TK 的赛狐 shopId）"
                )
                args.shops = [str(s) for s in wl]
    if not client_id or not client_secret:
        print("ERROR: 需要 --config 含 sellfox 密钥，或 --client-id/--client-secret", file=sys.stderr)
        sys.exit(2)
    return str(base_url), str(client_id), str(client_secret)


def main():
    ap = argparse.ArgumentParser(description="探测赛狐 TikTok 商品/利润接口（只读）")
    ap.add_argument("--config", default=None, help="yaml（含 sellfox.client_*）；也可用纯 CLI 密钥")
    ap.add_argument("--client-id", default=None)
    ap.add_argument("--client-secret", default=None)
    ap.add_argument("--base-url", default=None, help="默认 https://openapi.sellfox.com")
    ap.add_argument(
        "--shop",
        action="append",
        dest="shops",
        help="赛狐 shopId（TK 店卡 Shop Code，如 GBLCJGQ23Q），可多次",
    )
    ap.add_argument(
        "--only",
        choices=["all", "products", "report", "packages"],
        default="all",
        help="只跑某一类探测",
    )
    ap.add_argument("--page-size", type=int, default=20)
    ap.add_argument(
        "--start-date",
        default=None,
        help="yyyy-MM-dd；商品自营店与利润报表用；默认=今天-29 天（≤30 天窗）",
    )
    ap.add_argument("--end-date", default=None, help="默认今天")
    ap.add_argument(
        "--currency",
        default="",
        help="利润报表币种；空字符串=原币（文档约定）",
    )
    ap.add_argument(
        "--marketplace",
        default=None,
        help="站点码，逗号分隔，如 UK,US；可选",
    )
    ap.add_argument("-o", "--out", help="完整报告 JSON（不含密钥）")
    args = ap.parse_args()

    if not args.config and not (args.client_id and args.client_secret):
        # 默认尝试项目常用配置
        default_cfg = ROOT / "config" / "config.g2-3shops.yaml"
        if default_cfg.exists():
            args.config = str(default_cfg)
        else:
            print("ERROR: 请提供 --config 或 --client-id/--client-secret", file=sys.stderr)
            sys.exit(2)

    base_url, client_id, client_secret = resolve_credentials(args)
    if args.base_url:
        base_url = args.base_url

    end_d = args.end_date or date.today().isoformat()
    start_d = args.start_date or (date.today() - timedelta(days=29)).isoformat()
    shop_ids = [str(s) for s in (args.shops or [])]
    marketplace = None
    if args.marketplace:
        marketplace = [x.strip() for x in args.marketplace.split(",") if x.strip()]

    client = SellfoxClient(base_url=base_url, client_id=client_id, client_secret=client_secret)

    print("=== 赛狐 TikTok 探测（只读）===")
    print(f"base_url={base_url}")
    print(f"client_id={client_id}")
    print(f"shops={shop_ids or '(未指定，部分接口拉账号可见范围)'}")
    print(f"date_window={start_d}~{end_d} page_size={args.page_size} only={args.only}")

    report = {
        "base_url": base_url,
        "client_id": client_id,
        "shops": shop_ids,
        "date_window": f"{start_d}~{end_d}",
        "calls": {},
    }

    # 1) token 探活
    try:
        tok = client._get_token()
        print(f"\ntoken: ok (len={len(tok) if tok else 0})")
        report["token"] = "ok"
    except Exception as e:
        print(f"\ntoken: FAIL {e}", file=sys.stderr)
        report["token"] = str(e)
        if args.out:
            Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.exit(1)

    do_products = args.only in ("all", "products")
    do_report = args.only in ("all", "report")
    do_packages = args.only in ("all", "packages")

    if do_products:
        # 全托父体（文档 body 较简，无强制日期）
        call_named(
            "tiktok_fully_managed_parent",
            lambda: client.tiktok_fully_managed_parent_page(
                page_no=1, page_size=args.page_size, shop_ids=shop_ids or None
            ),
            report["calls"],
        )
        # 自营全球父体
        call_named(
            "tiktok_global_parent",
            lambda: client.tiktok_global_parent_page(
                page_no=1, page_size=args.page_size, shop_ids=shop_ids or None
            ),
            report["calls"],
        )
        # 自营店铺父体（强制日期窗）
        call_named(
            "tiktok_shop_parent",
            lambda: client.tiktok_shop_parent_page(
                page_no=1,
                page_size=args.page_size,
                shop_ids=shop_ids or None,
                date_type="createDate",
                start_date=start_d,
                end_date=end_d,
            ),
            report["calls"],
        )
        # 若任一类有 parentId，抽 1 条子体
        parent_id = None
        parent_src = None
        for label in (
            "tiktok_shop_parent",
            "tiktok_global_parent",
            "tiktok_fully_managed_parent",
        ):
            ent = report["calls"].get(label) or {}
            for s in ent.get("samples") or []:
                if isinstance(s, dict) and s.get("parentId"):
                    parent_id = s["parentId"]
                    parent_src = label
                    break
            if parent_id:
                break
        if parent_id:
            child_fn = {
                "tiktok_shop_parent": client.tiktok_shop_child_info,
                "tiktok_global_parent": client.tiktok_global_child_info,
                "tiktok_fully_managed_parent": client.tiktok_fully_managed_child_info,
            }[parent_src]
            call_named(
                f"tiktok_child_from_{parent_src}",
                lambda: child_fn(parent_id),
                report["calls"],
            )
        else:
            print("\n(skip child: 无 parentId 样本)")

    if do_report:
        # 利润报表 shopIds：Shop Code 即 shopId（可字母数字）；无 shop 时传 None 看账号默认范围
        report_shop_ids = shop_ids or None
        call_named(
            "tiktok_report_shop",
            lambda: client.tiktok_report_shop(
                start_date=start_d,
                end_date=end_d,
                shop_ids=report_shop_ids,
                currency=args.currency,
                marketplace_codes=marketplace,
                page_num=1,
                page_size=args.page_size,
            ),
            report["calls"],
        )
        call_named(
            "tiktok_report_sku",
            lambda: client.tiktok_report_sku(
                start_date=start_d,
                end_date=end_d,
                shop_ids=report_shop_ids,
                currency=args.currency,
                marketplace_codes=marketplace,
                page_num=1,
                page_size=min(args.page_size, 20),
            ),
            report["calls"],
        )
        call_named(
            "tiktok_report_statement_detail",
            lambda: client.tiktok_report_statement_detail(
                start_date=start_d,
                end_date=end_d,
                shop_ids=report_shop_ids,
                currency=args.currency,
                page_no=1,
                page_size=min(args.page_size, 20),
            ),
            report["calls"],
        )

    if do_packages:
        # 发货包裹：与平台弱绑定，能侧面证明 TK 单是否进了赛狐
        ds = f"{start_d} 00:00:00"
        de = f"{end_d} 23:59:59"
        for st in ("to_process", "has_shipped", "apply_track_no"):
            call_named(
                f"package_{st}",
                lambda status=st: client.get_package_page(
                    status=status,
                    date_start=ds,
                    date_end=de,
                    page_no=1,
                    page_size=min(args.page_size, 50),
                    shop_ids=shop_ids or None,
                ),
                report["calls"],
            )

    # 判定摘要
    print("\n=== 判定摘要 ===")
    ok_with_rows = []
    ok_empty = []
    failed = []
    for k, v in (report.get("calls") or {}).items():
        if not v.get("ok"):
            failed.append(k)
        elif (v.get("meta") or {}).get("row_count", 0) > 0 or v.get("samples"):
            ok_with_rows.append(k)
        else:
            ok_empty.append(k)

    print(f"有数据: {ok_with_rows or '无'}")
    print(f"通了但空: {ok_empty or '无'}")
    print(f"失败: {failed or '无'}")

    if failed and all("40005" in str((report['calls'].get(k) or {}).get('error') or '') for k in failed):
        print("总判: IP 白名单阻断，换机器后再探。")
    elif ok_with_rows:
        print(
            "总判: 赛狐侧 **已能读到 TK 相关数据**。"
            "下一步：固定 TK shopId 映射到清泉 public.shop，再定增量同步范围。"
        )
    elif ok_empty and not failed:
        print(
            "总判: 接口通但无行。"
            "优先检查：1) 赛狐是否绑定 TK 店 2) --shop 是否为 TK 的赛狐 shopId "
            "3) 日期窗/店类型（全托 vs 自营）是否匹配 4) App 是否开通多平台/财务 TK 模块。"
        )
    else:
        print("总判: 部分失败 — 看各 call 的 error；权限不足与参数错误需对照文档。")

    print(
        "\n对清泉驾驶舱的提示: "
        "商品/利润/结算可评估赛狐补数；广告、内容、健康分、店 KPI 细指标仍走 TK 采集。"
        "详见清泉 docs/TK-赛狐数据源对照.md"
    )

    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写入 {outp}")

    print("\n完成。")
    # 有失败且无任何数据时非 0，便于 CI/定时
    if failed and not ok_with_rows:
        sys.exit(1)


if __name__ == "__main__":
    main()
