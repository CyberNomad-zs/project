# ACCEPTANCE: TK产品表赛狐→PG→飞书同步

| 字段 | 值 |
|------|-----|
| Spec ID | SPEC-20260817-tk-sellfox-product-sync |
| 状态 | draft |

> 与 SPEC 成对使用。Gherkin 为主。

---

## 约定

- 场景标题清晰、可独立验证
- 禁止：可能、大概、适当、优化一下、尽快
- 每个 Scenario 应能在 <5 分钟内由人或脚本判定 pass/fail

---

## 功能 F1: 在售商品主数据同步（赛狐 → 飞书）

### Happy

```gherkin
Scenario: F1-H1 首次全量同步在售商品主数据
  Given 服务器容器内 PG fact_tiktok_product 有 174 行 tkStatus=在售，且 source=sellfox 行已刷新
  When 运行 python -m app.jobs.tk_sellfox_product_feishu_sync --full
  Then 飞书 TK产品表 tbl69GJ8cAAhizmj 在售商品行的「货源/品名/SKUID/上架状态/售价（含VAT）」列被赛狐值灌入
  And 同步日志输出 created=N updated=M skipped_no_sellfox_data=K failed=0
```

### Error / 边界

```gherkin
Scenario: F1-E1 PG 赛狐数据为空时中止
  Given PG fact_tiktok_product 无 source=sellfox 行（未先跑 tk_sellfox_sync）
  When 运行 python -m app.jobs.tk_sellfox_product_feishu_sync --full
  Then job 中止，不调用飞书写接口
  And 日志输出提示「先运行 python -m app.jobs.tk_sellfox_sync 刷新赛狐数据」
```

```gherkin
Scenario: F1-E2 商品下架后不从飞书删行
  Given 飞书表已有货源=1729440514610072752 的行，该商品在 PG 变为 tkStatus=已下架
  When 运行只新增模式同步（不带 --full）
  Then 飞书表该行不被删除、不被更新
  And 同步日志不计入该行（只新增在售新行，不处理下架）
```

---

## 功能 F2: 赛狐利润报费用拆分灌入飞书成本列

### Happy

```gherkin
Scenario: F2-H1 首次全量灌入 GBP 成本拆分（9 可写列）
  Given PG fact_sellfox_tk_profit_sku 有 SKU=VIPGN22 的利润行，raw_extra 含 purchaseFee=-3.56（负数）, 配送费键=-1.75
  When 运行 --full 同步
  Then 飞书表该行的「采购 GBP」=3.56（取绝对值）、「配送费GBP」=1.75（取绝对值）被赛狐值灌入
  And 「平台佣金/头程 GBP/广告费」3 个 Formula 列不被 job 写入（API 写不进），由飞书公式自算
  And 「采购 CNY/头程 CNY」列保持原值（不被赛狐写）
```

### Error / 边界

```gherkin
Scenario: F2-E1 赛狐无该 SKU 利润数据
  Given 某在售 SKU 在 PG fact_sellfox_tk_profit_sku 无对应行
  When 运行同步
  Then 该行赛狐成本列（采购GBP/头程GBP/佣金/服务费等）保持空或原值
  And 该 SKU 记入同步日志的 skipped_no_sellfox_data 列表
  And 飞书群（FEISHU_BOT_WEBHOOK_TK_HEALTH）收到告警，含 SKU 列表但不含金额
```

```gherkin
Scenario: F2-E2 同一 SKU 多区间利润行取最近一期
  Given PG fact_sellfox_tk_profit_sku 对 SKU=VIPC2VY 有两条不同 period 的行
  When 运行同步
  Then 取 period_end 最大的一期数据灌入
  And 日志记录该 SKU 有多区间数据（记一行警告）
```

---

## 功能 F3: 公式列飞书自算（清泉不写值）

### Happy

```gherkin
Scenario: F3-H1 公式列不被同步 job 写入
  Given 飞书表 13 个 Formula 列（平台价格/售价不含VAT/平台佣金/头程GBP/商品总成本GBP/毛利润/毛利润率/退款率/达人佣金/广告费/利润/利润率/保本单量）
  When 运行 --full 同步
  Then 同步 job 的 batch_update/create fields 中不包含这 13 个列名（API 写不进 Formula 类型）
  And 同步完成后人工抽检 3 行，这 13 个公式列有自动重算出的值（入参=售价含VAT+采购GBP+头程CNY+配送费+服务费+操作费）
```

### Error / 边界

```gherkin
Scenario: F3-E1 公式入参列名与赛狐灌入列名不一致导致公式失效
  Given 飞书某公式引用「采购成本GBP」而赛狐灌入列名是「采购 GBP」
  When 首次同步后人工抽检
  Then 该公式列显示 #ERROR 或空
  And 记入 FINDINGS，回 PHASE 3 修正列映射（列名对齐）
```

---

## 功能 F4: 首次全量 vs 只新增覆盖策略

### Happy

```gherkin
Scenario: F4-H1 只新增模式不覆盖已有行财务列
  Given 飞书表已有货源=X 的行，运营手填「采购 GBP」=5.0；PG 赛狐该 SKU 采购GBP=3.56
  When 运行只新增模式同步（不带 --full）
  Then 飞书表该行「采购 GBP」仍为 5.0（不被覆盖）
  And 该行不在 updated 计数（只新增 PG 有而飞书无的行）
```

### Error / 边界

```gherkin
Scenario: F4-E1 首次全量覆盖手填值
  Given 飞书表已有货源=X 的行，运营手填「采购 GBP」=5.0；PG 赛狐该 SKU 采购GBP=3.56
  When 运行 --full 同步
  Then 飞书表该行「采购 GBP」变为 3.56（首次覆盖，按用户决定）
  And 日志记录该行在 updated 计数
```

---

## 功能 F5: 缺数据记日志 + 飞书群告警

### Happy

```gherkin
Scenario: F5-H1 缺数据 SKU 推群告警
  Given 同步发现 3 个在售 SKU 在赛狐利润报无数据
  When 同步完成
  Then 飞书群收到告警消息，含 3 个 SKU 的 SKUID 列表
  And 告警消息不含任何金额数字
  And stdout 日志含 skipped_no_sellfox_data=3 + SKU 列表
```

### Error / 边界

```gherkin
Scenario: F5-E1 webhook 未配置时只落日志
  Given .env 未配置 FEISHU_BOT_WEBHOOK_TK_HEALTH（空）
  When 同步发现缺数据 SKU
  Then 不推群，仅 stdout 日志记录缺数据 SKU 列表
  And job 不报错继续完成
```

---

## Edge 清单（汇总，≥ 3）

| ID | 描述 | 期望行为 | 对应 Scenario |
|----|------|----------|---------------|
| E1 | 赛狐无某在售 SKU 利润数据 | 成本列空/保留原值 + 记日志 + 群告警（无金额） | F2-E1, F5-H1 |
| E2 | 飞书表货源列空行（如 VIPGN22*2 货源=null） | 无法匹配更新，首次按新增建行或跳过，记日志 | F1（隐含，实现时处理） |
| E3 | 商品下架 | 不删飞书行，只新增模式不处理 | F1-E2 |
| E4 | 同一 SKU 多区间利润行 | 取最近一期，记警告 | F2-E2 |
| E5 | 首次全量覆盖手填 GBP 成本列 | 按用户决定覆盖，日志记 updated | F4-E1 |
| E6 | 公式列入参列名不匹配 | 公式失效，记 FINDINGS 回 PHASE 3 | F3-E1 |
| E7 | PG 赛狐数据未刷新 | 中止 + 提示先跑 tk_sellfox_sync | F1-E1 |
| E8 | webhook 未配置 | 只落日志不推群，不报错 | F5-E1 |
| E9 | 13 Formula 列 API 写不进 | job fields 中 omit 这 13 列，由飞书公式自算；抽检有值 | F3-H1 |
| E10 | 赛狐成本是负数、飞书要正数 | mapper 取 abs() 灌入 | F2-H1 |
| E11 | product seller_sku 多规格拼接 | 拆 `\|` 逐个匹配 profit_sku sku_key | F2（实现时处理） |
| E12 | profit_sku 只覆盖 Gardena（Deal/SHOP INOUT 缺） | 69% 在售缺数据，按缺数据策略记日志告警 | F2-E1 |

---

## 可勾选验收（发布/Demo 用）

### MVP Demo（与 SPEC §2.4 Success check 对齐）

- [ ] 服务器容器跑 `python -m app.jobs.tk_sellfox_product_feishu_sync --full`，飞书 TK产品表在售行灌入赛狐成本+主数据
- [ ] 公式列（毛利润/毛利润率/利润率/保本单量）首次同步后由飞书自动重算出值
- [ ] 采购CNY/头程CNY/亚马逊同款售价/黑猫RM 列保留手填原值
- [ ] 缺数据 SKU 在飞书群有告警（无金额）
- [ ] 第二次只新增模式跑，已有行财务列不被覆盖

### P0

- [ ] 在售过滤（tkStatus=在售）生效，下架商品不进飞书新行
- [ ] 首次全量 vs 只新增两模式行为符合 F4
- [ ] 公式列在 fields 中被 omit（代码层验证）
- [ ] 缺数据 SKU 记日志 + 群告警（F5）
- [ ] 财务金额不进群告警/Prompt/日志明文
- [ ] .env 含 FEISHU_BITABLE_TABLE_TK_PRODUCT，store-tables.json 含 tk_product key

### P1（可选）

- [ ] 同步统计写 sellfox_sync_run 表（复用）
- [ ] dry-run 模式打印将覆盖的行/列不实写

---

## 验证记录

| 日期 | 人/命令 | 结果 | 备注 |
|------|---------|------|------|
| | | | |
