# FINDINGS: TK产品表赛狐→PG→飞书同步

| 字段 | 值 |
|------|-----|
| Spec | SPEC-20260817-tk-sellfox-product-sync |
| 日期 | 2026-08-17 |
| 探查人 | Claude |
| 状态 | approved |

> PHASE 5 Findings（Gate B）。feature 模式，基于真实阅读核查 Plan 与现有代码冲突。

## Findings

### 探查范围

- `backend/app/config.py`（行 41-49：`feishu_bitable_table_tk_*` 字段）
- `backend/app/adapters/feishu/bitable.py`（行 629-668：mapper 函数尾部 + `_omit_none`/`_num` 辅助）
- `backend/app/jobs/tk_feishu_sync.py`（行 365-405 TABLE_SPECS；行 518-541 `_list_table_field_names`；行 544-547 `_filter_fields_to_table`；行 735-748 分店 fan-out）
- `backend/app/jobs/` 目录（现有 tk_*.py 文件清单）
- `config/feishu-tk-store-tables.json`（tables 段结构）

### 当前状态（事实）

1. `config.py` 现有 6 个 `feishu_bitable_table_tk_*` 字段（shop_daily/ads_campaign/anomaly_task/content_daily/affiliate_creator_daily/experience_daily），命名规范统一。新加 `feishu_bitable_table_tk_product` 同构，无冲突。
2. `bitable.py` 现有 9 个 `*_to_fields` mapper，都用 `_omit_none({...})` + `_num()` 辅助。新 `tk_product_to_fields` 放文件末尾，同构无冲突。
3. `backend/app/jobs/` 现有 12 个 tk_*.py，无 `tk_sellfox_product_feishu_sync`——新文件名不撞车，且语义清晰（区别于 `tk_sellfox_sync` 赛狐→PG 和 `tk_feishu_sync` PG→飞书日表）。
4. `tk_feishu_sync.py` 的 `TABLE_SPECS` 是**硬编码 dict**（6 个 key），**不**遍历 `store-tables.json` 的 tables 段。`store-tables.json` 只被按 `table_key`（来自 TABLE_SPECS）查分店 table_id（行 739 `meta.get("tables").get(table_key)`）。

### 意外发现

1. **`_list_table_field_names` 会返回 Formula 列名**（行 534-537 只取 `field_name`，不管 `ui_type`）。→ `_filter_fields_to_table`（行 544-547）**过滤不掉 Formula 列**（它们在 allowed 集合里）。
   - **影响 P2：** 如果 mapper 意外包含了 13 公式列名，`_filter_fields_to_table` **不会兜底挡住**，会直接发给飞书 batch_update。
   - **缓解：** mapper 必须**自己显式 omit** 13 公式列（不放进返回 dict）。Plan 方案 3 已含此设计，Findings 强化为**硬约束**：mapper 的 9 列白名单是唯一防线，不能依赖 filter。

2. **`store-tables.json` 加 `tk_product` key 安全**：`tk_feishu_sync.py` 不会主动同步 `tk_product`（不在 TABLE_SPECS），只有新 job 显式查 `tk_product` key 才用。三店同 table_id `tbl69GJ8cAAhizmj` 无妨——产品表非分店表，新 job 不走分店 fan-out，直接用 `.env` 的总表 id（D2 已定 job 自管，不依赖 store-tables fan-out）。
   - **小优化：** 新 job 可直接读 `.env` 的 `FEISHU_BITABLE_TABLE_TK_PRODUCT`，**不必**依赖 `store-tables.json`。Plan 文件列表里 `store-tables.json` 加 key 可改为「可选/备用」，避免给 `tk_feishu_sync.py` 留无用 key。但保留也无害（不会被误读）。**建议保留 Plan 原案**（加 key），为未来分店产品表预留。

3. **`bitable.batch_update_records` 现有实现无 Formula 列特殊处理**（行 65-85）：直接把 fields dict 发给飞书。Formula 列在 batch_update 时的行为（静默忽略 vs 报错）仍不确定（P2）。mapper omit 是唯一保险。

4. **无迁移需求确认**：新 job 只读现有 `fact_tiktok_product` / `fact_sellfox_tk_profit_sku`（迁移 006/018 已在生产），不新建表、不改 schema。`sellfox_sync_run` 复用（迁移 018 已建）。Plan 无迁移文件，正确。

### 对原 Plan 的影响

- [x] **无影响，按原 Plan 执行**（含 1 处强化）
- [ ] 需修订 Plan
- [ ] 需打回 L1

**强化点（不改 Plan 文件，实现时遵守）：**
- mapper 的 9 列白名单是**唯一**公式列防线——`tk_product_to_fields` 返回的 dict **不得**包含 13 公式列名。不能依赖 `_filter_fields_to_table`（它不挡 Formula）。这是 P2 风险的根因缓解。
- 新 job 读 table_id 优先用 `.env` 的 `FEISHU_BITABLE_TABLE_TK_PRODUCT`；`store-tables.json` 加 `tk_product` key 保留为备用（不被 `tk_feishu_sync` 误读，已证实）。

### 修订后的 Plan

无修订。Plan 原案有效，含上述强化约束。

### 风险增量

- **P2 风险上调为「mapper 白名单是唯一防线」**：`_filter_fields_to_table` 不挡 Formula 列。实现时 mapper 必须严格 9 列白名单；单测必须断言「fields 不含 13 公式列名」（ACCEPTANCE F3-H1 已覆盖，单测强化）。
- 其余风险不变。

## SOP Status

```text
- mode: feature
- phase: 5 — Findings / Gate B
- skill-pack: 04 (loaded)
- artifacts: FINDINGS-...md (进仓)
- mvp: approved | arch: approved (v2) | plan: approved
- gate: Gate B waiting
- blockers: none
- next: 等你批准 Findings → PHASE 6 实现
```
