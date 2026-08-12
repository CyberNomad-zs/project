# TK / 全平台 SKU 相关字段说明 · 同事交接

> 快照日期：**2026-08-07**（对照代码 + 迁移 + 2026-08-06 生产实查）  
> 用途：说明 PostgreSQL 里 **和 SKU 有关的字段** 分别在哪张表、从哪抓、含义是什么、怎么用、常见脏数据  
> 相关：
> - [TK-销量字段说明-同事交接.md](./TK-销量字段说明-同事交接.md)
> - [TK-赛狐数据源对照.md](./TK-赛狐数据源对照.md)
> - [字段映射字典.md](./字段映射字典.md)
> - [数据库现状说明.md](./数据库现状说明.md)

---

## 0. 30 秒结论

| 问题 | 答案 |
|------|------|
| PG 里「SKU」是一个字段吗？ | **不是**。至少有 `seller_sku` / `sku_id` / `sku_key` / `msku_list` / `commoditySku` 等多套 |
| 运营说的「商家 SKU / Seller SKU」看哪？ | 主字段 **`seller_sku`**（商品、订单头、订单行、异常任务） |
| 平台 SKU 数字 ID 看哪？ | **`sku_id`**（订单头/行；商品侧在 `raw_extra.sku_ids`） |
| 赛狐利润按 SKU 看哪？ | `tk.fact_sellfox_tk_profit_sku`（`grain=sku` 或 `msku`） |
| 订单列表页能直接抓到 SKU 吗？ | **不能稳定抓**；列表常空，要靠 **订单详情页** 补 `order_line` 再回填订单头 |
| 多规格怎么存？ | `seller_sku` 用 `\|` 拼接；完整数组在 `raw_extra.seller_skus` |
| 颜色词（Black/Pink…）是 SKU 吗？ | **不是**；赛狐偶发把颜色写进 `msku`，同步时已过滤，勿当编码 |

**推荐用法（稳态）：**

```text
商品主档「这个链接的卖家 SKU」     → tk.fact_tiktok_product.seller_sku
订单履约「这单买了哪个 SKU」       → tk.fact_tiktok_order_line.seller_sku / sku_id
订单头快速检索（可能为空/单 SKU） → tk.fact_tiktok_order.seller_sku / sku_id
利润区间「某 SKU 卖了多少」       → tk.fact_sellfox_tk_profit_sku（grain 勿混加）
异常任务飞书列「SKU」             → tk.fact_tk_anomaly_task.seller_sku
亚马逊链接日「SKU」               → fact_amz_link_daily.seller_sku（无 ASIN 时作业务键）
内容「归因 SKU 订单数」           → fact_tiktok_content_daily.attributed_sku_orders（是数量，不是 SKU 编码）
```

---

## 1. 先分清：三种「SKU」不是一回事

| 名称 | 常见别名 | 形态示例 | 体系 | 用途 |
|------|----------|----------|------|------|
| **卖家 SKU** | Seller SKU / 商家 SKU / MSKU | `JMCATCJCT`、`JMCATYZWJ*2` | 卖家自编 | 运营/仓储/对货主码 |
| **平台 SKU ID** | SKU ID / skuId | `1729xxxxxxxxxxxx`（长数字） | TikTok 平台 | 规格级唯一 ID、订单行键 |
| **ERP / 货品 SKU** | commoditySku / 赛狐货品编码 | 赛狐货品编码 | 赛狐 ERP | msku 脏时回退；仓配映射 |
| **赛狐利润 SKU 键** | sku_key / skuList / mskuList | 报表行拼接键 | 赛狐财务 | 区间利润切片，**不是**前台一行一码 |

> 业务口头说「SKU」时，默认多半指 **卖家 SKU（seller_sku）**。  
> 写 SQL / 对接前务必确认是编码还是平台 ID，还是利润表的 `sku_key`。

---

## 2. 三店主数据（查 SKU 前先对齐店）

| 店名（清泉） | 紫鸟 `external_shop_id` | 赛狐数字 `shopId` | 赛狐 Shop Code |
|--------------|-------------------------|-------------------|----------------|
| Deal to deal | `27501502216807` | `429674` | `GBLCJGQ23Q` |
| SHOP INOUT | `27328767468273` | `396800` | `GBLCAW729L` |
| Gardena | `27758103898326` | `610764` | `HKGBCB8LQLRC` |

```sql
SELECT name, external_shop_id,
       meta->>'sellfox_shop_id'   AS sellfox_shop_id,
       meta->>'sellfox_shop_code' AS sellfox_shop_code
FROM shop
WHERE platform = 'tiktok'
ORDER BY name;
```

---

## 3. 字段清单（按表）

下列均以 **`tk` schema** 为准（`public` 下有同名镜像/视图时结构一致，生产优先 `tk.`）。

---

### 3.1 商品主档 · `tk.fact_tiktok_product`（SKU 主战场之一）

| 字段 | 类型 | 含义 |
|------|------|------|
| `product_id` | text | TK 商品 ID；缺 ID 时可能为 `sku:{seller_sku}` 或 `name:…` 兜底 |
| `seller_sku` | text | **卖家 SKU**；多规格用 `\|` 拼接，如 `SKU-A\|SKU-B` |
| `raw_extra.seller_skus` | jsonb 数组 | 多规格完整列表（推荐拆规格时用这个） |
| `raw_extra.sku_ids` | jsonb 数组 | 赛狐子体平台 `skuId` 列表（**仅赛狐同步时有**） |
| `raw_extra.raw_mskus` | jsonb 数组 | 赛狐原始 msku（可能含颜色脏值） |
| `raw_extra.commodity_skus` | jsonb 数组 | 赛狐 `commoditySku`（ERP 货品码） |
| `raw_extra.children` | jsonb | 子体精简明细（skuId/msku/commoditySku/库存等） |
| `raw_extra.source` | text | `sellfox` = 赛狐写入；缺省多为紫鸟/Seller 页面采集 |
| `sales_qty` / `stock_qty` / `price` | numeric | 销量/库存/标价（不是 SKU 编码） |

**粒度：** 店铺 × `product_id`（**父体/链接级**，不是一行一个规格）。  
**幂等：** `(shop_external_id, product_id)`。

#### 抓取来源 A · TK Seller 商品列表（紫鸟浏览器采集）

| 项 | 说明 |
|----|------|
| 脚本 | `collectors/tiktok-ads/scripts/scrape-products-page.js` |
| 页面 | TK Seller **商品管理**列表 |
| 抽取规则 | 正则匹配 `商家SKU` / `Seller SKU` / `卖家SKU` 后的编码 |
| 多规格 | 先点「N 个 SKU 展开」，再合并 `sellerSkus[]`；单列字段 `sellerSku` 用 `\|` join |
| 噪声过滤 | 拒绝 `2 个 SKU展开`、`SKU展开`、`Expand N SKU` 等 UI 文案当 SKU |
| 入库 | Ingest `source=tiktok_products` → `backend/app/api/ingest.py` |
| 写入策略 | `COALESCE`：新值非空才覆盖，**不主动清空**已有 scrape 值 |

#### 抓取来源 B · 赛狐 OpenAPI 商品子体

| 项 | 说明 |
|----|------|
| Job | `python -m app.jobs.tk_sellfox_sync`（模块 `products`） |
| 接口 | 自营店父体 `…/shop/product/getParentPageList.json` + 子体 `…/getChildInfo.json` |
| 字段映射 | 见下表 |
| 标记 | `raw_extra.source = 'sellfox'` |
| 写入策略 | `seller_sku = COALESCE(NULLIF(新值,''), 旧值)` —— **不覆盖**已有正规 scrape SKU |

| 赛狐子体字段 | 落入 | 说明 |
|--------------|------|------|
| `msku` | 优先 → `seller_sku` / `seller_skus` | 对应 TK 商家 SKU；**偶发是颜色文案** |
| `commoditySku` | msku 脏时回退；另存 `raw_extra.commodity_skus` | ERP 货品 SKU |
| `skuId` | `raw_extra.sku_ids[]` + children | 平台规格 ID |
| `quantity` | `stock_qty`（子体合计） | 可售库存 |
| `priceIncludeVat` 等 | `price` | 标价 |

**颜色脏值过滤（2026-08-06 事故后已修）：**

- `Black / Pink / Green and purple` 等 **不当** `seller_sku`
- 合法编码如 `JMCATCJCT`、`VIPKGCZ`（可无数字）**保留**
- 清理脚本：`scripts/_cleanup_colorish_product_sku.sql`

```sql
-- 商品 SKU 覆盖与来源
SELECT shop_name,
       count(*) AS n,
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '') AS with_sku,
       count(*) FILTER (WHERE raw_extra->>'source' = 'sellfox') AS from_sellfox
FROM tk.fact_tiktok_product
GROUP BY 1
ORDER BY 1;

-- 看多规格数组
SELECT product_id, seller_sku,
       raw_extra->'seller_skus' AS seller_skus,
       raw_extra->'sku_ids' AS sku_ids,
       raw_extra->>'source' AS src
FROM tk.fact_tiktok_product
WHERE seller_sku LIKE '%|%'
LIMIT 20;
```

---

### 3.2 订单头 · `tk.fact_tiktok_order`

| 字段 | 类型 | 含义 |
|------|------|------|
| `order_id` | text | 平台订单号 |
| `seller_sku` | text | 订单头级卖家 SKU（**单 SKU 有值；多 SKU 订单可能只回填首行**） |
| `sku_id` | text | 订单头级平台 SKU ID（同上，可能不全） |
| `product_name` | text | 商品名（列表摘要） |
| `quantity` | numeric | 订单件数（头） |

**粒度：** 店铺 × 订单号（**一头一行**，不是 SKU 明细）。  
**幂等：** `(shop_external_id, order_id)`。

#### 抓取来源

| 路径 | 脚本 / 入口 | SKU 情况 |
|------|-------------|----------|
| 订单**列表**页 | `scrape-orders-page.js` | 列表 DOM **通常抽不到** SKU，`sellerSku`/`skuId` 常为空串 |
| 订单**详情**页 | `scrape-order-detail-page.js` → Ingest `tiktok_order_lines` | 抽出行级 SKU 后，**回填**订单头空字段（`COALESCE`，不覆盖已有） |
| 补数脚本 | `collectors/tiktok-ads/scripts/fill-order-skus.ps1` | 对缺 SKU 订单批量打开详情补抓 |

**重要：**  
- 要「这单每个规格买了什么」→ 必须看 **`fact_tiktok_order_line`**，不要只看订单头。  
- 订单头 `seller_sku` 适合列表展示/粗检索，**不保证多规格完整**。

```sql
SELECT shop_name,
       count(*) AS orders,
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '') AS with_seller_sku,
       count(*) FILTER (WHERE sku_id IS NOT NULL AND btrim(sku_id) <> '') AS with_sku_id
FROM tk.fact_tiktok_order
GROUP BY 1
ORDER BY 1;
```

---

### 3.3 订单明细行 · `tk.fact_tiktok_order_line`（SKU 粒度真相源）

| 字段 | 类型 | 含义 |
|------|------|------|
| `order_id` | text | 订单号 |
| `line_no` | int | 行号（默认 1） |
| `line_key` | text | **稳定行键**：优先 `sid:{sku_id}`，其次 `sku:{seller_sku}`，再次 `n:{line_no}` |
| `product_id` | text | 商品 ID（能抽到时） |
| `product_name` | text | 行商品名 |
| `seller_sku` | text | **行级卖家 SKU**（商家 SKU） |
| `sku_id` | text | **行级平台 SKU ID** |
| `quantity` | numeric | 行件数 |
| `unit_price` / `pay_amount` | numeric | 单价 / 行金额 |

**粒度：** 店铺 × 订单 × `line_key`。  
**幂等：** `(shop_external_id, order_id, line_key)`。  
**索引：** `seller_sku`、`sku_id` 均有部分索引。

#### 抓取来源 · 订单详情页（紫鸟）

| 项 | 说明 |
|----|------|
| 脚本 | `collectors/tiktok-ads/scripts/scrape-order-detail-page.js` |
| 标定 | seller-uk，2026-08-06 |
| 商家 SKU | 正则：`商家SKU` / `卖家SKU` / `Seller SKU` + 编码（允许 `*` 如 `JMCATYZWJ*2`） |
| 平台 SKU ID | 正则：`SKU ID` / `平台SKU ID` + 10–22 位数字 |
| 切块策略 | 优先以每个 `SKU ID` 窗口切行；否则按 `商家SKU` 窗口 |
| Ingest | `source=tiktok_order_lines`（见 `ingest.py`） |
| 回填头 | 行入库后，若订单头 `seller_sku`/`sku_id` 为空，用**该行**值 `COALESCE` 回填 |

```sql
-- 某单 SKU 明细
SELECT order_id, line_key, seller_sku, sku_id, quantity, unit_price, product_name
FROM tk.fact_tiktok_order_line
WHERE order_id = '<ORDER_ID>'
ORDER BY line_no;

-- 按卖家 SKU 汇总件数（履约口径）
SELECT shop_name, seller_sku,
       sum(quantity) AS qty,
       count(DISTINCT order_id) AS orders
FROM tk.fact_tiktok_order_line
WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> ''
  AND biz_date >= CURRENT_DATE - 14
GROUP BY 1, 2
ORDER BY qty DESC
LIMIT 50;
```

---

### 3.4 赛狐利润 · SKU/MSKU · `tk.fact_sellfox_tk_profit_sku`

| 字段 | 类型 | 含义 |
|------|------|------|
| `grain` | text | **`sku`** 或 **`msku`** —— 两套切片，**SUM 勿混加** |
| `sku_key` | text | 幂等/去重键（由 list 拼接） |
| `sku_list` | jsonb | 赛狐 `skuList` |
| `msku_list` | jsonb | 赛狐 `mskuList`（卖家 SKU 侧） |
| `commodity_name_list` | jsonb | 货品名列表 |
| `period_start` / `period_end` | date | **报表区间**（不是自然日一行） |
| `sales_qty` / `return_qty` | numeric | 区间销/退件数 |
| `gross_sales_amount` / `gross_profit` / `ads_cost`… | numeric | 金额类 |

**来源：**

| grain | 赛狐 API |
|-------|----------|
| `sku` | `POST /api/financial/tkReport/queryPageSku.json` |
| `msku` | `POST /api/financial/tkReport/queryPageMsku.json` |

**Job：** `tk_sellfox_sync` 模块 `profit_sku` / `profit_msku`。  
**幂等：** `(shop_external_id, period_start, period_end, grain, sku_key, currency)`。

**注意（2026-08-06）：**

- 利润 SKU 表当前生产主要可靠在 **Gardena**；另两店件数优先用 **statement** 或商品/订单。  
- `sku_key` 是报表行键，**不一定**等于前台单个 `seller_sku` 字符串。  
- 关联前台时：优先 `msku_list` ↔ `fact_tiktok_product.seller_sku` / `order_line.seller_sku`。

```sql
SELECT shop_name, grain,
       count(*) AS n,
       sum(COALESCE(sales_qty, 0)) AS sales_sum
FROM tk.fact_sellfox_tk_profit_sku
GROUP BY 1, 2
ORDER BY 1, 2;

-- 展开 msku 看编码
SELECT shop_name, grain, sku_key, msku_list, sku_list, sales_qty
FROM tk.fact_sellfox_tk_profit_sku
WHERE grain = 'msku'
ORDER BY sales_qty DESC NULLS LAST
LIMIT 30;
```

---

### 3.5 赛狐账单 · `tk.fact_sellfox_tk_statement`

| 与 SKU 关系 | 说明 |
|-------------|------|
| **无**独立 `seller_sku` 列 | 账单是 **订单/结算行** 粒度 |
| 关联方式 | 用 `order_id` → `fact_tiktok_order` / `order_line` 再取 SKU |
| 件数 | `sales_qty` / `return_qty` 是账单件数，不是 SKU 编码 |

```sql
-- 账单件数 + 订单行 SKU（示例）
SELECT s.shop_name, s.order_id, s.sales_qty,
       l.seller_sku, l.sku_id, l.quantity AS line_qty
FROM tk.fact_sellfox_tk_statement s
LEFT JOIN tk.fact_tiktok_order_line l
  ON l.shop_external_id = s.shop_external_id
 AND l.order_id = s.order_id
WHERE s.statement_date >= CURRENT_DATE - 7
LIMIT 50;
```

---

### 3.6 异常任务 · `tk.fact_tk_anomaly_task`

| 字段 | 含义 |
|------|------|
| `product_id` | TK 商品 ID（飞书「ASIN」列在 TK 侧填这个） |
| `seller_sku` | 卖家 SKU → 飞书列 **「SKU」** |
| `object_ref` | 活动/店铺级异常时的对象引用 |
| `object_type` | product / campaign / shop / order / other |

**来源：** 规则引擎（如商品断货从 `fact_tiktok_product` 带出 `seller_sku`）、人工建单、Ingest `tiktok_anomaly_task`。  
**同步：** 飞书 TK 异常任务表，列名「SKU」= `seller_sku`。

---

### 3.7 内容日 · `tk.fact_tiktok_content_daily`（注意：不是 SKU 编码）

| 字段 | 含义 | 是否 SKU 编码 |
|------|------|----------------|
| `attributed_sku_orders` | 内容归因 **SKU 订单数**（后台「视频归因 SKU 订单」） | ❌ 是**数量** |
| `attributed_units` | 内容归因件数 | ❌ 数量 |
| `product_id` | 关联商品 ID（有则填） | 商品 ID，非 seller_sku |

**来源：** `scrape-content-overview-page.js` / 视频列表等 → Ingest 内容源。  
**勿把** `attributed_sku_orders` 当成 SKU 字符串字段。

---

### 3.8 亚马逊 · `fact_amz_link_daily`（对照，非 TK）

| 字段 | 含义 |
|------|------|
| `asin` | 亚马逊 ASIN（优先业务键） |
| `seller_sku` | 卖家 SKU；**无 ASIN 时** `biz_key = 'sku:' \|\| seller_sku` |
| `biz_key` | 生成列：`asin:…` 或 `sku:…` |

**来源：** 赛狐/AMZ 链接日 Ingest（`amz_link_daily` 等）。  
**约束：** ASIN 与 seller_sku 至少一个非空。

---

### 3.9 其它相关（弱 SKU / 非编码）

| 表/位置 | 字段 | 说明 |
|---------|------|------|
| `tk.fact_tiktok_shop_daily` | （无 seller_sku） | 店日 KPI；后台文案「SKU 订单数」进的是 **`orders_cnt` 类订单量**，不是 SKU 码 |
| `tk.fact_tiktok_product_traffic_daily` | 流量指标 | 商品×日；SKU 编码仍回 product 表 |
| `product_platform_ref`（字典规划） | `seller_sku` / `commodity_sku` | 中台产品映射；以实表为准 |
| 飞书补货备忘 | 手工「SKU」列 | 人工填写，不接同步 |

---

## 4. 端到端数据流（一张图）

```text
┌───────────────────── TK Seller（紫鸟浏览器）─────────────────────┐
│ 商品列表 scrape-products-page.js                                 │
│   → sellerSku / sellerSkus[]  → Ingest tiktok_products           │
│   → fact_tiktok_product.seller_sku (+ raw_extra.seller_skus)     │
│                                                                  │
│ 订单列表 scrape-orders-page.js                                   │
│   → 订单头（SKU 常空）→ fact_tiktok_order                        │
│                                                                  │
│ 订单详情 scrape-order-detail-page.js                             │
│   → 行 sellerSku + skuId → Ingest tiktok_order_lines             │
│   → fact_tiktok_order_line 且 COALESCE 回填订单头 SKU             │
│                                                                  │
│ 内容页 → attributed_sku_orders（数量）→ fact_tiktok_content_daily│
└──────────────────────────────────────────────────────────────────┘

┌───────────────────── 赛狐 OpenAPI ───────────────────────────────┐
│ getParentPageList + getChildInfo                                 │
│   msku / commoditySku / skuId → fact_tiktok_product              │
│   （颜色 msku 过滤；不覆盖已有 scrape seller_sku）                 │
│                                                                  │
│ tkReport queryPageSku / queryPageMsku                            │
│   → fact_sellfox_tk_profit_sku (grain=sku|msku)                  │
│                                                                  │
│ queryStatementDetail → fact_sellfox_tk_statement（无 SKU 列）     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. 口径与对接约定（避免同事对不上）

| # | 约定 |
|---|------|
| 1 | **对外默认「SKU」= `seller_sku`（卖家/商家编码）**；平台数字 ID 请明确说 `sku_id` |
| 2 | 商品表是 **链接级**；多规格在 `seller_sku` 的 `\|` 或 `raw_extra.seller_skus`，不要假定一行一规格 |
| 3 | 订单 **明细以 order_line 为准**；订单头 SKU 可能空或仅首行 |
| 4 | 赛狐 `grain=sku` 与 `grain=msku` **禁止加总混用** |
| 5 | 赛狐 `msku` ≠ 永远等于干净 seller_sku（颜色脏值已过滤，历史脏数据见清理脚本） |
| 6 | `attributed_sku_orders` 是 **订单数指标**，不是 SKU 列表 |
| 7 | 紫鸟 storeId 与赛狐 shopId **两套 ID**，关联店铺用 `shop.external_shop_id` + `meta` |
| 8 | 写入普遍 `COALESCE`：后到的空值 **不会** 抹掉先到的 SKU |
| 9 | UI 噪声（「N 个 SKU 展开」）在采集端 + Ingest 双端拒绝，入库不应再出现 |
| 10 | SHOP INOUT 前台订单若未采齐，该店订单 SKU 覆盖会偏低 → 商品/赛狐侧补 |

---

## 6. 给飞书 / 报表 / 开发的取数建议

| 诉求 | 主表 | 主字段 | 备注 |
|------|------|--------|------|
| 链接维度卖家 SKU | `tk.fact_tiktok_product` | `seller_sku` | 多规格看 `raw_extra.seller_skus` |
| 订单每个规格 | `tk.fact_tiktok_order_line` | `seller_sku`, `sku_id`, `quantity` | 履约/客服 |
| 订单头快速字段 | `tk.fact_tiktok_order` | `seller_sku`, `sku_id` | 可能不全 |
| SKU 区间利润 | `tk.fact_sellfox_tk_profit_sku` | `msku_list`/`sku_list`, `sales_qty`, `gross_profit` | 注意 grain + 店覆盖 |
| 异常任务 SKU 列 | `tk.fact_tk_anomaly_task` | `seller_sku` | 飞书同步 |
| 内容带货「SKU 订单」 | `tk.fact_tiktok_content_daily` | `attributed_sku_orders` | 数量 |
| 账单对账后再看 SKU | statement ⋈ order_line | `order_id` 关联 | statement 本身无 SKU 列 |
| 亚马逊链接 SKU | `fact_amz_link_daily` | `seller_sku` | ASIN 优先 |

**Ingest source 速查：**

| source | 目标表 | SKU 相关 |
|--------|--------|----------|
| `tiktok_products` | `fact_tiktok_product` | `seller_sku` / `seller_skus` |
| `tiktok_orders` | `fact_tiktok_order` | 头 `seller_sku`/`sku_id`（常空） |
| `tiktok_order_lines` | `fact_tiktok_order_line` + 回填头 | 行级完整 |
| `tiktok_anomaly_task` | `fact_tk_anomaly_task` | `seller_sku` |
| 赛狐 Job（非 ingest） | product / profit_sku / statement | 见 §3.1 / 3.4 / 3.5 |

---

## 7. 补数与运维入口

| 动作 | 怎么做 |
|------|--------|
| 赛狐商品+利润+账单同步 | 服务器：`python -m app.jobs.tk_sellfox_sync --days 30` 或 `scripts/server-run-sellfox-tk-sync.sh` |
| 缺订单 SKU 批量补详情 | `collectors/tiktok-ads/scripts/fill-order-skus.ps1`（读 missing CSV） |
| 缺商品 SKU 补抓 | `fill-product-skus.ps1` / 商品列表重采 + 赛狐 products 模块 |
| 颜色脏 seller_sku 清理 | `scripts/_cleanup_colorish_product_sku.sql` |
| 覆盖率自查 | `scripts/_tmp_sku_coverage.sql` |
| 进生产库 | `ssh …` → `docker exec -it qingquan-db-1 psql -U qingquan -d qingquan`（DB 不公网） |

```sql
-- 一键覆盖率（可直接跑）
SELECT 'product' AS src, shop_name,
       count(*) AS n,
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '') AS with_sku
FROM tk.fact_tiktok_product GROUP BY 2
UNION ALL
SELECT 'order_head', shop_name,
       count(*),
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '')
FROM tk.fact_tiktok_order GROUP BY 2
UNION ALL
SELECT 'order_line', shop_name,
       count(*),
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '')
FROM tk.fact_tiktok_order_line GROUP BY 2
ORDER BY 1, 2;
```

---

## 8. 已知缺口 / 历史坑（交接必读）

1. **订单列表无 SKU** → 必须详情页 / `order_line`；历史上有大量订单头空 SKU，靠 `fill-order-skus` 回填。  
2. **商品列表「N 个 SKU 展开」** 曾误入库为 `product_id/name`，已在 scrape + ingest 双端拦截。  
3. **赛狐 msku 颜色污染**（`Black`、`Pink`…）曾写入 `seller_sku`，已加 `_is_colorish_sku` + SQL 清理；纯字母短码与合法无数字编码需区分。  
4. **多规格 `\|` 拼接** 检索时记得 `LIKE` 或 `unnest(string_to_array(seller_sku,'\|'))`，不要只 `= '单码'`。  
5. **利润 SKU 店覆盖不全**（主要 Gardena）→ 三店 SKU 动销件数不要只信 profit_sku。  
6. **SHOP INOUT 前台订单** 采集若未齐，该店 order/line SKU 覆盖偏低。  
7. **赛狐不同步广告/内容**；内容侧只有归因数量，没有内容级 seller_sku 主数据。  
8. `product_id` 兜底前缀：`sku:` / `name:` 出现时说明页面没抽到平台商品 ID，关联要小心。

---

## 9. 字段别名速查（采集 payload ↔ PG）

| 业务说法 | payload 常见键 | PG 列 / JSON 路径 |
|----------|----------------|-------------------|
| 商家/卖家 SKU | `seller_sku`, `sellerSku`, `sku` | `seller_sku` |
| 多规格列表 | `seller_skus`, `sellerSkus` | `raw_extra.seller_skus` |
| 平台 SKU ID | `sku_id`, `skuId` | `sku_id`；商品侧 `raw_extra.sku_ids` |
| 赛狐 MSKU | `msku` | → 清洗后 `seller_sku`；原始 `raw_extra.raw_mskus` / children |
| 赛狐货品码 | `commoditySku`, `commodity_sku` | 回退 seller_sku；`raw_extra.commodity_skus` |
| 利润 SKU 列表 | `skuList` / `mskuList` | `sku_list` / `msku_list` |
| 利润行键 | （拼接） | `sku_key` |
| 内容归因 SKU 订单 | `attributed_sku_orders` | 同名列（**数量**） |

---

## 10. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-08-07 | 首版：按迁移/采集/赛狐同步/ingest 整理全库 SKU 相关字段、来源、口径与对接约定 |
