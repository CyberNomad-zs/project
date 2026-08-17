# PLAN: TK产品表赛狐→PG→飞书同步

| 字段 | 值 |
|------|-----|
| Spec | SPEC-20260817-tk-sellfox-product-sync |
| Mode | feature |
| 状态 | approved |
| 日期 | 2026-08-17 |

> Plan ⊆ Ship-now，落在 ARCH v2 已声明模块/边界内。

### 引用

- Spec：`docs/specs/SPEC-20260817-tk-sellfox-product-sync.md`
- MVP：SPEC §2.4
- ARCH：`docs/specs/ARCHITECTURE-20260817-tk-sellfox-product-sync.md`（v2 approved）
- Explore：`docs/specs/EXPLORE-20260817-tk-sellfox-product-sync.md`
- ACCEPTANCE：`docs/specs/ACCEPTANCE-20260817-tk-sellfox-product-sync.md`

### Objective

新建「PG 赛狐产品+利润 → 飞书 TK产品表」同步 job，手动触发，把在售商品的 9 可写列从赛狐灌入飞书，13 公式列由飞书自算，缺数据记日志+群告警，首次全量/之后只新增两模式。

### 文件列表

| 动作 | 路径 | 所属 ARCH 模块 | 说明 |
|------|------|----------------|------|
| 新建 | `backend/app/jobs/tk_sellfox_product_feishu_sync.py` | 新 job | 主同步逻辑：读 PG、关联 profit_sku、调 mapper、batch_create/update、缺数据告警、`--full` flag、统计 |
| 改 | `backend/app/adapters/feishu/bitable.py` | mapper | 加 `tk_product_to_fields(row)` 函数（9 可写列映射，成本负数取 abs，omit 13 公式列 + CNY/亚马逊/黑猫/SKU） |
| 改 | `backend/app/config.py` | Settings | 加 `feishu_bitable_table_tk_product: str = ""` 字段 |
| 改 | `config/feishu-tk-store-tables.json` | 分店表映射 | tables 段三店各加 `"tk_product": "tbl69GJ8cAAhizmj"`（三店同表，产品表非分店表，但复用 store-tables 读取入口） |
| 改 | 服务器 `/opt/qingquan/.env` | 配置 | 加 `FEISHU_BITABLE_TABLE_TK_PRODUCT=tbl69GJ8cAAhizmj`（生产部署步骤，非 git） |
| 新建 | `backend/tests/test_tk_sellfox_product_feishu_sync.py` | 测试 | mapper 单测 + 关联键拆分单测 + abs 口径单测 + 缺数据告警单测 |
| 新建 | `docs/ops/SERVER.md`（追加节） | 文档 | 记录手动触发命令、首次全量/只新增、前置 tk_sellfox_sync、告警 |

**部署相关（非 git 文件，生产操作步骤）：**
- `scp` 新 job + 改后的 bitable.py/config.py 到服务器 `/opt/qingquan/backend/...`
- 服务器 `.env` 加 table id（备份 .env.bak）
- rebuild api/worker 镜像（代码内嵌，不挂载）
- `docker cp` 改后的 `feishu-tk-store-tables.json` 到两容器 `/config/`（容器内 `_REPO_ROOT=/`，路径 `/config/`）

### 方案（5 条）

1. **新 job 结构照 `tk_sellfox_sync.py` 同构**：async + sqlalchemy `SessionLocal` + `text()` 查询 + `httpx` 调飞书（经 `bitable.py`）。main() argparse：`--full` flag、`--dry-run`（打印将覆盖的行/列不实写）、`--shop`（可选过滤单店调试）。不复用 `tk_feishu_sync.py` 窗口框架（D1）。

2. **数据读取与关联**：
   - 读 `fact_tiktok_product` WHERE `status='在售'`，按 `product_id` 去重（D8，优先有 seller_sku 的行）
   - 对每行，拆 `seller_sku` 的 `|`，逐个 join `fact_sellfox_tk_profit_sku` ON `sku_key = seller_sku_part`，取 `period_end` 最大一期（D5，现网单一期退化）
   - 关联不到 → 进 `skipped_no_sellfox_data` 列表
   - 前置检查：`fact_tiktok_product` 无 sellfox 数据或 `fact_sellfox_tk_profit_sku` 为空 → 中止 + 提示先跑 `tk_sellfox_sync`（F1-E1）

3. **mapper `tk_product_to_fields`（D3/D4/D6/D7）**：硬编码 9 可写列映射，成本值 `abs(Decimal(raw_extra键))`，omit 13 公式列 + 采购CNY/头程CNY/黑猫RM/亚马逊售价1/2/SKU。费用键→飞书列映射（PHASE 6 实现时用现网 raw_extra 逐键核实服务费/操作费/配送费具体键，先按 Explore 候选：purchaseFee→采购GBP、actualShippingFeeAmount→配送费GBP、logisticsFee→服务费GBP 候选、operationFee?→操作费GBP 候选）。

4. **幂等与覆盖（D2 + 覆盖策略）**：
   - job 启动时 `list_records` 拉飞书表现有 record_id ↔ 货源列值（product_id）映射 dict
   - `--full`：PG 行的 product_id 在 dict 中 → batch_update（覆盖 9 可写列）；不在 → batch_create
   - 默认（只新增）：仅 batch_create PG 有而飞书无的 product_id；已有行**不动**（F4-H1）
   - 不写 `sync_feishu_map`（D2 选 C）

5. **缺数据告警（F5）**：`skipped_no_sellfox_data` 列表 → 推 `FEISHU_BOT_WEBHOOK_TK_HEALTH`（复用），消息含 SKUID 列表**不含金额**；webhook 空 → 只落日志。同步结束写 `tk.sellfox_sync_run` 一行（modules=["product_feishu"], stats={created,updated,skipped,failed}）。

### 非目标

- cron 定时、HTTP 接口、前端按钮（Defer）
- 亚马逊同款售价/黑猫RM/CNY 自动采集（Out of Scope）
- 改飞书表结构、改 13 公式列（Out of Scope）
- 改 `tk_feishu_sync.py` / `tk_sellfox_sync.py` 现有逻辑（不改）
- 自动部署（生产部署步骤手动，rebuild 需用户授权）

### 待决决策（PHASE 6 实现时关闭）

| ID | 待决 | 关闭方式 |
|----|------|----------|
| P1 | 服务费GBP/操作费GBP/配送费GBP 对应 profit_sku raw_extra 哪个具体键 | 实现时 dump 一条 profit_sku raw_extra 全键，对照飞书表手填值反推 |
| P2 | 飞书 batch_update 写 Formula 列名是静默忽略还是报错 | 首次 dry-run 单行试写验证；若报错则 mapper 已 omit 可挡 |
| P3 | fact_tiktok_product 两批记录（TK采集/sellfox）是否真同 product_id 重复 | 实现时 `SELECT product_id, count(*) GROUP BY 1 HAVING count>1` 核实 |
| P4 | 飞书表现有 173 行 vs PG 在售 191 行的差集（飞书有PG无 / PG有飞书无） | 首次 dry-run 打印双向 diff，确认只新增模式行为 |

### 风险与回滚

| 风险 | 缓解 | 回滚 |
|------|------|------|
| 首次 --full 覆盖运营手填 9 列 | SPEC 已确认；`--dry-run` 先预览；建议首次只对 Gardena 单店试跑（`--shop gardena`） | 飞书表有操作历史，人工恢复手填值；job 不删行 |
| Formula 列写报错 | mapper omit 13 公式列 + `_filter_fields_to_table` 双保险 | 若仍报错，回 PHASE 3 加显式 Formula 列过滤 |
| 服务费/操作费键映射错（P1） | dry-run 打印映射结果对照手填值 | 改 mapper 键名重跑 |
| 69% 缺数据告警刷屏 | 告警按店聚合一条（N 个 SKU/店），不逐条 | 调整告警聚合粒度 |
| rebuild 后 /tmp 脚本丢失 | 用 `python -m app.jobs...` 不依赖 /tmp | — |
| 生产部署误操作 | 按 SERVER.md 步骤：scp→备份.env→rebuild→docker cp→冒烟 | 镜像可回滚到上一个 tag |

### 验证计划（对照 MVP Demo）

1. **本机单测**：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_tk_sellfox_product_feishu_sync.py -v`
   - mapper 9 列输出正确、13 公式列不在 fields、成本 abs() 转换、seller_sku 拆分匹配、缺数据告警格式（无金额）
2. **本机 dry-run**（需 .env 有飞书 token + 本机能连服务器 PG？——本机无 PG，dry-run 只能测 mapper 逻辑，PG 读取在服务器测）
3. **服务器冒烟**（生产授权后）：
   - `docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python -m app.jobs.tk_sellfox_product_feishu_sync --dry-run --shop gardena` → 看将覆盖行/列
   - `... --full --shop gardena` → Gardena 单店首跑
   - 人工抽检飞书表 3 行：9 可写列有赛狐值、13 公式列有重算值、CNY/亚马逊/黑马 保留手填
   - `... `（不带 --full）→ 只新增模式，已有行不动
   - 看飞书群告警（缺数据 SKU 列表无金额）
4. **全量**：Gardena 验证通过后跑无 `--shop` 的 `--full`，再跑只新增确认幂等

### SOP Status（Plan 阶段）

```text
- mode: feature
- phase: 4 — Explore + Plan / Gate A
- skill-pack: 04-spec-to-plan (loaded)
- artifacts: PLAN-...md (draft)；EXPLORE-...md (进仓)
- mvp: approved
- arch: approved (v2)
- gate: Gate A waiting
- blockers: none（P1-P4 实现时关闭，非阻断）
- next: 等你批准 Plan → PHASE 5 Findings（feature 有现有代码，需 Findings）→ PHASE 6 实现
```
