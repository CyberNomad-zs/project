# TK 整站运营数据采集路线图

> 职责口径（已确认）：**抓取 TikTok Shop 后台对运营有用的整站数据**（不限广告），经紫鸟 → 清泉 PG（+ 按需飞书）。  
> 广告是第一域，不是终点。

更新：2026-08-03

---

## 1. 原则

| 原则 | 说明 |
|------|------|
| 一域一页一脚本 | 后台多菜单，禁止指望广告页抓全站 |
| 一域一事实表 | 订单不进 `fact_ads_campaign_daily` |
| 一域一 Ingest source | 如 `tiktok_ads` / `tiktok_orders` / `tiktok_products` |
| 只走紫鸟 | 禁止本机浏览器直连卖家后台；采集在 **Windows + Bridge**，中心 Linux 只收数 |
| 分期上线 | 每域：调研字段 → 脚本 → 迁移/Ingest → dual/飞书 → 稳定采集 |
| **广告日更归属** | **同事本机** Windows 计划任务已跑；中心不重建广告定时 |
| **非广告日更** | 采集机可装 shop-modules / orders / products 计划任务（见 `docs/每日定时任务.md`） |

---

## 2. 批次与状态

| 批次 | 域 | 菜单/入口（典型） | 事实表 / source | 状态 |
|------|-----|-------------------|-----------------|------|
| **P0** | 广告计划日指标 | 营销 → 店铺广告 | `tk.fact_ads_campaign_daily` / `tiktok_ads` | **已通**；同事本机 17:20 日更 |
| **P1** | 广告同页扩列 | 同上 | 同上 + P1 列 | **已通** |
| **P2a** | **订单** | 订单列表 | `tk.fact_tiktok_order` / `tiktok_orders` | **已通**；多页 + 粘连时间 + 店名主数据；可装 `TK-Orders-Daily` |
| **P2b** | 商品/库存 | `/product/manage` | `tk.fact_tiktok_product` / `tiktok_products` | **已通**；open+settle 无 visit；翻页；可装 `TK-Products-Daily` |
| **P2c** | 店级 KPI | **首页** `/homepage` | `tk.fact_tiktok_shop_daily` | **已通**；近 N 天卡片；全店日更 19:45 |
| **P3a** | 账号健康 | `/health-center` | `tk.fact_tiktok_health_daily` | **已通** |
| **P3b** | 财务摘要 | `/finance/bills` | `tk.fact_tiktok_finance_daily` | **已通** |
| **P4** | 联盟/达人、直播、促销… | UK:`affiliate.tiktok.com/insights/transaction-analysis`；EU:`affiliate.tiktokshopglobalselling.com/…`（经 seller landing CTA） | 另表 | 按需；**经营计划称 P3 达人表现**（编号勿混）。P3.1～P3.5+D4 已交；**日更包装** `run-affiliate-daily` / `TK-Affiliate-Daily` 可选装（2026-08-07）；POC 默认 SkipIngest；见 `docs/TK-P3-达人表现POC结论.md` |

---

## 3. 流水线形态

### 3.1 广告日更（已有 · 同事本机）

```text
TK-Ad-Daily-Report 17:20
  → run-daily-report.ps1 / run-multi-store.ps1
  → 飞书（按需）+ 清泉 ingest tiktok_ads
```

### 3.2 非广告日更（采集机可选）

```text
# 拆分（推荐错开）
19:45 TK-Shop-Modules-Daily  → shop/health/finance
20:00 TK-Orders-Daily        → orders
20:20 TK-Products-Daily      → products
20:40 TK-Content-Daily       → video_list + product_traffic（经营 P2；可选装）
20:55 TK-Affiliate-Daily     → enter_center + performance（经营 P3；可选装；含 Pop）

# 或合并一条（勿与拆分同时开）
19:50 TK-Full-Site-Daily     → shop → orders → products
              + 可选 -WithContent / -WithAffiliate

# 中心机（不抢紫鸟）
21:00 TK-P0-Post-Collect     → 规则(ads/product/shop/content/affiliate) + 飞书 T1/T2/T6/T7/异常
```

### 3.3 手工 / 夜循环

```text
run-orders.ps1 | run-products.ps1 | run-shop-modules.ps1
run-content-daily.ps1 | run-affiliate-daily.ps1   # 强制入库
night-loop.ps1   # Bridge 通时轮询 ads+shop+orders+products（内容/达人另任务）
```

---

## 4. 验收（摘要）

### 广告
- [x] dual ingest + 同事本机定时  

### 订单
- [x] 多页 + 幂等 UPSERT + 粘连时间  
- [x] `run-orders-daily` / install 脚本  

### 商品
- [x] productId 去重、价格、翻页、Bridge settle 轮询  
- [x] `run-products-daily` / install 脚本  

### KPI / 健康 / 财务
- [x] homepage / health-center / finance scrapers  
- [x] 全店 `TK-Shop-Modules-Daily`  

### 欧盟 Pop
- [x] **exclude 策略**：非广告模块用 `opsExcludeStoreIds` / `opsExcludePlatformContains`（默认 Pop + 欧盟）  
- [ ] 若广告也排除：写入 `filter.excludeStoreIds`（慎用）  

### 仍可选
- [ ] 商品 Bridge 再压测  
- [ ] P4 域按业务优先级  

进度见仓库根 `PROGRESS-tk-full-scrape.md`。
