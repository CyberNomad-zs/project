# SPEC: TK产品表赛狐→PG→飞书同步

| 字段 | 值 |
|------|-----|
| ID | SPEC-20260817-tk-sellfox-product-sync |
| 状态 | approved |
| mode | feature |
| 作者 | Claude（代拟，待用户批准） |
| 日期 | 2026-08-17 |
| 批准人 | 用户（口头批准） |
| 批准日期 | 2026-08-17 |

> 复制到工作区（`docs/specs/`），填空后走 DoR。

---

## 1. BRIEF — 问题与目标

### 1.1 原始需求（用户原话）

INTENT 路径：本 Spec 由对话澄清生成（无独立 INTENT 文件）。原始材料见下方摘要。

```text
用户 2026-08-17：
- 「这张表的数据能不能走赛狐API拿到」（指飞书 TK产品表 tbl69GJ8cAAhizmj，28 字段/173 行，原运营手动导入 Excel）
- 确认 5 条口径：
  1. 能走赛狐API的列走赛狐API
  2. 在售过滤（只同步 tkStatus=在售）
  3. 公式列（保本单量/毛利润率/利润率）= 飞书自算，清泉只灌入参
  4. 赛狐拿不到的列（亚马逊同款售价、黑猫RM附加费）= 空着
  5. 币种方案A：采购GBP/头程GBP 走赛狐；采购CNY/头程CNY 空着留手填
- 确认 4 条边界：
  a. 覆盖策略 = 首次全量 + 之后只新增
  b. 毛利润口径 = 飞书公式自算（赛狐只灌成本拆分入参，不灌毛利值）
  c. 触发方式 = 手动触发（不挂 cron，需要时在服务器容器跑）
  d. 缺数据策略 = 记日志 + 告警
```

### 1.2 问题陈述

- **谁遇到什么问题：** 运营在飞书 TK产品表手动维护 173 行在售商品的成本/利润账本，数据来自历史一次性 Excel 导入 + 日常手填。商品主数据（货源号/SKUID/品名/状态）与 PG `fact_tiktok_product` 同源但无自动同步；财务成本拆分（采购/头程/佣金/服务费等）靠手填，易过期且与赛狐 ERP 实际口径脱节。
- **不做的后果：** 运营每次新上架商品要手工在飞书建行并手填成本；赛狐已有商品主数据 + 利润报费用拆分（现网已落 PG 但未接飞书），不接则这部分能力闲置；飞书表与赛狐 ERP 持续脱节，成本口径无对账来源。

### 1.3 目标用户与场景

| 角色 | 场景 | 频率 |
|------|------|------|
| 运营（宋敏等） | 在飞书 TK产品表看在售商品的成本/利润账本 | 日常高频查看 |
| 运营 | 新上架商品后，触发同步让该行自动出现在飞书表 | 偶发（有新品时） |
| 工程/运营 | 在服务器手动跑同步命令，查日志确认覆盖/告警 | 每次同步触发时 |

### 1.4 成功标准（可观测）

- [ ] 手动在服务器容器跑一次同步命令，飞书 TK产品表在售商品行数 = PG `fact_tiktok_product` 中 `tkStatus=在售` 且赛狐有数据的商品数（允许赛狐缺数据的行按缺数据策略处理）
- [ ] 赛狐能覆盖的**可写列**（货源/品名/SKUID/上架状态/售价含VAT/采购GBP/服务费GBP/操作费GBP/配送费GBP，共 9 列）在首次同步后从赛狐灌入值（成本负数取绝对值）
- [ ] 13 个 Formula 列（平台价格/售价不含VAT/平台佣金/头程GBP/商品总成本GBP/毛利润/毛利润率/退款率/达人佣金/广告费/利润/利润率/保本单量）首次同步后由飞书现有公式从 9 可写入参自动重算出值（清泉不写这些列——API 写不进 Formula 类型）
- [ ] 采购CNY/头程CNY/亚马逊同款售价1/2/黑猫RM附加费 列在首次同步后保留运营手填原值（赛狐不碰）
- [ ] 赛狐无利润数据的在售 SKU 写入同步日志并在飞书群告警
- [ ] 第二次及以后同步只新增「新上架在售商品」行，已有行的可写列不被覆盖（运营手填值稳定保留）

### 1.5 非目标（Non-goals）

- 不做赛狐商品的 TK 后台双源对账（哪边作主数据由业务另行拍板，本期赛狐为财务/主数据来源）
- 不做定时自动同步（不挂 cron）
- 不做前端按钮/HTTP 接口触发
- 不做亚马逊同款售价、黑猫RM附加费的自动采集（本期空着）
- 不做 CNY 列的汇率反算或自动填充（采购CNY/头程CNY 留手填）
- 不改 `fact_tiktok_product` 现有 TK 采集通道，不触碰 ads/content/health 同步

---

## 2. SCOPE — 范围

### 2.1 In Scope

| # | 能力 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | 赛狐在售商品主数据同步到飞书 TK产品表 | P0 | 货源/品名/SKUID/上架状态/售价含VAT；按 tkStatus=在售 过滤 |
| 2 | 赛狐利润报 SKU 粒度费用拆分灌入飞书成本列 | P0 | 采购GBP/头程GBP/平台佣金/服务费GBP/操作费GBP/配送费GBP/广告费；从 `fact_sellfox_tk_profit_sku.raw_extra` 取 |
| 3 | 公式列保留飞书自算 | P0 | 毛利润/毛利润率/利润率/保本单量/退款率 等不写值，靠飞书公式从入参重算 |
| 4 | 首次全量 + 之后只新增的覆盖策略 | P0 | 首次：赛狐列覆盖手填；之后：只新增新行，已有行财务列不动 |
| 5 | 缺数据记日志 + 飞书群告警 | P0 | 赛狐无利润数据的在售 SKU 记日志并推 `FEISHU_BOT_WEBHOOK_TK_HEALTH`（复用现有群机器人） |
| 6 | 手动触发入口 | P0 | 服务器容器内 `python -m app.jobs.<新sync job>` 命令，支持 `--full`（首次全量）/默认（只新增） |

### 2.2 Out of Scope（≥ 3 条）

1. 不挂 cron 定时调度（手动触发即可，定时下一版评估）
2. 不做前端/HTTP 接口触发（不加 tk_ops 路由、不加任务台按钮）
3. 不自动采集亚马逊同款售价、黑猫RM附加费（这两列空着，留手填）
4. 不做 CNY 列自动填充或汇率反算（采购CNY/头程CNY 留手填）
5. 不做赛狐 vs TK后台商品双源对账/差异告警
6. 不改飞书表结构（28 列不动；不新建飞书表）

### 2.3 依赖

| 依赖 | 类型 | 状态 | 失败策略 |
|------|------|------|----------|
| 赛狐 OpenAPI（`openapi.sellfox.com`） | 系统 | 已对接（`tk_sellfox_sync.py` 通，三店映射齐，密钥在服务器 .env） | API 失败 → 同步中止 + 日志 + 群告警 |
| PG `fact_sellfox_tk_profit_sku` / `fact_tiktok_product` | 数据 | 已有数据（profit_sku 159 行、product sellfox 140 行；需先跑 `tk_sellfox_sync` 刷新） | PG 缺数据 → 按缺数据策略记日志告警，不阻塞 |
| 飞书 TK产品表 `tbl69GJ8cAAhizmj` | 系统 | 已存在（28 字段/173 行）；table id 需写入 .env | 飞书写失败 → batch_update/create 失败计数 + 日志 |
| 飞书群机器人 webhook | 系统 | 已有 `FEISHU_BOT_WEBHOOK_TK_HEALTH` | webhook 空 → 只落日志不推群（现有降级行为） |

### 2.4 MVP / Ship-now（Gate M，Spec 批准后填写）

> 本迭代先做哪一刀。Spec 批准后完成本节并走 `MVP READY`。

### Spec 引用

`docs/specs/SPEC-20260817-tk-sellfox-product-sync.md`（已批准 2026-08-17）

| 字段 | 值 |
|------|-----|
| 状态 | ready |
| 跳过理由 | （非跳过） |
| 另存路径 | （内联于本 SPEC §2.4） |

#### Ship-now（本迭代必做，≤ 5 条）

| # | 能力 | 对应 In Scope # | 说明 |
|---|------|-----------------|------|
| 1 | 新建飞书同步 job：PG 赛狐产品+利润 → 飞书 TK产品表 | 1,2 | mapper + 在售过滤 + 列映射 |
| 2 | 首次全量 vs 只新增 两模式 | 4 | `--full` flag |
| 3 | 公式列不写值 + 手填列不覆盖 | 3,4 | mapper 显式 omit 公式列与 CNY/亚马逊/黑猫列 |
| 4 | 缺数据记日志 + 群告警 | 5 | 复用 `FEISHU_BOT_WEBHOOK_TK_HEALTH` |
| 5 | .env 加 `FEISHU_BITABLE_TABLE_TK_PRODUCT` + store-tables.json 加 `tk_product` key | 1 | 配置接入 |

#### Defer（明确下一版）

1. cron 定时调度
2. 前端按钮 / HTTP 接口触发
3. 亚马逊同款售价、黑猫RM自动采集
4. CNY 列自动填充
5. 赛狐 vs TK后台双源对账

#### Success check（可演示/可测，≥ 1）

- [ ] 在服务器容器跑 `python -m app.jobs.<新job> --full`，飞书 TK产品表在售商品行从赛狐灌入成本拆分 + 主数据，公式列由飞书自动算出值，缺数据 SKU 在飞书群有告警

**MVP 批准记录：**

```text
批准人: 用户
日期: 2026-08-17
语句: 批准本迭代 MVP / Ship-now
```

---

## 3. 主流程

### 3.1 Happy path

1. 运营/工程 SSH 到服务器，进 qingquan-api 容器
2. （若 PG 赛狐数据旧）先跑 `python -m app.jobs.tk_sellfox_sync --days 30` 刷新 `fact_sellfox_tk_profit_sku` / `fact_tiktok_product`(source=sellfox)
3. 跑 `python -m app.jobs.<新product飞书sync job> --full`（首次）或不带 `--full`（只新增）
4. job 从 PG 读在售商品（`tkStatus=在售`）+ 对应 SKU 利润报费用拆分
5. job 按列映射组装飞书 fields：赛狐列灌值、公式列 omit、CNY/亚马逊/黑猫列 omit
6. job 首次模式：batch_create 新行 + batch_update 已有行（覆盖赛狐列）；只新增模式：仅 batch_create PG 有而飞书无的行
7. 缺数据的在售 SKU 记日志 + 推飞书群告警
8. job 输出统计：created / updated / skipped_no_sellfox_data / failed

### 3.2 异常与边界（≥ 3 edge）

1. 赛狐利润报里某在售 SKU 无数据 → 该行赛狐成本列空着（不阻塞），记日志 + 群告警，主数据列仍灌（货源/品名/SKUID/状态有）
2. 飞书表已有该货源号行但运营手填了采购GBP → 首次模式覆盖（按用户决定），只新增模式不动
3. 同一 product_id 在赛狐 profit_sku 有多行（不同区间/币种）→ 取最近一期 GBP 区间数据，多行记日志
4. 飞书 batch_update/create 部分失败 → 失败行 record_id 列入日志，统计 failed 计数，不回滚成功行
5. PG 赛狐数据为空（未先跑 tk_sellfox_sync）→ job 检测到 product/profit_sku 无 sellfox 数据，中止 + 日志提示先跑 tk_sellfox_sync
6. 商品下架（tkStatus 从在售变下架）→ 本期不从飞书删行（Out of Scope 双源对账），只新增不删除；下架行留在飞书表

---

## 4. 数据与权限

| 实体/数据 | 读 | 写 | 角色 | 敏感？ |
|-----------|----|----|------|--------|
| PG `fact_tiktok_product` | job 读 | 不写 | 工程 | 否（商品主数据） |
| PG `fact_sellfox_tk_profit_sku` | job 读 | 不写 | 工程 | 是（财务成本/利润，含金额） |
| 飞书 TK产品表 `tbl69GJ8cAAhizmj` | job 读（对齐已有行） | job 写（batch_create/update） | 工程+运营 | 是（财务账本） |
| 赛狐 OpenAPI | 不直接调（走 PG） | — | — | 是（赛狐凭据在 .env） |

**权限模型（一句话）：** 同步 job 以服务器 `.env` 的飞书 app token + 赛狐凭据运行，运营在飞书 UI 维护公式列与手填列，工程在服务器手动触发。

**数据删除/保留策略：** 本期不从飞书删行（只增/更新）；PG 数据保留按现有 `fact_*` 策略；赛狐凭据/财务金额不进日志明文（日志只记 SKU/统计数）。

**敏感数据约束：** 财务金额（采购/头程/佣金/毛利）属财务数据——**不进 Prompt、不进飞书群告警明文**（告警只说「N 个在售 SKU 赛狐无利润数据」+ SKU 列表，不写金额）；赛狐 secret 不进日志。

---

## 5. 集成

| 系统 | 方向 | 契约来源 | 备注 |
|------|------|----------|------|
| 赛狐 OpenAPI | in（间接，经 PG） | `docs/TK-赛狐数据源对照.md` + `tk_sellfox_sync.py` | 本 job 不直连赛狐，读 PG 已落数据 |
| PG `tk.fact_*` | in | 现有 schema | 读 product + profit_sku |
| 飞书 Bitable | out | `bitable.py` + 飞书 records API | batch_create/update 到 `tbl69GJ8cAAhizmj` |
| 飞书群机器人 | out | `FEISHU_BOT_WEBHOOK_TK_HEALTH` | 缺数据告警 |

---

## 6. 非功能（NFR）

| 项 | 要求 | N/A？ |
|----|------|-------|
| 语言 | Python（async，与现有 tk_feishu_sync 同构） | |
| 时区 | UTC + 北京展示（与现有同步一致） | |
| 多币种/计量 | 赛狐利润报 currency=GBP（现网已验证）；只取 GBP 行，CNY 列不灌 | |
| 性能 | 173 行级，batch_create/update ≤500/批，秒级完成 | |
| 审计日志 | 每次 sync 记 `sellfox_sync_run`（复用现有表）+ stdout 日志：created/updated/skipped/failed + 缺数据 SKU 列表 | |
| 环境 | 服务器 qingquan-api 容器内运行 | |

---

## 7. 合规与发布边界（维 8）

| # | 项 | 填写 |
|---|----|----------------|
| 8.1 | 目标区域/租户/环境 | 清泉组织飞书 TK Base（生产）；三店 UK/欧盟 |
| 8.2 | 外部平台/渠道 | 赛狐 OpenAPI（只读，已有凭据）；飞书 Bitable（读写） |
| 8.3 | 资金与计量 | **涉及财务成本/利润数据写入飞书**——但只读赛狐、写飞书运营表，不做结算/支付/计费。**G3 风险标注**：财务金额写入属敏感，需用户在 SPEC 批准时确认；金额不进群告警/Prompt |
| 8.4 | 法规与策略红线 | 无 PII；财务数据不外泄；赛狐凭据不提交仓库 |
| 8.5 | 审计与可追溯 | 每次 sync 写 `sellfox_sync_run` + stdout 日志（SKU 级统计） |
| 8.6 | 数据驻留与跨区 | 赛狐/飞书均国内 SaaS；PG 在腾讯云新加坡服务器；无跨区新增约束 |
| 8.7 | AI 披露 | N/A（无 AI 生成内容面向用户） |
| 8.8 | 授权范围 | 赛狐只读（已有授权）；飞书写 TK产品表（app token 已有权限）；不碰资金结算/外部凭据/法定字段 |
| 8.9 | 发布策略 | 手动触发，无灰度需求；首次 `--full` 跑前在测试店或小范围验证列映射，再全量 |

整维 N/A 理由：不适用（已逐项填写）。

---

## 8. ASSUMPTIONS（假设登记）

| ID | 假设 | 状态 | 若错的影响 |
|----|------|------|------------|
| A1 | [ASSUMES: 赛狐 `purchaseFee`=采购GBP、`logisticsFee`/`actualShippingFeeAmount`=配送费、服务费/操作费键待定；币种=GBP] | 已部分确认（Explore）：purchaseFee✓、headFee≠头程GBP（头程GBP是公式列）；服务费/操作费具体键 PHASE 6 实现时逐键核实 | 列映射错则灌错列 |
| A2 | [ASSUMES: 飞书公式列入参列名与赛狐灌入列名一致，首次同步后公式自动重算] | 已确认（Explore）：API 读不到公式表达式，但倒推确认 13 公式列入参=售价含VAT+采购GBP+头程CNY+配送费+服务费+操作费+率常量；赛狐灌 5 Number 入参后公式自算；靠首次同步后抽检公式列有值验证 | 若公式引用列名与赛狐灌入列名不一致，公式失值；抽检发现则回 PHASE 3 |
| A3 | [ASSUMES: 飞书表「货源」列（现索引列/主字段）值=赛狐 productId，可作为 batch_update 匹配键] | 待确认 | 若飞书表有行的货源列空（如 rec1 VIPGN22*2 货源=null），该行无法匹配更新，按只新增或跳过处理 |
| A4 | [ASSUMES: 赛狐 profit_sku 的 sku_key 能映射到飞书表 SKUID 列（seller_sku）] | 待确认 | SKU 维度对不齐则费用拆分灌不进对应行 |
| A5 | [ASSUMES: 首次全量覆盖运营手填的 GBP 成本列（采购GBP/头程GBP/佣金/服务费等）可接受] | 待用户批准 SPEC 时确认 | 若不可接受则改回「财务列永不覆盖」，缩小覆盖面 |
| A6 | [ASSUMES: 飞书群告警复用 `FEISHU_BOT_WEBHOOK_TK_HEALTH`，不新建 webhook] | 待确认 | 若运营要单独的「产品表同步告警群」则需新 webhook + .env |

---

## 9. OPEN QUESTIONS

> 未关闭 ≤ 2；阻断级必须关闭或升级。

| ID | 问题 | 阻断？ | 状态 |
|----|------|--------|------|
| Q1 | A1/A2/A4 的字段语义与列名对齐（赛狐费用键→飞书列名、飞书公式入参列名）需在 PHASE 4 Explore 时读现网数据 + 飞书公式定义核实；若对不齐是否阻断？ | N（可在 Explore 阶段关闭，不阻断 SPEC 批准） | open |
| Q2 | 首次全量覆盖手填 GBP 成本列是否可接受（A5）？ | Y（用户批准 SPEC 时确认） | open |

---

## 10. RISKS

| 风险 | 等级 | 缓解 | 是否 G3 |
|------|------|------|---------|
| 首次全量覆盖运营手填 GBP 成本列 | 中 | SPEC 批准时用户确认（A5）；建议首次跑前先 dry-run 打印将覆盖的行/列 | 否（数据丢失风险，非资金结算） |
| 财务金额写入飞书 | 中 | 金额不进群告警/Prompt/日志明文；只写飞书运营表 | **G3-边界**（财务数据，但非结算/支付/凭据；需用户确认） |
| 赛狐费用键→飞书列映射错 | 中 | PHASE 4 Explore 读现网 profit_sku + 飞书公式定义核对（A1/A2/A4） | 否 |
| 飞书公式列重算失效 | 中 | 首次同步后人工抽检 3 行公式列是否有值 | 否 |
| 赛狐缺数据导致行财务列长期空 | 低 | 记日志 + 群告警，运营人工补 | 否 |
| 同步 job 误删飞书行 | 低 | 本期只 create/update，代码不出现 delete 调用 | 否 |

---

## 11. DoR 自检

- [x] Out of Scope ≥ 3（6 条）
- [x] Open Questions 未关闭 ≤ 2（Q1 非阻断、Q2 待 SPEC 批准时确认）
- [x] Edge ≥ 3（6 条）
- [ ] 每主功能 ≥1 happy + ≥1 error AC（见 ACCEPTANCE）
- [x] 无不可测措辞（成功标准均可勾选/可观测）
- [x] 维 8 已填
- [ ] 用户批准：「可以按此 Spec 开发」
- [ ] （推荐）`check-dor.sh` PASS
- [ ] Spec 批准后完成 §2.4 并走 `MVP READY`

**批准记录：**

```text
批准人: 用户
日期: 2026-08-17
语句: 可以按此 Spec 开发
```
