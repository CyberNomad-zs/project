#!/usr/bin/env python3
"""ASIN每日数据：单表 + 按「逻辑店铺」建视图（合并名称变体）。

问题背景：
  赛狐/配置里同一实体店会出现多种写法，例如：
    LEDVIE / Ledvia / Ledvia-UK  → 实际数据多为 Ledvia-UK
    NOTTAC / Nottac / Nottac-UK → 实际数据多为 Nottac-UK
  若按 owners 配置键逐个建视图，会出现多个空视图。

策略：
  1) 以本地 asin_daily 真实出现的 shop_name 为主
  2) 用 config.shop_aliases 把别名合并到规范店名
  3) 每个规范店名只建一个「店铺_{规范名}」视图
  4) 筛选条件 OR 匹配：规范名 + 全部别名（防止历史脏数据）
  5) --cleanup 删除不属于规范列表的「店铺_*」冗余视图

用法：
  python scripts/setup_asin_shop_views.py
  python scripts/setup_asin_shop_views.py --cleanup
  python scripts/setup_asin_shop_views.py --dry-run
  python scripts/setup_asin_shop_views.py --shops 特米-UK,昇新-UK
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.feishu import FeishuClient, FeishuError
from app.config import get_settings
from app.sync.shops import (
    canonicalize_shop,
    list_canonical_shops_from_db,
    list_canonical_shops_from_names,
    load_alias_map,
    shop_match_variants,
)


def _alias_map() -> dict[str, str]:
    return load_alias_map()


def _canonical(name: str, aliases: dict[str, str]) -> str:
    return canonicalize_shop(name, aliases)


def _variants_for(canonical: str, aliases: dict[str, str]) -> list[str]:
    return shop_match_variants(canonical, aliases)


def _view_name(shop: str) -> str:
    return f"店铺_{shop}"


def main() -> int:
    parser = argparse.ArgumentParser(description="ASIN每日数据按逻辑店铺建视图（合并别名）")
    parser.add_argument(
        "--shops",
        default="",
        help="逗号分隔规范店名；默认从本地库实际店铺 + 别名归一化",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印计划，不调飞书写接口",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="删除不在规范列表中的「店铺_*」视图（去掉 LEDVIE/Nottac 等空别名视图）",
    )
    parser.add_argument(
        "--also-tasks",
        action="store_true",
        help="同时在「异常任务」表建同名店铺视图",
    )
    args = parser.parse_args()

    settings = get_settings()
    app = settings.feishu_bitable_app_token
    table_asin = settings.feishu_table_asin_daily
    table_tasks = settings.feishu_table_tasks
    if not settings.has_feishu or not app or not table_asin:
        print(
            "ERROR: 需要 FEISHU_APP_ID/SECRET、FEISHU_BITABLE_APP_TOKEN、"
            "FEISHU_TABLE_ASIN_DAILY"
        )
        return 2

    aliases = _alias_map()

    if args.shops.strip():
        canonicals = list_canonical_shops_from_names(
            [s.strip() for s in args.shops.split(",") if s.strip()]
        )
    else:
        canonicals = list_canonical_shops_from_db()
        if not canonicals:
            print("ERROR: 本地 asin_daily 无店铺。请先 sync，或传 --shops")
            return 2

    print("策略: 母表按逻辑店铺建视图（分表为主见 init_shop_tables.py；视图为辅）")
    print(f"app_token={app}")
    print(f"ASIN表={table_asin}")
    print(f"逻辑店铺({len(canonicals)}):")
    for can in canonicals:
        vars_ = _variants_for(can, aliases)
        print(f"  {_view_name(can)}  ← 匹配 {vars_}")

    if args.dry_run:
        print("[DRY-RUN] 未修改飞书")
        if args.cleanup:
            print("[DRY-RUN] 将删除不在规范列表中的 店铺_* 视图")
        return 0

    try:
        with FeishuClient(settings) as client:
            ok = _ensure_shop_views(
                client, app, table_asin, canonicals, aliases, field_name="店铺"
            )
            if args.cleanup:
                _cleanup_extra_views(client, app, table_asin, canonicals)

            if args.also_tasks:
                if not table_tasks:
                    print("WARN: 未配置 FEISHU_TABLE_TASKS，跳过异常任务视图")
                else:
                    print("--- 异常任务表 ---")
                    _ensure_shop_views(
                        client, app, table_tasks, canonicals, aliases, field_name="店铺"
                    )
                    if args.cleanup:
                        _cleanup_extra_views(client, app, table_tasks, canonicals)

            print()
            print("Base URL:")
            print(f"https://dcnkj1up67d5.feishu.cn/base/{app}?table={table_asin}")
            print("打开多维表左侧视图列表按店切换即可；同店别名已合并。")
            return 0 if ok else 1
    except FeishuError as e:
        print(f"FEISHU ERROR [{e.code}] {e.message}")
        if e.payload:
            print(e.payload)
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


def _ensure_shop_views(
    client: FeishuClient,
    app: str,
    table: str,
    canonicals: list[str],
    aliases: dict[str, str],
    *,
    field_name: str,
) -> bool:
    existing = {v.get("view_name"): v for v in client.list_views(app, table)}
    print("existing views:", list(existing.keys()))
    name_to_id = client.field_id_map(app, table)
    shop_fid = name_to_id.get(field_name)
    if not shop_fid:
        print(f"ERROR: 表中无「{field_name}」字段: {list(name_to_id.keys())}")
        return False
    print(f"field {field_name} -> {shop_fid}")

    all_ok = True
    for can in canonicals:
        vname = _view_name(can)
        variants = _variants_for(can, aliases)

        if vname in existing:
            vid = existing[vname].get("view_id")
            print(f"reuse: {vname} -> {vid}")
        else:
            v = client.create_view(app, table, vname, view_type="grid")
            vid = v.get("view_id")
            print(f"created: {vname} -> {vid}")
            if not vid:
                all_ok = False
                continue
            existing[vname] = {"view_id": vid, "view_name": vname}

        try:
            client.patch_view_filter_or(
                app,
                table,
                existing[vname]["view_id"],
                field_id=shop_fid,
                values=variants,
            )
            print(f"  filter OK (OR): {variants}")
        except FeishuError as e:
            # 回退：仅规范名单条件
            applied = False
            last_err = f"[{e.code}] {e.message}"
            for val in [
                json.dumps([can], ensure_ascii=False),
                f'["{can}"]',
                can,
            ]:
                try:
                    client.patch_view_filter(
                        app,
                        table,
                        existing[vname]["view_id"],
                        field_id=shop_fid,
                        operator="is",
                        value=val,
                    )
                    print(f"  filter OK (fallback is): {val!r}")
                    applied = True
                    break
                except FeishuError as e2:
                    last_err = f"[{e2.code}] {e2.message}"
            if not applied:
                all_ok = False
                print(f"  filter FAIL: {vname} last={last_err}")
                print("  → 请在飞书 UI 手动筛选店铺")

    return all_ok


def _cleanup_extra_views(
    client: FeishuClient,
    app: str,
    table: str,
    canonicals: list[str],
) -> None:
    """删除「店铺_*」且不在规范列表中的视图。"""
    keep = {_view_name(c) for c in canonicals}
    views = client.list_views(app, table)
    deleted = 0
    for v in views:
        name = v.get("view_name") or ""
        vid = v.get("view_id")
        if not name.startswith("店铺_") or not vid:
            continue
        if name in keep:
            continue
        try:
            client.delete_view(app, table, vid)
            print(f"deleted redundant view: {name} ({vid})")
            deleted += 1
        except FeishuError as e:
            print(f"delete FAIL {name}: [{e.code}] {e.message}")
    print(f"cleanup done: deleted={deleted}, keep={sorted(keep)}")


if __name__ == "__main__":
    raise SystemExit(main())
