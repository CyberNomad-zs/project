from __future__ import annotations

import logging
import time
from typing import Any, Callable

from app.config import Settings, get_settings
from app.store.db import Database
from app.sync.feishu_schema import (
    row_to_asin_fields,
    task_to_fields,
)
from app.sync.shops import (
    ShopTableRegistry,
    dual_write_enabled,
)

logger = logging.getLogger(__name__)

# Columns that belong to system sync (never "human" fields in local schema)
SYSTEM_COLUMNS = {
    "biz_date",
    "marketplace",
    "shop_name",
    "shop_id",
    "asin",
    "parent_asin",
    "sku",
    "msku",
    "title",
    "title_cn",
    "brand",
    "open_date",
    "product_grade",
    "owner",
    "sale_price",
    "sale_num",
    "order_num",
    "avg_sale_price",
    "sale_price_change_pct",
    "order_num_change_pct",
    "sessions",
    "sessions_change_pct",
    "page_view",
    "conversion_rate",
    "conversion_rate_change_pp",
    "buy_box_percent",
    "ad_impression",
    "ad_clicks",
    "ad_ctr",
    "ad_cost",
    "ad_cost_change_pct",
    "cpc",
    "acos",
    "ad_sales",
    "available",
    "in_transit",
    "available_days",
    "inv_age_365_plus",
    "rating",
    "rating_change",
    "rating_count",
    "low_review_num",
    "review_num",
    "raw_json",
}


def write_rows(
    rows: list[dict[str, Any]],
    *,
    db: Database,
    sync_run_id: int,
    sink: str = "sqlite",
    settings: Settings | None = None,
) -> int:
    """Write mapped ASIN daily rows to configured sinks.

    sink: sqlite | feishu | both
    """
    settings = settings or get_settings()
    db_rows = []
    for r in rows:
        db_rows.append(
            {k: v for k, v in r.items() if k in SYSTEM_COLUMNS or k == "raw_json"}
        )

    n = 0
    if sink in ("sqlite", "both"):
        n = db.upsert_asin_rows(db_rows, sync_run_id)
        logger.info("SQLite upserted %s asin_daily rows", n)

    if sink in ("feishu", "both"):
        if not settings.has_feishu:
            logger.warning("sink 需要飞书但凭证未配置，已跳过飞书写入")
        elif not settings.feishu_bitable_app_token or not settings.feishu_table_asin_daily:
            logger.warning(
                "FEISHU_BITABLE_APP_TOKEN / FEISHU_TABLE_ASIN_DAILY 未配置，跳过"
            )
        else:
            n_feishu = write_asin_to_feishu(
                db_rows, settings=settings, sync_run_id=sync_run_id
            )
            logger.info("Feishu asin_daily upserted %s rows", n_feishu)
            n = max(n, n_feishu)

    return n


_LEGACY_TEXT_DATE_FIELDS = (
    "日期",
    "截止时间",
    "执行日期",
    "复查日期",
    "最近复盘日期",
)


def _ms_to_date_str(ms: float | int) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")


def _fields_for_legacy_mother(fields: dict[str, Any]) -> dict[str, Any]:
    """母表日期列常为文本 type=1，毫秒时间戳会触发 TextFieldConvFail。"""
    out = dict(fields)
    for key in _LEGACY_TEXT_DATE_FIELDS:
        d = out.get(key)
        if isinstance(d, (int, float)) and d > 10_000_000_000:
            out[key] = _ms_to_date_str(d)
    return out


def _upsert_payload(
    settings: Settings,
    table_id: str,
    payload: list[dict[str, Any]],
    *,
    key_field: str = "主键",
) -> int:
    if not payload or not table_id:
        return 0
    from app.clients.feishu import FeishuClient

    app_token = settings.feishu_bitable_app_token
    with FeishuClient(settings) as client:
        stats = client.upsert_by_text_key(
            app_token, table_id, payload, key_field=key_field
        )
    return int(stats.get("total") or 0)


def _create_if_absent_payload(
    settings: Settings,
    table_id: str,
    payload: list[dict[str, Any]],
    *,
    key_field: str = "主键",
) -> dict[str, int]:
    if not payload or not table_id:
        return {"created": 0, "skipped": 0, "total": 0}
    from app.clients.feishu import FeishuClient

    app_token = settings.feishu_bitable_app_token
    with FeishuClient(settings) as client:
        return client.create_records_if_absent(
            app_token, table_id, payload, key_field=key_field
        )


def dual_write_fields(
    settings: Settings,
    *,
    mother_table_id: str,
    kind: str,
    rows: list[dict[str, Any]],
    to_fields: Callable[[dict[str, Any]], dict[str, Any] | None],
    shop_key: str = "shop_name",
    mode: str = "upsert",
    key_field: str = "主键",
) -> dict[str, int]:
    """母表全量写入 + 按规范店名写入子表。

    to_fields: 原始 row → 飞书 fields（可返回 None 跳过）
    mode: upsert | create_if_absent
    返回 {"mother": n, "children": n, "unknown_shop": n}
    """
    result = {"mother": 0, "children": 0, "unknown_shop": 0}
    if not settings.has_feishu or not settings.feishu_bitable_app_token:
        return result
    if not mother_table_id:
        return result

    # 构建 (row, fields) 对
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for r in rows:
        fields = to_fields(r)
        if not fields:
            continue
        fields = {k: v for k, v in fields.items() if v is not None}
        if not fields.get(key_field):
            continue
        pairs.append((r, fields))
    if not pairs:
        return result

    # 母表历史字段「日期」多为文本；子表为 DATE(ms)。母表写入时转回 YYYY-MM-DD 字符串
    mother_payload = [_fields_for_legacy_mother(f) for _, f in pairs]
    if mode == "create_if_absent":
        st = _create_if_absent_payload(
            settings, mother_table_id, mother_payload, key_field=key_field
        )
        result["mother"] = int(st.get("total") or 0)
    else:
        result["mother"] = _upsert_payload(
            settings, mother_table_id, mother_payload, key_field=key_field
        )

    if not dual_write_enabled():
        return result

    registry = ShopTableRegistry.load(settings.shop_tables_path)
    if not registry.data:
        logger.debug("无 shop table registry，跳过子表双写")
        return result

    # 按规范店分组
    from app.sync.shops import canonicalize_shop, load_alias_map

    aliases = load_alias_map()
    shop_groups: dict[str, list[dict[str, Any]]] = {}
    for r, fields in pairs:
        raw = r.get(shop_key) or r.get("店铺") or ""
        can = canonicalize_shop(str(raw) if raw else "", aliases)
        shop_groups.setdefault(can, []).append(fields)

    for can, payload in shop_groups.items():
        if not can:
            result["unknown_shop"] += len(payload)
            logger.warning("无法规范店名的记录 %d 条，仅已写母表", len(payload))
            continue
        child_id = registry.get(can, kind)
        if not child_id:
            result["unknown_shop"] += len(payload)
            logger.warning("店铺 [%s] 无 %s 子表，仅已写母表", can, kind)
            continue
        if mode == "create_if_absent":
            st = _create_if_absent_payload(
                settings, child_id, payload, key_field=key_field
            )
            result["children"] += int(st.get("total") or 0)
        else:
            result["children"] += _upsert_payload(
                settings, child_id, payload, key_field=key_field
            )
        time.sleep(0.15)

    logger.info(
        "dual_write kind=%s mother=%s children=%s unknown=%s",
        kind,
        result["mother"],
        result["children"],
        result["unknown_shop"],
    )
    return result


def write_asin_to_feishu(
    rows: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
    sync_run_id: int | None = None,
) -> int:
    settings = settings or get_settings()
    table_id = settings.feishu_table_asin_daily
    if not settings.feishu_bitable_app_token or not table_id:
        return 0

    def to_fields(r: dict[str, Any]) -> dict[str, Any] | None:
        if not r.get("asin"):
            return None
        return row_to_asin_fields(r, sync_run_id=sync_run_id)

    stats = dual_write_fields(
        settings,
        mother_table_id=table_id,
        kind="asin_daily",
        rows=rows,
        to_fields=to_fields,
        shop_key="shop_name",
        mode="upsert",
    )
    return int(stats.get("mother") or 0)


# 负责人在飞书写入的运营动作列：系统日批 upsert 一律不碰，避免冲掉人工填写。
# 注意：「执行日期」由系统根据「采取动作」自动回填，不在此集合；见 fill_exec_date_from_action。
HUMAN_ACTION_FIELD_NAMES = frozenset(
    {
        "是否属实",
        "原因",
        "判断依据",
        "采取动作",
        "执行人",
        "需审核事项",
        "复查日期",
        "动作前数据",
        "动作后数据",
        "是否有效",
        "下一步动作",
        "闭环状态",
    }
)

ACTION_FIELD = "采取动作"
# 展示名带「系统」提示；兼容旧名「执行日期」/带括号名
EXEC_DATE_FIELD = "执行日期_系统"
EXEC_DATE_FIELD_ALIASES = ("执行日期_系统", "执行日期(系统)", "执行日期", "系统执行日期")
TASK_PK_FIELD = "主键"


def _field_nonempty(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return True


def _day_to_ms(day: str) -> int:
    from datetime import datetime, timezone

    y, m, d = (int(x) for x in day.split("-", 2))
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000)


def _parse_feishu_day(v: Any) -> str | None:
    """把飞书日期字段值解析成 YYYY-MM-DD。"""
    from datetime import datetime, timezone

    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]
        # 可能是毫秒时间戳字符串
        if s.isdigit():
            v = int(s)
        else:
            return None
    if isinstance(v, (int, float)):
        ms = int(v)
        # 秒级时间戳兜底
        if ms < 10_000_000_000:
            ms *= 1000
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return None


def _exec_date_value_for_table(
    *,
    field_type: int | None,
    when_ms: int,
    when_day: str,
) -> Any:
    """DATE 字段写毫秒；文本日期写 YYYY-MM-DD。"""
    if field_type == 5:
        return when_ms
    return when_day


def _resolve_exec_date_field_name(ftypes: dict[str, Any]) -> str | None:
    for name in EXEC_DATE_FIELD_ALIASES:
        if name in ftypes:
            return name
    return None


def fill_exec_date_from_action(
    *,
    settings: Settings | None = None,
    db: Database | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """系统维护执行日期（母表+子表）。

    规则：
    1. 「采取动作」有值时，系统认定执行日期：
       - 本地已锁定 → 用锁定日
       - 否则若飞书已有日期 → 采纳并锁定
       - 否则用当天并锁定
    2. 飞书上的值若与系统认定不一致（含人工改日期），**强制回写**系统值。
    3. 无「采取动作」不处理；不因清空动作而清除已锁定日期。

    说明：当前飞书租户普通版无法用 API 把字段设为 UI 只读；
    靠系统回写 + 字段名「执行日期(系统)」约束人工勿改。
    """
    from datetime import datetime, timezone

    from app.clients.feishu import FeishuClient
    from app.store.db import Database

    settings = settings or get_settings()
    if db is None:
        db = Database(settings.db_path)

    stats = {
        "tables": 0,
        "scanned": 0,
        "filled": 0,
        "corrected": 0,
        "already_ok": 0,
        "locked_new": 0,
        "skipped_no_action": 0,
        "skipped_no_task_id": 0,
        "errors": 0,
    }
    if not settings.has_feishu or not settings.feishu_bitable_app_token:
        logger.warning("飞书未配置，跳过执行日期回填")
        return stats
    mother = settings.feishu_table_tasks
    if not mother:
        return stats

    targets: list[tuple[str, str]] = [("母表", mother)]
    if dual_write_enabled():
        try:
            reg = ShopTableRegistry.load(settings.shop_tables_path)
            for shop, tid in reg.all_table_ids("tasks"):
                targets.append((f"子表-{shop}", tid))
        except Exception:
            logger.exception("加载子表注册表失败，仅处理母表")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    app = settings.feishu_bitable_app_token
    with FeishuClient(settings) as client:
        for label, table_id in targets:
            stats["tables"] += 1
            try:
                ftypes = {
                    f.get("field_name"): f.get("type")
                    for f in client.list_fields(app, table_id)
                }
                if ACTION_FIELD not in ftypes:
                    logger.warning("[%s] 缺少字段 %s，跳过", label, ACTION_FIELD)
                    continue
                exec_name = _resolve_exec_date_field_name(ftypes)
                if not exec_name:
                    logger.warning(
                        "[%s] 缺少字段 %s，跳过",
                        label,
                        "/".join(EXEC_DATE_FIELD_ALIASES),
                    )
                    continue
                exec_type = ftypes.get(exec_name)
                updates: list[dict[str, Any]] = []
                for item in client.iter_records(app, table_id, page_size=100):
                    stats["scanned"] += 1
                    fields = item.get("fields") or {}
                    rid = item.get("record_id")
                    if not rid:
                        continue
                    action = fields.get(ACTION_FIELD)
                    if not _field_nonempty(action):
                        stats["skipped_no_action"] += 1
                        continue

                    task_id = str(
                        fields.get(TASK_PK_FIELD)
                        or fields.get("异常编号")
                        or ""
                    ).strip()
                    if not task_id:
                        stats["skipped_no_task_id"] += 1
                        continue

                    current_day = _parse_feishu_day(fields.get(exec_name))
                    locked = db.get_task_exec_date(task_id)
                    if locked:
                        system_day = locked
                    elif current_day:
                        system_day = current_day
                        if not dry_run:
                            db.set_task_exec_date(
                                task_id, system_day, source="adopt_feishu"
                            )
                            stats["locked_new"] += 1
                    else:
                        system_day = today
                        if not dry_run:
                            db.set_task_exec_date(
                                task_id, system_day, source="first_action"
                            )
                            stats["locked_new"] += 1

                    if current_day == system_day:
                        stats["already_ok"] += 1
                        continue

                    val = _exec_date_value_for_table(
                        field_type=int(exec_type) if exec_type is not None else None,
                        when_ms=_day_to_ms(system_day),
                        when_day=system_day,
                    )
                    updates.append(
                        {"record_id": rid, "fields": {exec_name: val}}
                    )
                    if current_day:
                        stats["corrected"] += 1
                    else:
                        stats["filled"] += 1

                if dry_run:
                    logger.info(
                        "[DRY-RUN][%s] 将写入执行日期 %s 条（新填/纠正合计）",
                        label,
                        len(updates),
                    )
                    continue
                for i in range(0, len(updates), 100):
                    chunk = updates[i : i + 100]
                    if chunk:
                        client.bitable_batch_update(app, table_id, chunk)
                        time.sleep(0.2)
                logger.info(
                    "[%s] 执行日期维护 写入=%s（本轮统计累计 filled/corrected）",
                    label,
                    len(updates),
                )
            except Exception:
                stats["errors"] += 1
                logger.exception("[%s] 执行日期回填失败", label)

    logger.info("fill_exec_date_from_action: %s", stats)
    return stats


def write_tasks_to_feishu(
    tasks: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
) -> int:
    settings = settings or get_settings()
    table_id = settings.feishu_table_tasks
    if not settings.has_feishu or not settings.feishu_bitable_app_token or not table_id:
        logger.warning("飞书任务表未配置，跳过任务同步")
        return 0

    def to_fields(t: dict[str, Any]) -> dict[str, Any] | None:
        fields = task_to_fields(t)
        fields = {k: v for k, v in fields.items() if v is not None}
        # 合并表后：动作列只给人填，系统同步只更新异常/责任字段
        for name in HUMAN_ACTION_FIELD_NAMES:
            fields.pop(name, None)
        if not fields.get("主键"):
            return None
        return fields

    stats = dual_write_fields(
        settings,
        mother_table_id=table_id,
        kind="tasks",
        rows=tasks,
        to_fields=to_fields,
        shop_key="shop_name",
        mode="upsert",
    )
    return int(stats.get("mother") or 0)

