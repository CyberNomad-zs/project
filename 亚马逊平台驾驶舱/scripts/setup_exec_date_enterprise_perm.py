"""企业版：把「执行日期_系统」设为字段只读（运营可改动作列，不可改执行日期）。

背景
----
- 普通版 / 非商业版：飞书返回 ``Only Available For Business and Enterprise Editions``，
  **无法**用 API 做字段级只读。请继续依赖系统回写（``fill_exec_date_from_action``）。
- 商业版 / 企业版：开启多维表「高级权限」后，可用自定义角色的 ``field_perm``
  把指定字段设为只读。

field_perm 取值（飞书 bitable 高级权限）
----------------------------------------
- ``1`` = 可读写
- ``2`` = 只读

本脚本会：
1. 确保 base 已开高级权限（``is_advanced=true``）
2. 确保字段名为 ``执行日期_系统``（兼容旧名自动重命名）
3. 对所有「异常任务」母表/子表生成 field_perm：执行日期只读，其余默认可读写
4. 创建或更新角色 **「运营协作者(系统)」**（可改动作字段；执行日期只读）
5. 可选：创建 **「只读访客(系统)」**（整表只读）
6. ``--check`` 仅探测当前租户是否支持字段权限，不改配置

用法
----
::

    # 先探测（当前普通版会明确提示不支持）
    python scripts/setup_exec_date_enterprise_perm.py --check

    # 企业版正式配置
    python scripts/setup_exec_date_enterprise_perm.py

    # 只看将要提交的 JSON
    python scripts/setup_exec_date_enterprise_perm.py --dry-run

    # 同时建只读访客角色
    python scripts/setup_exec_date_enterprise_perm.py --with-viewer

配置角色成员（API 加成员常需额外权限，建议 UI 操作一次）
----------------------------------------------------------
1. 打开多维表格 → 右上角「…」→「高级权限」/「自定义角色」
2. 将 梦晴 / 潘启豪 / 马文静 / 助理 加入 **运营协作者(系统)**
3. 将老板等加入 **只读访客(系统)**（若创建了）
4. 确认「普通用户」不要再给异常任务表「可编辑全部字段」的宽松权限，
   否则会绕过本角色的字段限制（以飞书实际权限叠加规则为准）

相关
----
- 系统回写兜底：``python -m app.main fill-exec-date``
- 字段改名：``python scripts/lock_exec_date_field.py``
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.clients.feishu import FeishuClient, FeishuError
from app.config import get_settings
from app.sync.shops import ShopTableRegistry, dual_write_enabled
from app.sync.writer import (
    EXEC_DATE_FIELD,
    EXEC_DATE_FIELD_ALIASES,
    HUMAN_ACTION_FIELD_NAMES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("setup_exec_date_enterprise_perm")

# 飞书 field_perm
PERM_EDIT = 1  # 可读写
PERM_READONLY = 2  # 只读

# table_perm：1 只读表 / 2 可编辑记录（与开放平台高级权限一致）
TABLE_READ = 1
TABLE_EDIT = 2

ROLE_OPERATOR = "运营协作者(系统)"
ROLE_VIEWER = "只读访客(系统)"

# 系统维护、一般不希望运营改的列（只读）；动作列保持可写
SYSTEM_READONLY_EXTRA = frozenset(
    {
        EXEC_DATE_FIELD,
        *EXEC_DATE_FIELD_ALIASES,
        "主键",
        "异常编号",
        "日期",
        "店铺",
        "ASIN",
        "产品",
        "中文名称",
        "异常类型",
        "等级",
        "当前值",
        "对比值",
        "变化幅度",
        "当前值含义",
        "对比值含义",
        "变化幅度含义",
        "指标摘要",
        "说明",
        "截止时间",
        "连续异常次数",
        # 负责人和需要老板决策允许运营改：不放这里
    }
)


def ensure_advanced(client: FeishuClient, app: str, *, dry_run: bool) -> dict[str, Any]:
    meta = client._api("GET", f"/bitable/v1/apps/{app}")
    app_info = (meta.get("data") or {}).get("app") or {}
    info = {
        "is_advanced": bool(app_info.get("is_advanced")),
        "advance_version": app_info.get("advance_version"),
        "name": app_info.get("name"),
    }
    logger.info(
        "base=%s is_advanced=%s advance_version=%s",
        info.get("name"),
        info["is_advanced"],
        info["advance_version"],
    )
    if info["is_advanced"]:
        return info
    if dry_run:
        logger.info("[DRY-RUN] 将开启高级权限 is_advanced=true")
        return info
    client._api("PUT", f"/bitable/v1/apps/{app}", json_body={"is_advanced": True})
    info["is_advanced"] = True
    logger.info("已开启高级权限")
    return info


def list_task_tables(client: FeishuClient, settings) -> list[tuple[str, str]]:
    """返回 [(label, table_id), ...] 异常任务母表+子表。"""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(label: str, tid: str | None) -> None:
        if not tid or tid in seen:
            return
        seen.add(tid)
        out.append((label, tid))

    add("母表-异常任务", settings.feishu_table_tasks)
    if dual_write_enabled():
        try:
            reg = ShopTableRegistry.load(settings.shop_tables_path)
            for shop, tid in reg.all_table_ids("tasks"):
                add(f"子表-{shop}", tid)
        except Exception:
            logger.exception("加载 shop_tables 注册失败，将按表名扫描")

    for t in client.list_tables(settings.feishu_bitable_app_token):
        name = str(t.get("name") or "")
        tid = t.get("table_id")
        if name.startswith("异常任务"):
            add(name, tid)
    return out


def ensure_exec_date_field_name(
    client: FeishuClient,
    app: str,
    label: str,
    table_id: str,
    *,
    dry_run: bool,
) -> str | None:
    """确保存在 EXEC_DATE_FIELD；若仅有旧名则重命名。返回实际字段名。"""
    fields = client.list_fields(app, table_id)
    by_name = {f.get("field_name"): f for f in fields if f.get("field_name")}
    for alias in EXEC_DATE_FIELD_ALIASES:
        if alias in by_name and alias == EXEC_DATE_FIELD:
            return EXEC_DATE_FIELD
    if EXEC_DATE_FIELD in by_name:
        return EXEC_DATE_FIELD
    # 旧名 → 新名
    for old in ("执行日期", "执行日期(系统)", "系统执行日期"):
        if old not in by_name:
            continue
        field = by_name[old]
        fid = field.get("field_id")
        ftype = field.get("type")
        prop = field.get("property")
        if not fid:
            continue
        if dry_run:
            logger.info("[DRY-RUN][%s] 重命名 %s → %s", label, old, EXEC_DATE_FIELD)
            return EXEC_DATE_FIELD
        client.update_field(
            app,
            table_id,
            str(fid),
            field_name=EXEC_DATE_FIELD,
            field_type=int(ftype) if ftype is not None else 5,
            property_=prop if isinstance(prop, dict) else None,
        )
        logger.info("[%s] 已重命名 %s → %s", label, old, EXEC_DATE_FIELD)
        return EXEC_DATE_FIELD
    logger.warning("[%s] 未找到执行日期类字段", label)
    return None


def build_field_perm(
    field_names: list[str],
    *,
    exec_date_name: str,
    operator_mode: bool,
) -> dict[str, int]:
    """
    operator_mode=True: 动作列可写，系统列/执行日期只读，其余默认可写。
    operator_mode=False: 全部只读（访客）。
    """
    perm: dict[str, int] = {}
    for name in field_names:
        if not operator_mode:
            perm[name] = PERM_READONLY
            continue
        if name == exec_date_name or name in SYSTEM_READONLY_EXTRA:
            # 人工动作列即使出现在 extra 也不应只读
            if name in HUMAN_ACTION_FIELD_NAMES:
                perm[name] = PERM_EDIT
            else:
                perm[name] = PERM_READONLY
        elif name in HUMAN_ACTION_FIELD_NAMES or name in {
            "负责人",
            "审核人",
            "需要老板决策",
            "状态",
            "闭环状态",
        }:
            perm[name] = PERM_EDIT
        else:
            # 未分类字段默认只读，避免运营改系统指标
            perm[name] = PERM_READONLY
    # 强制执行日期只读
    if exec_date_name:
        perm[exec_date_name] = PERM_READONLY
    # 强制动作列可写（运营）
    if operator_mode:
        for name in HUMAN_ACTION_FIELD_NAMES:
            if name in field_names:
                perm[name] = PERM_EDIT
        if "需要老板决策" in field_names:
            perm["需要老板决策"] = PERM_EDIT
    return perm


def build_table_role(
    table_id: str,
    field_perm: dict[str, int],
    *,
    table_perm: int,
    allow_add: bool,
    allow_delete: bool,
) -> dict[str, Any]:
    return {
        "table_id": table_id,
        "table_perm": table_perm,
        "allow_add_record": allow_add,
        "allow_delete_record": allow_delete,
        "field_perm": field_perm,
    }


def list_roles(client: FeishuClient, app: str) -> list[dict[str, Any]]:
    data = client._api("GET", f"/bitable/v1/apps/{app}/roles")
    return list((data.get("data") or {}).get("items") or [])


def find_role(roles: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for r in roles:
        if r.get("role_name") == name:
            return r
    return None


def upsert_role(
    client: FeishuClient,
    app: str,
    *,
    role_name: str,
    table_roles: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    body = {"role_name": role_name, "table_roles": table_roles}
    roles = list_roles(client, app)
    existing = find_role(roles, role_name)
    if dry_run:
        logger.info(
            "[DRY-RUN] %s role=%s tables=%s sample_field_perm=%s",
            "更新" if existing else "创建",
            role_name,
            len(table_roles),
            {
                k: v
                for tr in table_roles[:1]
                for k, v in list((tr.get("field_perm") or {}).items())
                if "执行" in k or k in ("采取动作", "原因")
            },
        )
        logger.debug("body=%s", json.dumps(body, ensure_ascii=False)[:2000])
        return {"dry_run": True, "role_name": role_name, "exists": bool(existing)}

    if existing and existing.get("role_id"):
        rid = existing["role_id"]
        # 更新：PUT /roles/:role_id （部分租户为 PUT 全量）
        try:
            data = client._api(
                "PUT",
                f"/bitable/v1/apps/{app}/roles/{rid}",
                json_body=body,
            )
            logger.info("已更新角色 %s (%s)", role_name, rid)
            return (data.get("data") or {}).get("role") or {"role_id": rid, **body}
        except FeishuError as e:
            logger.warning("PUT 更新角色失败，尝试删建: %s", e)
            try:
                client._api("DELETE", f"/bitable/v1/apps/{app}/roles/{rid}")
            except FeishuError as e2:
                logger.warning("删除旧角色失败: %s", e2)

    data = client._api("POST", f"/bitable/v1/apps/{app}/roles", json_body=body)
    role = (data.get("data") or {}).get("role") or {}
    logger.info("已创建角色 %s (%s)", role_name, role.get("role_id"))
    return role


def probe_field_perm_support(
    client: FeishuClient,
    app: str,
    table_id: str,
    exec_date_name: str,
) -> tuple[bool, str]:
    """尝试创建一个临时角色带 field_perm，成功则删掉并返回 True。"""
    body = {
        "role_name": "__perm_probe_exec_date__",
        "table_roles": [
            {
                "table_id": table_id,
                "table_perm": TABLE_EDIT,
                "allow_add_record": False,
                "allow_delete_record": False,
                "field_perm": {exec_date_name: PERM_READONLY},
            }
        ],
    }
    try:
        data = client._api("POST", f"/bitable/v1/apps/{app}/roles", json_body=body)
        role = (data.get("data") or {}).get("role") or {}
        rid = role.get("role_id")
        # 确认返回里是否带回 field_perm
        tr = (role.get("table_roles") or [{}])[0]
        fp = tr.get("field_perm") or {}
        logger.info("probe ok role_id=%s field_perm=%s", rid, fp)
        if rid:
            try:
                client._api("DELETE", f"/bitable/v1/apps/{app}/roles/{rid}")
            except FeishuError:
                logger.warning("probe 角色删除失败，请在 UI 手动删 __perm_probe_exec_date__")
        if not fp:
            return (
                False,
                "角色已创建但未返回 field_perm（租户可能未真正启用字段权限，或需商业版）",
            )
        return True, "支持 field_perm（商业版/企业版）"
    except FeishuError as e:
        msg = str(e)
        if "1254304" in msg or "Business and Enterprise" in msg or "商业" in msg:
            return False, f"当前租户不支持字段级权限（需商业版/企业版）: {e}"
        return False, f"探测失败: {e}"
    except Exception as e:
        return False, f"探测异常: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="企业版：配置异常任务表「执行日期_系统」字段只读"
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不写飞书")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅探测是否支持 field_perm，不创建业务角色",
    )
    parser.add_argument(
        "--with-viewer",
        action="store_true",
        help="同时创建/更新只读访客角色",
    )
    parser.add_argument(
        "--operator-role-name",
        default=ROLE_OPERATOR,
        help=f"运营角色名（默认 {ROLE_OPERATOR}）",
    )
    parser.add_argument(
        "--viewer-role-name",
        default=ROLE_VIEWER,
        help=f"访客角色名（默认 {ROLE_VIEWER}）",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="打印将提交的 role body JSON",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_feishu or not settings.feishu_bitable_app_token:
        logger.error("飞书未配置（FEISHU_APP_ID/SECRET/BITABLE_APP_TOKEN）")
        return 2
    app = settings.feishu_bitable_app_token

    with FeishuClient(settings) as client:
        ensure_advanced(client, app, dry_run=args.dry_run)
        tables = list_task_tables(client, settings)
        if not tables:
            logger.error("未找到异常任务表")
            return 2
        logger.info("异常任务表 %s 张: %s", len(tables), [x[0] for x in tables])

        # 字段名对齐 + 收集 perm
        operator_table_roles: list[dict[str, Any]] = []
        viewer_table_roles: list[dict[str, Any]] = []
        exec_name_by_table: dict[str, str] = {}

        for label, tid in tables:
            exec_name = ensure_exec_date_field_name(
                client, app, label, tid, dry_run=args.dry_run
            )
            if not exec_name:
                logger.warning("[%s] 跳过（无执行日期字段）", label)
                continue
            exec_name_by_table[tid] = exec_name
            fields = client.list_fields(app, tid)
            names = [str(f.get("field_name")) for f in fields if f.get("field_name")]
            # dry-run 重命名后 list 可能仍是旧名
            if exec_name not in names:
                for a in EXEC_DATE_FIELD_ALIASES:
                    if a in names:
                        exec_name = a
                        break
            op_perm = build_field_perm(
                names, exec_date_name=exec_name, operator_mode=True
            )
            vi_perm = build_field_perm(
                names, exec_date_name=exec_name, operator_mode=False
            )
            operator_table_roles.append(
                build_table_role(
                    tid,
                    op_perm,
                    table_perm=TABLE_EDIT,
                    allow_add=False,
                    allow_delete=False,
                )
            )
            viewer_table_roles.append(
                build_table_role(
                    tid,
                    vi_perm,
                    table_perm=TABLE_READ,
                    allow_add=False,
                    allow_delete=False,
                )
            )
            logger.info(
                "[%s] fields=%s exec=%s→%s 动作可写=%s",
                label,
                len(names),
                exec_name,
                op_perm.get(exec_name),
                {k: op_perm[k] for k in ("采取动作", "原因", "是否属实") if k in op_perm},
            )

        if not operator_table_roles:
            logger.error("没有可配置的表")
            return 2

        # 探测
        first_tid = operator_table_roles[0]["table_id"]
        first_exec = exec_name_by_table.get(first_tid) or EXEC_DATE_FIELD
        if not args.dry_run:
            ok, reason = probe_field_perm_support(client, app, first_tid, first_exec)
        else:
            ok, reason = (
                False,
                "dry-run 未实际探测；去掉 --dry-run 且在企业版上会真实探测",
            )
            # dry-run 下用 check 语义：仍组装 JSON
        logger.info("field_perm 支持? %s — %s", ok, reason)

        if args.check:
            print(
                json.dumps(
                    {
                        "supported": ok,
                        "reason": reason,
                        "tables": len(operator_table_roles),
                        "exec_date_field": EXEC_DATE_FIELD,
                        "hint": (
                            "支持则运行: python scripts/setup_exec_date_enterprise_perm.py"
                            if ok
                            else "请升级飞书商业版/企业版，或继续依赖 fill-exec-date 系统回写"
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if ok else 3

        if not ok and not args.dry_run:
            logger.error(
                "当前租户无法配置字段只读。已保留系统回写兜底："
                " python -m app.main fill-exec-date"
            )
            print(
                json.dumps(
                    {"ok": False, "reason": reason, "fallback": "fill-exec-date"},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 3

        if args.print_json or args.dry_run:
            preview = {
                "role_name": args.operator_role_name,
                "table_roles_count": len(operator_table_roles),
                "table_roles": operator_table_roles,
            }
            print(json.dumps(preview, ensure_ascii=False, indent=2))

        op_result = upsert_role(
            client,
            app,
            role_name=args.operator_role_name,
            table_roles=operator_table_roles,
            dry_run=args.dry_run,
        )
        results: dict[str, Any] = {
            "operator_role": op_result,
            "field_perm_supported": ok,
            "reason": reason,
            "tables": len(operator_table_roles),
        }
        if args.with_viewer:
            results["viewer_role"] = upsert_role(
                client,
                app,
                role_name=args.viewer_role_name,
                table_roles=viewer_table_roles,
                dry_run=args.dry_run,
            )

        logger.info(
            "完成。请在飞书「高级权限」里把负责人加入角色「%s」。"
            "系统应用身份写表不受此角色限制。",
            args.operator_role_name,
        )
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
