# 方案 B：按店物理分表（母表双写 + 子表）

## Context

当前飞书是「一个多维表格 base + 6 张全局母表」，店铺隔离靠**视图筛选**。你要求升级为 **方案 B**：每个逻辑店铺拥有一套完整业务子表，且 **母表继续保留、全量双写**（跨店总览不丢）。

已确认：
- **分表范围**：全部分表（ASIN每日 / 异常任务 / 运营动作 / 配置 / 每日汇总 / 产品主档案）
- **母表策略**：保留母表 + 同时写子表

本地实际逻辑店（`shop_aliases` 归一后）：`Ledvia-UK`、`Nottac-UK`、`特米-UK`、`昇新-UK`、`起的快-UK`、`字同道合`（约 6 店）。

现状写入全部走单一 `settings.feishu_table_*`（见 `app/sync/writer.py`、`app/notify/actions.py`、`app/notify/summary_table.py`），**没有按店路由**。

## 目标形态

同一 base 内：

| 类型 | 命名约定 | 数量 |
|---|---|---|
| 母表（已有） | `ASIN每日数据`、`异常任务`、… | 6 张 |
| 子表（新建） | `{母表名}__{规范店名}` 例：`ASIN每日数据__Ledvia-UK` | 6 店 × 6 逻辑表 ≈ **36 张** |

- 子表**只含本店数据**（按 `shop_aliases` 归一后的规范名匹配）
- 母表仍含**全店数据**（行为与今天一致）
- 侧边栏可直接打开某店子表，无需靠视图伪装

## 架构

```text
sync / rules / dispatch
  → 映射行（含 shop_name 原始值）
  → 规范店名 = canonicalize(shop_name)   # config.shop_aliases
  → 写母表（原 table_id）
  → 按规范店名 group → 写对应子表 table_id
```

注册表（持久化 table_id，避免每次 list_tables）：

- 文件：`data/feishu_shop_tables.json`（gitignore 可选，也可提交 id 映射）
- 或 `.env` 长 JSON：`FEISHU_SHOP_TABLE_MAP=...`（不推荐过长）
- 推荐：**json 文件 + 脚本生成**，Settings 增加加载路径

结构示例：

```json
{
  "Ledvia-UK": {
    "asin_daily": "tblxxx",
    "tasks": "tblyyy",
    "actions": "tblzzz",
    "config": "tbl...",
    "daily_summary": "tbl...",
    "product_master": "tbl..."
  },
  ...
}
```

## 实现步骤

### 1. 规范店名工具（复用已有别名）

- 将 `scripts/setup_asin_shop_views.py` 中的 `DEFAULT_SHOP_ALIASES` / `_canonical` / `_variants_for` **抽到** `app/sync/shops.py`（避免脚本与 runtime 重复）
- 提供：
  - `canonicalize_shop(name) -> str`
  - `list_canonical_shops(db|config) -> list[str]`
  - `shop_match_variants(canonical) -> list[str]`（写入过滤：原始 shop 属于该店任一变体）

### 2. Settings / 配置

**文件**：`app/config.py`、`config/config.yaml`

- 新增：`feishu_shop_tables_path`（默认 `data/feishu_shop_tables.json`）
- 新增：`feishu_dual_write_shop_tables: bool = True`（YAML `sync.dual_write_shop_tables`，可关闭仅写母表）
- 加载 `ShopTableRegistry`：`get_table_id(canonical_shop, kind) -> str | None`
- `kind` ∈ `asin_daily | tasks | actions | config | daily_summary | product_master`

母表 id 继续用现有 `FEISHU_TABLE_*`。

### 3. 初始化子表脚本

**新建** `scripts/init_shop_tables.py`：

1. 读规范店列表（DB 真实店 ∪ aliases 规范名）
2. `list_tables`，按命名 `{TABLE_SPECS[i].name}__{shop}` 幂等创建
3. 字段 = 母表同一 `*_FIELDS`（`app/sync/feishu_schema.py`）
4. 写出 `data/feishu_shop_tables.json` + 打印摘要
5. 可选：`--shops Ledvia-UK` 只建部分店；`--dry-run`

**不删除**母表；不改动现有 `init_feishu_tables.py` 母表逻辑（可在其文档中指向新脚本）。

### 4. 写入层改造（核心）

**文件**：`app/sync/writer.py`

抽取通用：

```python
def _write_to_table(client, app_token, table_id, fields_list, *, mode="upsert"|"create_if_absent"):
    ...

def dual_write_by_shop(
    rows: list[dict],
    *,
    mother_table_id: str,
    kind: str,
    shop_field: str,  # "店铺" 或从 row 取 shop_name
    get_fields: Callable,
    mode: str,
):
    # 1) mother: all rows
    # 2) for each shop group: child table
```

改造点：

| 函数 | 变更 |
|---|---|
| `write_asin_to_feishu` | 母表 upsert 全量；按 `canonicalize(shop_name)` 分组 upsert 子表 |
| `write_tasks_to_feishu` | 同上（`shop_name`） |
| `write_action_shells_to_feishu` | 同上；`ensure_action_table_columns` 对**每个子表**也 ensure（可缓存已处理 table_id） |
| `backfill_task_action_links` | 母表对跑一遍；**每个店**的 tasks 子表 ↔ actions 子表各跑一遍（关联不跨店） |

**文件**：`app/notify/summary_table.py`

- 母表：保持 `aggregate_daily_summary` 全局汇总写母表
- 子表：新增 `aggregate_daily_summary_for_shop(db, biz_date, shop_variants)` 或过滤 tasks/asin 后写该店 `daily_summary` 子表（主键仍可用 `biz_date` 或 `biz_date|shop`）

**配置表 / 产品主档案**

- **配置表**：双写时母表全量；子表写入「该店相关行」（若配置有 `店铺` 列则过滤；全局阈值行可复制到每店子表，便于单店打开即见）
- **产品主档案**：母表全量；子表按 `店铺` 过滤导入（改造 `scripts/import_product_master.py` 或统一走 registry）

配置/产品主档案若当前无日更写入路径，至少保证：
1. init 建子表
2. 导入脚本支持 dual write
3. 文档说明如何手工/脚本刷新

### 5. 匹配规则（避免写错店）

- 行上的 `shop_name` 先 `canonicalize` 再路由
- 子表过滤：`canonicalize(row.shop_name) == target_shop`
- 历史脏数据别名（`LEDVIE`/`Ledvia`）与 `Ledvia-UK` 进同一子表
- 未知店名：只写母表 + 打 warning（不丢数）

### 6. 视图与文档

- `setup_asin_shop_views.py`：母表上的按店视图**可保留**作备用；文档改为「分表为主、视图为辅」
- 更新 `docs/飞书接入指南.md`：删除「不分表」结论，改为母表+子表说明与 init 命令
- `README.md` 增加一节分表运维

### 7. CLI（可选但实用）

`app/main.py`：

- `python -m app.main init-shop-tables` 包装脚本
- `python -m app.main backfill-shop-tables --date YYYY-MM-DD`：从 SQLite 按日把已有 asin/tasks 重推到子表（上线后补历史）

### 8. 上线顺序（执行时）

1. 实现 `shops.py` + registry + init 脚本  
2. 跑 `init_shop_tables.py` 建 36 张空表，确认 json  
3. 改 writer 双写，先 `--date` 小流量验证 1 店有数据  
4. `backfill-shop-tables` 补近几日  
5. 产品主档案 / 配置再导入子表  
6. 飞书侧边栏验收：每店子表仅本店行；母表行数不变/仍全量  

## 关键文件

| 操作 | 路径 |
|---|---|
| 新建 | `app/sync/shops.py` |
| 新建 | `scripts/init_shop_tables.py` |
| 新建 | `scripts/backfill_shop_tables.py`（可并入 main） |
| 改 | `app/config.py` |
| 改 | `app/sync/writer.py` |
| 改 | `app/notify/summary_table.py`、`app/notify/actions.py` |
| 改 | `scripts/import_product_master.py` |
| 改 | `scripts/setup_asin_shop_views.py`（改为调用 `app.sync.shops`） |
| 改 | `config/config.yaml`、`.env.example`、`docs/飞书接入指南.md`、`README.md` |

复用：`FeishuClient.create_table` / `upsert_by_text_key` / `create_records_if_absent` / `TABLE_SPECS` / 已有 `shop_aliases`。

## 风险与约束

- **表数量**：约 36 张，飞书侧边栏会变长；命名统一前缀便于折叠阅读
- **关联字段**：任务↔动作链接只在同范围（母↔母、店↔店），不跨店
- **限流**：双写 ≈ 2× 写次数；保持现有 batch + sleep；子表按店顺序写
- **schema 变更**：以后加字段要「母表 + 全部子表」同步（可在 `ensure_*_columns` 扫 registry）
- **权限**：分表后可对单店子表单独加协作者（方案 B 的主要收益）

## 验证

1. `python scripts/init_shop_tables.py --dry-run` → 列出 6×6 表名  
2. `python scripts/init_shop_tables.py` → json 生成，飞书可见空子表  
3. `python -m app.main sync --date <近日>` → 母表行数≈原子表之和；任选 `ASIN每日数据__Nottac-UK` 仅 Nottac 变体  
4. `python -m app.main dispatch --date <近日> --dry-run-notify` → 任务/动作子表有本店 open 任务；关联列可回填  
5. 每日汇总：母表全局数字；子表该店 red/orange 与母表拆分一致  
6. 产品主档案 import 后子表行数 ≈ 该店档案数  

## 非目标（本次不做）

- 不为每店新建独立 base（仍在同一 `FEISHU_BITABLE_APP_TOKEN`）
- 不删除母表、不强制删旧「店铺_*」视图
- 不改 SQLite 本地 schema（本地仍全局表）
