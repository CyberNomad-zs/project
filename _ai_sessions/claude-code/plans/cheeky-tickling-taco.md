# Plan: 合并运营动作记录表到异常任务表

## Context

当前飞书多维表格中，"异常任务"和"运营动作记录"是两个独立的表，通过单向关联(type=18)和 `backfill_task_action_links()` 每日回填机制同步数据（动作-闭环状态、动作-原因等 5 个文本列）。这增加了：
- 表间关联维护的复杂度
- 双重写入（`write_action_shells_to_feishu` + `backfill_task_action_links`）
- 用户需要在两个表之间切换

**目标**：将运营动作记录的所有字段直接合并到异常任务表中，取消独立的运营动作记录表，简化数据模型和日常同步流程。

## 改动文件清单

### 1. `app/sync/feishu_schema.py` — 核心 schema 变更

**TASK_FIELDS 变更**：
- 删除：`关联运营动作`(type=18)、`动作-闭环状态`、`动作-原因`、`动作-采取动作`、`动作-是否有效`、`动作-复查日期`
- 新增（来自原 ACTION_FIELDS 的独有字段）：`是否属实`、`原因`、`判断依据`、`采取动作`、`执行日期`、`执行人`、`需审核事项`、`复查日期`、`动作前数据`、`动作后数据`、`是否有效`、`下一步动作`、`闭环状态`

**删除**：
- `ACTION_FIELDS` 整个列表
- `action_pk_for_task()` 函数
- `action_shell_from_task()` 函数

**TABLE_SPECS**：删除 `{"env_key": "FEISHU_TABLE_ACTIONS", "name": "运营动作记录", ...}`

**task_to_fields()**：增加 action 相关字段的映射（从 task dict 中读取，初始为空/None）

### 2. `app/config.py`
- 删除 `feishu_table_actions` Field 定义

### 3. `app/sync/writer.py` — 删除整个动作表写入/回填体系
- 删除 `ACTION_SYSTEM_FIELD_NAMES`
- 删除 `ensure_action_table_columns()`
- 删除 `write_action_shells_to_feishu()`
- 删除 `ACTION_COPY_COLUMNS`
- 删除 `_backfill_pair()`
- 删除 `backfill_task_action_links()`
- `write_tasks_to_feishu()`: 删除 `fields.pop("关联运营动作", None)` 这一行

### 4. `app/notify/actions.py` — 简化 dispatch 流程
- 删除 `write_action_shells_to_feishu` 和 `backfill_task_action_links` 的 import
- 删除 `dispatch_open_tasks()` 中的 `create_action_shells` 参数及相关逻辑（步骤 54-64）
- `dispatch_open_tasks()` 返回值去掉 `action_shells` 和 `task_action_links`

### 5. `app/notify/owner_push.py` — 只保留任务表链接
- `_view_urls()`: 删除 `actions_url`，只返回 `tasks_url`
- `_build_owner_card()`: 去掉 `actions_url` 参数，按钮改为只有"查看任务表"
- `build_owner_messages()`: 更新文案（从"打开运营动作记录"改为"在任务表中补全"），去掉 actions_url
- 卡片按钮只保留一个"查看任务表"

### 6. `app/notify/daily_digest.py` — 只保留任务表链接
- `build_digest_card()`: 删除 `actions_url`，按钮只保留"查看任务表"

### 7. `app/main.py` — CLI 命令更新
- 删除 `push-action-shells` 命令（或将其改为 no-op 提示）
- `dispatch_cmd`: 删除 `--no-actions` 参数及相关逻辑
- `backfill_shop_tables_cmd`: 删除 action_shells 和 links 回填逻辑

### 8. `app/sync/shops.py` — 删除 actions kind
- `KIND_TO_MOTHER_NAME`: 删除 `"actions": "运营动作记录"`
- `TABLE_KINDS`: 自动更新（从 KIND_TO_MOTHER_NAME 推导）

### 9. `scripts/init_shop_tables.py` — 不再创建 action 子表
- `ENV_TO_KIND`: 删除 `"FEISHU_TABLE_ACTIONS": "actions"`
- 删除创建 action 子表的逻辑
- 删除创建单向关联字段的逻辑
- 删除 action 定位列补充的逻辑

### 10. `scripts/setup_action_lookup.py` — 整个文件废弃
- 此脚本的唯一作用是在任务表上创建关联列和动作文本列，合并后毫无意义
- 可直接删除或在文件顶部标注"已废弃"

### 11. `scripts/migrate_feishu_fields.py`
- `name_to_id`: 删除 `"运营动作记录": settings.feishu_table_actions`

### 12. `.env.example`
- 删除 `FEISHU_TABLE_ACTIONS=` 行

### 13. `docs/飞书接入指南.md`
- 删除 `FEISHU_TABLE_ACTIONS` 相关行

## 关键设计决策

1. **字段命名**：直接使用原始 ACTION 字段名（如 `原因`、`采取动作`、`闭环状态`），不再加"动作-"前缀。这些字段在任务表中语义清晰。

2. **初始值**：合并后，新 action 字段在任务记录中初始为空。负责人直接在任务表上编辑这些字段（取代之前在动作表编辑再由回填同步的模式）。

3. **向后兼容**：`feishu_table_actions` 配置项保留在 `.env` 中不会导致错误（pydantic `extra="ignore"`），但脚本不再使用它。

## 验证

1. 运行 `python -c "from app.sync.feishu_schema import TASK_FIELDS, TABLE_SPECS; print('OK')"` 确认 schema 可导入
2. 运行 `python -c "from app.config import get_settings; print(get_settings().feishu_table_tasks)"` 确认配置正常
3. 运行现有测试：`python -m pytest tests/ -v`（如果涉及相关模块）
4. 检查 `scripts/init_shop_tables.py --dry-run` 不再尝试创建 action 子表
5. 手动检查 `TASK_FIELDS` 打印输出，确认字段完整且无重复
