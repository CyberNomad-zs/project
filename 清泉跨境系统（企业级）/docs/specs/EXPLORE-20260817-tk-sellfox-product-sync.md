# Explore 记录：TK产品表赛狐同步（PHASE 4 探查）

| 字段 | 值 |
|------|-----|
| Spec | SPEC-20260817-tk-sellfox-product-sync |
| 日期 | 2026-08-17 |
| 探查人 | Claude |

> PHASE 4 Explore 产物。核实 ARCH 留的待确认点（A1/A2/A4/D2）。结论回灌 ARCH/Plan。

## 1. 飞书表 28 列可写性（A2 核实）

飞书 list_fields API **不返回公式表达式**（Formula 列 `property.formula=null`，API 限制）。

按 ui_type 分类：

| 类型 | 数量 | 可写？ | 列 |
|---|---|---|---|
| Text | 6 | ✅ 可写 | 货源、品名、SKU、SKUID、上架状态、亚马逊同款售价1 |
| Number | 9 | ✅ 可写 | 售价含VAT、黑猫RM、服务费GBP、操作费GBP、配送费GBP、采购GBP、采购CNY、头程CNY、亚马逊同款售价2 |
| Formula | 13 | ❌ **不可写**（飞书自算） | 平台价格、售价不含VAT、平台佣金、头程GBP、商品总成本GBP、毛利润、毛利润率、退款率、达人佣金、广告费、利润、利润率、保本单量 |

**关键发现（推翻 ARCH 原假设）：** `平台佣金`、`头程 GBP`、`广告费` 是 Formula 类型——ARCH 原计划让赛狐灌这 3 列是**错的**，API 写不进。赛狐实际能灌的列 = 15 可写列中赛狐有数据的 9 列。

## 2. 公式入参倒推（读现网记录 rec0-2）

通过读飞书表现有记录的 Number 值与 Formula 值关系，倒推公式依赖：

- `头程 GBP`(0.6) = `头程 CNY`(5.58) ÷ 汇率(≈9.3) → **依赖头程 CNY（手填），赛狐不碰**
- `平台佣金`(1.2591) = `售价不含VAT`(11.658) × 佣金率(0.108) → 依赖售价
- `商品总成本GBP`(5.91) = `采购GBP`(3.56) + `头程GBP`(0.6) + `配送费GBP`(1.75) = 5.91 ✓ → 依赖采购GBP+头程GBP+配送费GBP
- `毛利润` = 售价不含VAT − 商品总成本 − 平台佣金 − ...
- `广告费`(2.18) = `售价不含VAT`(11.658) × 广告费率(0.1872) → 依赖售价

**结论：** 13 个公式列的入参 = `售价含VAT` + `采购GBP` + `头程CNY`(→头程GBP) + `配送费GBP` + `服务费GBP` + `操作费GBP` + 各种率（藏在公式常量里）。

**赛狐灌这 5 个 Number 列（售价含VAT/采购GBP/服务费GBP/操作费GBP/配送费GBP）后，13 个公式列自动重算**——不需要写公式列，不需要读公式表达式。`头程 GBP` 公式列依赖 `头程 CNY`（手填），赛狐不碰，仍由飞书算。

## 3. 赛狐→飞书列映射（A1 核实）

| 飞书列 | 类型 | 赛狐来源 | 口径处理 |
|---|---|---|---|
| 货源 | Text | `fact_tiktok_product.product_id` | 直填 |
| 品名 | Text | `fact_tiktok_product.product_name` | 直填（英文名，飞书表现有是中文名→可能不一致，记 FINDINGS） |
| SKUID | Text | `fact_tiktok_product.seller_sku`（拆 `\|`） | 直填 |
| 上架状态 | Text | `fact_tiktok_product.status`（在售/已下架枚举映射） | 映射 |
| 售价（含VAT） | Number | `fact_tiktok_product` 子体 `priceIncludeVat`（在 raw_extra）或利润报 | 取正数 |
| 采购 GBP | Number | `profit_sku.raw_extra->>'purchaseFee'` | **取绝对值**（赛狐是负数冲减，飞书要正数） |
| 服务费GBP | Number | `profit_sku.raw_extra` 服务费键（待定具体键，候选 `logisticsFee`/`mallServiceFeeAmount`） | 取绝对值 |
| 操作费GBP | Number | `profit_sku.raw_extra` 操作费键（候选 `operationFee`?需核实） | 取绝对值 |
| 配送费GBP | Number | `profit_sku.raw_extra->>'actualShippingFeeAmount'` 或 `logisticsFee` | 取绝对值 |

**待 PHASE 6 实现时用现网 profit_sku raw_extra 逐键核实服务费/操作费/配送费的具体键名**（raw_extra 有 60+ 费用键，需业务/数据对照确定哪个键 = 飞书哪列）。

**不灌的列：**
- 13 个 Formula 列（API 写不进，飞书自算）
- 采购 CNY / 头程 CNY（手填，赛狐无 CNY）
- 黑猫RM附加费（赛狐无）
- 亚马逊同款售价1/2（赛狐无）
- SKU 列（飞书表里多为 null，与 SKUID 重复，不灌）

## 4. 关联键（A4 核实）

- `fact_tiktok_product.seller_sku` ↔ `fact_sellfox_tk_profit_sku.sku_key` 可 join
- **复杂点1**：product 的 `seller_sku` 有多规格拼接（`vip8558\|VIPC2VY\|vipH6XD\|vipKS63`），需拆分后逐个匹配 profit_sku
- **复杂点2**：现网在售 191 行，profit_sku 只覆盖 60 行（全 Gardena，Deal/SHOP INOUT 无 profit_sku 数据）→ **69% 缺数据**，首次同步会推大批缺数据告警（真实情况，非 bug）
- profit_sku 只有单一 period（2026-07-08..08-06），D5「取 period_end 最大一期」现网退化为取唯一期

## 5. product 数据源选择（新发现）

`fact_tiktok_product` 现网两批记录：
- TK 采集（174 行，`raw_extra->>'source'` 为空）
- 赛狐拉（140 行，`source=sellfox`）
- 按 `UNIQUE(shop_external_id, product_id)` 各占一行（同 product_id 两条记录？需核实是否真重复）

**Plan 决策：** 同步读 `fact_tiktok_product` 时按 `product_id` 去重，优先取 `status=在售` 且有 `seller_sku` 的行；profit_sku 关联用 seller_sku。**PHASE 6 实现时核实两批是否同 product_id 重复**。

## 6. D2 幂等方式核实

- `sync_feishu_map.local_id` 为 uuid，product_id 为 text → 确认不直接复用
- **决策定 C**：job 内自管 `product_id → record_id` 映射，从飞书表现读（list records 取 货源列值↔record_id），不写 sync_feishu_map
- 只新增模式：比对飞书现有货源列值集合，PG 有而飞书无的才 create
- 首次全量：飞书已有的按货源匹配 update（覆盖 9 可写列），无的 create

## 7. 对 ARCH 的修订（边界变更）

原 ARCH「赛狐灌入 ~12 列」→ 修正为「**赛狐灌 9 可写列**（5 主数据 Text + 4 成本 Number：采购GBP/服务费GBP/操作费GBP/配送费GBP）+ 售价含VAT」。

13 个 Formula 列由飞书自算，不灌——这从「我们选择不写」变为「**结构上写不进**」。

此变更属模块边界/数据流变化，按 SOP 回 PHASE 3 修订 ARCH 再批。

## 8. 对 SPEC 的修订

- 成功标准「平台佣金/头程GBP/广告费 从赛狐灌入」→ 修正为「这 3 列是 Formula，飞书自算；赛狐灌 9 可写列后公式自动重算」
- A1 假设：`purchaseFee`=采购GBP 仍成立；`headFee`≠头程GBP（头程GBP 是公式列，依赖头程CNY）→ 修正
- A2 假设：从「公式入参列名一致」修正为「API 读不到公式表达式，靠灌 5 Number 列后抽检公式列有值验证」
