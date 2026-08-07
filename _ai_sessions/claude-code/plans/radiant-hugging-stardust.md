# 飞书多维表格仪表盘充实话 — 实施计划

## Context

项目一期主链路已打通（sync → rules → dispatch → notify），但飞书侧的协作体验比较粗糙：
- 没有每日汇总表，老板看不到全局概览
- 字段类型（日期、站点）全用文本，无法在飞书 UI 中按日期筛选/排序/做图
- 群机器人推送是纯文本，信息密度低，没有视觉层次
- 逾期升级逻辑已写好（`escalate.py`）但从未接入推送

本次改进覆盖方向 2-5，全部是程序可控的改动，不需要手动 UI 操作。

## 改动总览

| # | 改动 | 涉及文件 |
|---|------|----------|
| 2 | 新增"每日汇总"表，程序每天自动写入 | feishu_schema.py, db.py, main.py, 新建 notify/summary_table.py |
| 3 | 字段类型优化：日期→飞书日期、站点/店铺→单选 | feishu_schema.py, sync/writer.py, scripts/migrate_feishu_fields.py |
| 4 | 群机器人消息升级为交互式卡片 | clients/feishu.py, notify/daily_digest.py, notify/owner_push.py, notify/escalate.py |
| 5 | 逾期升级接入 dispatch 流水线 + 独立 CLI | notify/escalate.py, notify/actions.py, main.py |

---

## 2. 新增"每日汇总"表

### 2.1 飞书表定义 (`app/sync/feishu_schema.py`)

新增 `DAILY_SUMMARY_FIELDS` 和对应的 `TABLE_SPECS` 条目：

| 字段 | 类型 | 说明 |
|------|------|------|
| 主键 | 文本 | `{biz_date}` |
| 日期 | 日期 | 业务日期 |
| 店铺数 | 数字 | 参与统计的店铺数 |
| ASIN总数 | 数字 | 参与统计的 ASIN 总数 |
| 红色任务 | 数字 | 当日红色任务数 |
| 橙色任务 | 数字 | 当日橙色任务数 |
| 黄色观察 | 数字 | 当日黄色观察数 |
| 任务总计 | 数字 | 红+橙+黄合计 |
| 逾期任务 | 数字 | 所有逾期未关闭任务数 |
| 库存预警(红) | 数字 | inventory_low 红色数 |
| 库存预警(橙) | 数字 | inventory_low 橙色数 |
| 广告异常 | 数字 | acos_abnormal + ad_spend_abnormal 合计 |
| 销量异常 | 数字 | sales_drop + order_drop 合计 |
| TOP异常类型 | 文本 | 出现最多的异常类型 |
| 负责人分布 | 文本 | JSON 字符串，各负责人任务数 |
| 同步批次 | 数字 | run_id |

环境变量：`FEISHU_TABLE_DAILY_SUMMARY`

### 2.2 数据汇总查询 (`app/store/db.py`)

新增方法：
- `aggregate_daily_summary(biz_date: str) -> dict` — 聚合查询，返回上述字段所需的所有统计数据

### 2.3 汇总构建与写入 (`app/notify/summary_table.py`)

新建文件，提供：
- `build_summary_row(db, biz_date) -> dict` — 调用 db 聚合查询，返回 feishu 记录
- `write_summary_to_feishu(row, settings) -> dict` — 写入飞书每日汇总表（upsert）

### 2.4 CLI 接入 (`app/main.py`)

- 新增 `push-summary` 命令
- `once` 和 `dispatch` 命令增加 `--push-summary` 选项

---

## 3. 字段类型优化

### 3.1 Schema 更新 (`app/sync/feishu_schema.py`)

将以下字段从 `T_TEXT` → `T_DATE`：
- ASIN每日数据：`日期`
- 异常任务：`日期`、`截止时间`
- 运营动作记录：`执行日期`、`复查日期`

将以下字段从 `T_TEXT` → `T_SINGLE`（单选）：
- ASIN每日数据：`站点`（已有的 marketplace 值）、`店铺`（已有的 shop_name 值）
- 运营动作记录：`等级`（对齐任务表的 yellow/orange/red 选项）

### 3.2 写入适配 (`app/sync/writer.py`)

飞书日期字段需要毫秒级 Unix 时间戳（int64），修改 `map_product_analyze_row` 中的日期字段输出格式：
- `biz_date` → 增加 `biz_date_ts` 字段（时间戳），写入飞书日期列
- 任务表中的 `due_at` → 同样转为时间戳

### 3.3 迁移脚本 (`scripts/migrate_feishu_fields.py`)

新建脚本，逻辑：
1. 对每张表，调用 `list_fields` 获取现有字段
2. 对需要类型优化的字段，如果仍是文本类型：
   - 用新名称创建正确类型的新字段（如 `日期` → 先建 `日期_v2`）
   - 通过 `iter_records` + `batch_update` 把文本值迁移到新字段
   - 过程中记录条数，支持断点续跑
3. 打印手动步骤提示：删旧字段、重命名新字段（飞书 API 不支持删字段/重命名字段，需手动）

> **注意**：飞书开放 API 不支持删除字段和重命名字段。迁移脚本负责建新字段+数据搬迁，旧字段的清理和新字段的重命名需在飞书 UI 中手动完成。

---

## 4. 群机器人消息升级为交互式卡片

### 4.1 新增卡片发送方法 (`app/clients/feishu.py`)

新增方法：
- `send_webhook_card(card: dict, webhook=None) -> dict` — 发送 `msg_type: "interactive"` 消息

包含卡片的 JSON Schema 构建辅助：
- `_card_header(title: str, color: str) -> dict` — 卡片头部（红/橙/绿/蓝）
- `_card_md(text: str) -> dict` — lark_md 文本元素
- `_card_button(text: str, url: str) -> dict` — 跳转按钮

### 4.2 日摘要卡片 (`app/notify/daily_digest.py`)

改用卡片格式：

```
┌─────────────────────────────────┐
│ 🔴 ASIN健康度 2026-07-22 异常摘要 │  ← 红色头部
├─────────────────────────────────┤
│ 红色 15  |  橙色 13  |  观察 11   │  ← KPI 行
│ 逾期未关闭: 3                    │
├─────────────────────────────────┤
│ 👤 梦晴    🔴8  🟠4              │  ← 负责人汇总
│ 👤 潘启豪   🔴5  🟠5              │
│ 👤 马文静   🔴2  🟠4              │
├─────────────────────────────────┤
│ [查看任务表]  [查看动作表]         │  ← 跳转按钮
└─────────────────────────────────┘
```

保留原有 `build_digest`（纯文本）作为 fallback，新增 `build_digest_card`。`send_digest` 优先发卡片，配置 `FEISHU_USE_CARD=false` 时回退纯文本。

### 4.3 负责人推送卡片 (`app/notify/owner_push.py`)

```
┌─────────────────────────────────┐
│ 🟠 待你处理 2026-07-22            │  ← 橙色/红色头部（依任务等级）
├─────────────────────────────────┤
│ 👤 梦晴  |  红 8  |  橙 4        │
├─────────────────────────────────┤
│ 🔴 #T001 sales_drop xxx ASIN    │
│ 🟠 #T002 acos_abnormal xxx ASIN │
│ ...（最多8条）                    │
├─────────────────────────────────┤
│ [打开动作表补充处理信息]           │  ← 一键跳转
└─────────────────────────────────┘
```

卡片颜色按最高等级决定：有红色任务→红色头部，仅有橙色→橙色头部。

### 4.4 逾期升级消息也使用卡片

`escalate.py` 的 `build_overdue_message` 改造为卡片格式，红色头部，列出逾期任务明细。

---

## 5. 逾期升级接入推送

### 5.1 补全 escalate.py

新增 `send_escalate_notification(db, settings, dry_run=False) -> dict`：
1. 调用 `find_overdue_tasks(db)` 
2. 过滤：仅对 `need_boss_decision=True` 或红色逾期超过 2 个工作日的任务发起升级
3. 调用 `build_overdue_message`（或直接 `build_overdue_card`）
4. 通过 `FeishuClient.send_webhook_card` 发送到群
5. 写入 `db.log_notify("escalate", ...)` 留底

### 5.2 接入 dispatch 流水线

`app/notify/actions.py` 的 `dispatch_open_tasks` 最后增加：
```python
if escalate:
    out["escalate"] = send_escalate_notification(db, settings, dry_run=dry_run_notify)
```

### 5.3 CLI 接入 (`app/main.py`)

- 新增 `escalate` 命令（`--dry-run`）
- `dispatch` 命令增加 `--escalate/--no-escalate` 选项
- `once` 命令增加 `--escalate/--no-escalate` 选项

---

## 文件修改清单

| 文件 | 操作 | 影响 |
|------|------|------|
| `app/sync/feishu_schema.py` | 编辑 | 新增 DAILY_SUMMARY_FIELDS + TABLE_SPECS；字段类型优化 |
| `app/store/db.py` | 编辑 | 新增 aggregate_daily_summary 方法 |
| `app/notify/summary_table.py` | **新建** | 汇总表构建+写入 |
| `app/clients/feishu.py` | 编辑 | 新增 send_webhook_card + 卡片构建辅助方法 |
| `app/notify/daily_digest.py` | 编辑 | 新增 build_digest_card；send_digest 优先卡片 |
| `app/notify/owner_push.py` | 编辑 | 新增 build_owner_cards；push_tasks_to_owners 卡片发送 |
| `app/notify/escalate.py` | 编辑 | 新增 send_escalate_notification；构建卡片 |
| `app/notify/actions.py` | 编辑 | dispatch_open_tasks 增加 escalate 步骤 |
| `app/notify/__init__.py` | 编辑 | 导出新模块 |
| `app/main.py` | 编辑 | 新增 push-summary、escalate 命令；once/dispatch 增加参数 |
| `app/sync/writer.py` | 编辑 | 日期字段值格式适配（时间戳） |
| `app/config.py` | 编辑 | Settings 新增 FEISHU_TABLE_DAILY_SUMMARY 等 |
| `scripts/migrate_feishu_fields.py` | **新建** | 字段类型迁移脚本 |
| `scripts/init_feishu_tables.py` | 编辑 | 支持创建每日汇总表 |
| `scripts/setup_summary_views.py` | **新建** | 为每日汇总表创建视图 |

---

## 验证方法

1. **字段类型**：运行 `scripts/migrate_feishu_fields.py --dry-run`，检查日志输出
2. **汇总表**：运行 `python -m app.main push-summary --date 2026-07-21 --dry-run`，检查生成的数据行
3. **卡片推送**：运行 `python -m app.main notify --date 2026-07-21 --dry-run`，检查打印的卡片 JSON
4. **逾期升级**：运行 `python -m app.main escalate --dry-run`，检查逾期任务列表和卡片 JSON
5. **全链路**：运行 `python -m app.main once --date 2026-07-21 --dry-run-notify`，确认 4 个改进点均生效
6. **单元测试**：运行 `python -m pytest tests/ -v`
