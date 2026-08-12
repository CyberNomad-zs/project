# TK 销量相关字段说明 · 同事交接

> 快照日期：**2026-08-06**（生产 `qingquan-db-1` @ `43.156.50.38` 实查）  
> 用途：说明服务器 PostgreSQL 里 **TikTok「销量」** 有哪些表/字段、口径差异、怎么查、当前有没有数  
> 相关：
> - [TK-赛狐数据源对照.md](./TK-赛狐数据源对照.md)
> - [数据库现状说明.md](./数据库现状说明.md)
> - [字段映射字典.md](./字段映射字典.md)
> - [ops/SERVER.md](./ops/SERVER.md)
> - [ops/生产环境-同事交接.md](./ops/生产环境-同事交接.md)（含进库方式；**含机密，勿提交**）

---

## 0. 30 秒结论

| 问题 | 答案 |
|------|------|
| PG 里有没有销量字段？ | **有**，多张表、多种口径，**不要混用** |
| 商品累计销量看哪？ | `tk.fact_tiktok_product.sales_qty` |
| 三店财务件数（最全）看哪？ | `tk.fact_sellfox_tk_statement.sales_qty` |
| 利润报表件数看哪？ | `tk.fact_sellfox_tk_profit_shop/sku.sales_qty`（目前 API 主要只有 **Gardena**） |
| 前台订单件数看哪？ | `tk.fact_tiktok_order.quantity` / `order_line.quantity` |
| 店日「单量」看哪？ | `tk.fact_tiktok_shop_daily.orders_cnt`（是**订单数**，不是件数） |
| 广告带来的单？ | `tk.fact_ads_campaign_daily.orders`（广告归因订单，不是全店销量） |
| 内容归因件数？ | `tk.fact_tiktok_content_daily.attributed_units` |

**推荐用法（稳态）：**

```text
看板「商品累计卖了多少」     → fact_tiktok_product.sales_qty
对账「结算口径卖了多少件」   → fact_sellfox_tk_statement（可按日/店 SUM）
利润区间 SKU 销量            → fact_sellfox_tk_profit_sku（注意店覆盖）
运营「昨天下了多少单/GMV」   → fact_tiktok_shop_daily.orders_cnt / gmv
客服/履约「订单明细件数」    → fact_tiktok_order(.quantity) / order_line
广告 ROI 分母订单            → fact_ads_campaign_daily.orders
短视频带货件数               → fact_tiktok_content_daily.attributed_units
```

---

## 1. 三店主数据（查销量前先对齐店）

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

> 历史别名：紫鸟侧曾出现 `Tiktok_Shop2` / `Tiktok - KK Seagull` / `TikTok - Pop`，已映射到上表三店，**不要再按旧名写死**。

---

## 2. 字段清单（按表）

下列均以 **`tk` schema** 为准（`public` 下有同名镜像表时结构一致，生产查询优先 `tk.`）。

### 2.1 商品累计销量 · `tk.fact_tiktok_product`

| 字段 | 类型 | 含义 |
|------|------|------|
| `sales_qty` | numeric | **商品累计销量（件数）** |
| `stock_qty` | numeric | 库存（不是销量） |
| `product_id` | text | TK 商品 ID |
| `seller_sku` | text | 卖家 SKU |
| `raw_extra` | jsonb | 扩展；赛狐写入时 `source=sellfox` |
| `collected_at` | timestamptz | 采集/同步时间 |

**口径：** 商品维度的**累计**销量快照，不是自然日增量。  
**来源：** TK Seller 采集 ingest + 赛狐商品同步（`raw_extra->>'source' = 'sellfox'`）。  
**2026-08-06 生产有数：**

| 店 | 商品行 | 有 sales_qty | sales_qty>0 | 销量合计 |
|----|--------|--------------|-------------|----------|
| Deal to deal | 89 | 78 | 35 | 465 |
| Gardena | 95 | 19 | 12 | 30 |
| SHOP INOUT | 95 | 82 | 55 | 1,288 |

```sql
SELECT shop_name,
       count(*) AS n,
       count(*) FILTER (WHERE COALESCE(sales_qty, 0) > 0) AS gt0,
       sum(COALESCE(sales_qty, 0)) AS sales_sum
FROM tk.fact_tiktok_product
GROUP BY 1
ORDER BY 1;
```

---

### 2.2 赛狐利润 · 店铺区间 · `tk.fact_sellfox_tk_profit_shop`

| 字段 | 类型 | 含义 |
|------|------|------|
| `sales_qty` | numeric | 区间内销售件数 |
| `return_qty` | numeric | 区间内退货件数 |
| `gross_sales_amount` | numeric | 毛销售金额（GMV 口径之一） |
| `gross_sales_refund` | numeric | 退款金额 |
| `settlement_amount` | numeric | 结算金额 |
| `period_start` / `period_end` | date | **报表区间**（不是单日） |
| `sellfox_shop_id` | text | 赛狐数字店 ID |

**口径：** 赛狐「利润报表 · 按店铺」**整段区间汇总**，不是自然日 KPI。  
**注意（2026-08-06）：** 接口常只回 **1 行**，当前落库挂在 **Gardena**（`sales_qty=607`，区间约近 30 天）。Deal to deal / SHOP INOUT 的利润件数请改用 **statement** 或等赛狐按店拆行稳定后再信此表。

---

### 2.3 赛狐利润 · SKU/MSKU · `tk.fact_sellfox_tk_profit_sku`

| 字段 | 类型 | 含义 |
|------|------|------|
| `grain` | text | `sku` 或 `msku` |
| `sku_key` | text | 去重键 |
| `sales_qty` | numeric | 区间销售件数 |
| `return_qty` | numeric | 退货件数 |
| `gross_sales_amount` | numeric | 毛销售金额 |
| `period_start` / `period_end` | date | 报表区间 |

**口径：** 与店铺利润同一套区间；`grain=sku` 与 `grain=msku` 是**两套切片**，SUM 时不要混加。  
**2026-08-06：** 仅 Gardena，sku/msku 各 53 行，`sales_qty` 合计均为 **607**（与店铺层一致）。

```sql
SELECT shop_name, grain,
       count(*) AS n,
       sum(COALESCE(sales_qty, 0)) AS sales_sum,
       sum(COALESCE(gross_sales_amount, 0)) AS gmv
FROM tk.fact_sellfox_tk_profit_sku
GROUP BY 1, 2
ORDER BY 1, 2;
```

---

### 2.4 赛狐结算账单 · `tk.fact_sellfox_tk_statement`（三店件数最全）

| 字段 | 类型 | 含义 |
|------|------|------|
| `sales_qty` | numeric | 本条账单关联销售件数 |
| `return_qty` | numeric | 退货件数 |
| `gross_sales_amount` | numeric | 毛销售金额 |
| `settlement_amount` | numeric | 结算金额 |
| `order_id` | text | 平台订单号 |
| `statement_date` / 时间类 | date/tstz | 账单/结算时间维度 |
| `order_status` / `order_type` | text | 订单状态/类型 |

**口径：** **结算/账单流水**上的件数，适合财务对账与按日 rollup；**不是** Seller 后台实时「今日销量」。  
**2026-08-06 生产有数（三店齐全）：**

| 店 | 行数 | sales_qty>0 行 | 销量合计 | 退货合计 |
|----|------|----------------|----------|----------|
| Deal to deal | 211 | 199 | 206 | 7 |
| Gardena | 517 | 466 | 559 | 17 |
| SHOP INOUT | 1,485 | 1,322 | 1,425 | 68 |

```sql
-- 按店汇总件数
SELECT shop_name,
       count(*) AS n,
       sum(COALESCE(sales_qty, 0)) AS sales_sum,
       sum(COALESCE(return_qty, 0)) AS return_sum
FROM tk.fact_sellfox_tk_statement
GROUP BY 1
ORDER BY 1;

-- 按自然日（statement_date）看件数趋势
SELECT shop_name, statement_date,
       sum(COALESCE(sales_qty, 0)) AS sales_qty,
       sum(COALESCE(gross_sales_amount, 0)) AS gmv
FROM tk.fact_sellfox_tk_statement
WHERE statement_date >= CURRENT_DATE - 14
GROUP BY 1, 2
ORDER BY 1, 2;
```

账单还会 rollup 进：

- `tk.fact_tiktok_finance_daily`（金额为主：`settlement_amount` 等；`raw_extra->>'source' = 'sellfox'`）  
  → **财务日表本身没有 `sales_qty` 列**，件数请回 statement 或自行按日 SUM。

---

### 2.5 前台订单 · `tk.fact_tiktok_order` / `tk.fact_tiktok_order_line`

| 表 | 字段 | 含义 |
|----|------|------|
| `fact_tiktok_order` | `quantity` | 订单件数（头） |
| `fact_tiktok_order` | `pay_amount` | 实付金额 |
| `fact_tiktok_order` | `biz_date` / `pay_time` | 业务日 / 支付时间 |
| `fact_tiktok_order_line` | `quantity` | **行级件数** |
| `fact_tiktok_order_line` | `unit_price` | 单价 |

**口径：** TK 前台/Seller 订单采集，偏履约与明细；与赛狐结算件数**不必逐日相等**（时区、取消、结算滞后）。  
**2026-08-06：** Deal to deal、Gardena 有订单；**SHOP INOUT 订单采集未齐**（件数请用 statement / product）。

```sql
SELECT shop_name,
       count(*) AS orders,
       sum(COALESCE(quantity, 0)) AS qty,
       sum(COALESCE(pay_amount, 0)) AS pay
FROM tk.fact_tiktok_order
GROUP BY 1
ORDER BY 1;
```

---

### 2.6 店日 KPI · `tk.fact_tiktok_shop_daily`

| 字段 | 类型 | 含义 |
|------|------|------|
| `biz_date` | date | 业务日 |
| `orders_cnt` | numeric | **订单数**（不是件数） |
| `gmv` | numeric | 当日 GMV |
| `buyers_cnt` | numeric | 买家数 |
| `refund_amount` | numeric | 退款金额 |

**口径：** 店维度**自然日**经营快照；问「昨天几单 / 多少 GMV」用这张。  
**不要**把 `orders_cnt` 当成 `sales_qty`（一单可多件）。

---

### 2.7 商品流量日 · `tk.fact_tiktok_product_traffic_daily`

| 字段 | 含义 |
|------|------|
| `orders_cnt` | 商品日订单数（采集侧，可能为 0） |
| `gmv` | 商品日 GMV |

**口径：** 商品 × 日 流量/转化；当前生产 `orders_cnt` 常为 0，GMV 可能仍有值——**件数请优先 product / statement / order**。

---

### 2.8 广告日 · `tk.fact_ads_campaign_daily`

| 字段 | 含义 |
|------|------|
| `orders` | **广告归因订单数** |
| `revenue` | 广告归因收入 |
| `avg_order_cost` | 单均成本类指标 |

**口径：** 只覆盖投放带来的单，**不是全店销量**。

---

### 2.9 内容日 · `tk.fact_tiktok_content_daily`

| 字段 | 含义 |
|------|------|
| `attributed_units` | 内容归因**件数** |
| `attributed_sku_orders` | 内容归因 SKU 订单 |
| `attributed_gmv` | 内容归因 GMV |

**口径：** 视频/直播等内容归因，子集销量。

---

## 3. 口径对照（避免同事对不上数）

| 维度 | 商品 `sales_qty` | 赛狐 profit | 赛狐 statement | 订单 `quantity` | 店日 `orders_cnt` |
|------|------------------|-------------|----------------|-----------------|-------------------|
| 粒度 | 商品累计 | 店/SKU **区间** | 账单行 → 可按日 | 订单/行 | 店 × 自然日 |
| 度量 | 件数 | 件数 | 件数 | 件数 | **订单数** |
| 三店覆盖（08-06） | 有 | 主要 Gardena | **三店全** | 缺 SHOP INOUT | 视采集 |
| 适合 | 链接累计动销 | 利润分析 | 财务件数/对账 | 履约明细 | 经营日报 |
| 不适合 | 当自然日销量 | 当「今日销量」 | 当实时后台 | 直接当财务结算 | 当件数 |

**常见误解：**

1. `orders_cnt` ≠ `sales_qty`（单数 ≠ 件数）  
2. 商品累计销量 ≠ 近 30 天销量（累计快照 vs 区间）  
3. 赛狐利润区间 GMV ≠ 店日 GMV 简单加总（币种、退款、统计窗不同）  
4. 广告 `orders` / 内容 `attributed_units` 都是**归因子集**  
5. `fact_tiktok_finance_daily` 有金额、**无件数列**

---

## 4. 数据从哪来 / 怎么再同步

| 数据 | 路径 | 备注 |
|------|------|------|
| 商品/订单/店日/广告/内容 | `collectors/tiktok-ads` → Ingest API → `tk.fact_*` | 广告/内容/健康**只能**走这条 |
| 赛狐商品+利润+账单 | `python -m app.jobs.tk_sellfox_sync --days 30` | 服务器 api 容器；密钥 `SELLFOX_*` |
| 一键脚本 | `scripts/server-run-sellfox-tk-sync.sh` | 迁移 018 + docker cp 代码 + 跑同步 |
| 迁移 | `backend/migrations/018_tk_sellfox_facts.sql` | sellfox 利润/账单/sync_run 表 |
| 同步流水 | `tk.sellfox_sync_run` | `status/stats/error_message` |

进生产库（服务器上）：

```bash
ssh -i keys/qingquan_sg_ed25519 ubuntu@43.156.50.38
docker exec -it qingquan-db-1 psql -U qingquan -d qingquan
```

本机管道示例（PowerShell）：

```powershell
$key = "E:\project\清泉跨境系统（企业级）\keys\qingquan_sg_ed25519"
@"
SELECT shop_name, sum(sales_qty) FROM tk.fact_sellfox_tk_statement GROUP BY 1;
"@ | ssh -i $key ubuntu@43.156.50.38 "docker exec -i qingquan-db-1 psql -U qingquan -d qingquan"
```

> DB 仅服务器本机 `127.0.0.1:5432`，**不公网**。密码见服务器 `/opt/qingquan/.env`，本文不写明文。

---

## 5. 给飞书 / 报表同事的取数建议

| 报表诉求 | 建议 SQL 主表 | 主字段 |
|----------|---------------|--------|
| 链接累计销量 TopN | `tk.fact_tiktok_product` | `sales_qty` |
| 近 N 日三店销售件数 | `tk.fact_sellfox_tk_statement` | `sum(sales_qty)` + `statement_date` |
| 近 N 日三店 GMV/结算 | statement 或 `fact_tiktok_finance_daily` | `gross_sales_amount` / `settlement_amount` |
| 昨日店铺单量/GMV | `tk.fact_tiktok_shop_daily` | `orders_cnt`, `gmv` |
| SKU 利润与销量 | `tk.fact_sellfox_tk_profit_sku` | `sales_qty`, `gross_profit`（注意店覆盖） |
| 广告花费与出单 | `tk.fact_ads_campaign_daily` | `spend`, `orders`, `revenue` |

---

## 6. 已知缺口（交接时一并说明）

1. **赛狐利润按店**：接口常返回单行汇总，目前可靠利润件数主要在 **Gardena**；另外两店用 **statement**。  
2. **SHOP INOUT 前台订单**采集未齐 → 不要用 `fact_tiktok_order` 代表该店全量件数。  
3. **`product_traffic_daily.orders_cnt`** 生产多为 0，勿单独当销量源。  
4. 赛狐同步代码若只 `docker cp` 进容器，**重建 api 镜像后需重部署**或走 `server-run-sellfox-tk-sync.sh`。  
5. 日更 cron：若尚未挂 worker/定时，件数会停在最近一次手动同步窗口（账单默认近 30 天）。  
6. 赛狐 **不提供** 广告/内容/健康分；那些仍只在 TK 采集链路。

---

## 7. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-08-06 | 首版：按生产实查整理销量字段、口径、样例 SQL 与三店覆盖情况 |
