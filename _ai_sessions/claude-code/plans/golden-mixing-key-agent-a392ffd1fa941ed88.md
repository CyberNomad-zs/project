# TK XMind Dashboard Module x Current Capability Gap Matrix

> Read-only inventory · 2026-08-04
> Inputs: `_xmind_tk_dash_new/outline.md` + `docs/TK-飞书驾驶舱*.md` + `docs/TK-AI素材分级-数据链路评估.md` + migrations/collectors/web
> Legend: DONE = usable · PARTIAL = skeleton/empty data · MISSING = absent

---

## 0. XMind module tree (design source)

Source: `E:\project\清泉跨境系统（企业级）\_xmind_tk_dash_new\outline.md`

| # | Module | Sub-areas | Core metrics |
|---|--------|-----------|--------------|
| M1 | Shop top-level data | KPI cards / trends / structure mix / product rank | Total GMV, orders, buyers, AOV, refund amt/rate; channel GMV mix (product card / short video / live / affiliate); daily GMV·orders 7/30d; hourly GMV; product GMV rank |
| M2 | TK patrol anomalies | Product-card traffic-conv / ads / affiliate | Exposure crash, CTR drop, conv crash, delist, violation; spend spike/drop, CTR drop, low ROI, ad review block; affiliate GMV drop, active creators drop, commission spike, video throttle, sample fulfillment |
| M3 | Content channel board (TAB) | Product-card channel / own short video | Exposure·click·GMV·orders·CVR; plays·product exposure·attributed GMV·SKU orders·watch CVR |
| M4 | Affiliate creator zone (TAB) | Summary / creator rank | Creator GMV, units, est. commission, active creators; collab-type mix; creator GMV/ROI/commission |
| (side) | AI creative grade S/A/B/C/D | Item/creative | Not in main XMind tree; Feishu empty shell exists |

Current Feishu plan is **AMZ XMind modules 2/3 TK-mapped** (multi-shop + ads). It only **partially overlaps** this TK XMind four-module tree.

---

## 1. Gap Matrix (main)

| Module | XMind metrics | PG | Collector | Feishu | Console (web) | Priority suggestion |
|--------|---------------|----|-----------|--------|---------------|---------------------|
| **M1a Shop core KPI cards** | GMV, orders, buyers, AOV, refund amt, refund rate | PARTIAL `tk.fact_tiktok_shop_daily` has gmv/orders/buyers/refund_amount; **no refund_rate col** (derivable); AOV can be precomputed on sync | PARTIAL `scrape-shop-daily-page.js` + `run-shop-modules` **built**; Feishu docs once reported shop_daily=0 (needs daily run) | PARTIAL T1 `店铺日经营` fields OK (sales/orders/buyers/refund/AOV); **D1 dashboard UI incomplete / components need rebind** | PARTIAL `tk-overview` nav placeholder, not full KPI cockpit | **P0**: fill shop_daily + daily sync, rebind D1 number cards |
| **M1b Channel GMV mix** | Product card / short video / live / affiliate | MISSING no channel breakdown table/cols | MISSING no content-analysis/channel collector (roadmap **P4 on-demand**) | MISSING T1 has no channel cols; ring chart has no source | MISSING | **P2**: needs M3 content collector before T1 extend or channel-daily table |
| **M1c Trend 7/30d** | Daily GMV, order volume | PARTIAL shop_daily by day is enough | PARTIAL same; needs continuous daily | PARTIAL T1 can bind line; D1 line component pending UI | PARTIAL no dedicated trend page | **P0**: same path as M1a once data is continuous |
| **M1d Hourly GMV** | Merchant-center hourly curve | MISSING no hour-grain table | MISSING no hourly scrape | MISSING | MISSING | **P3/later**: high cost, lower than daily MVP |
| **M1e Structure ring** | GMV source split (same as M1b) | MISSING | MISSING | MISSING | MISSING | **P2** = M1b |
| **M1f Product GMV rank** | Shop product GMV leaderboard | PARTIAL `tk.fact_tiktok_product` has sales_qty/price, **no daily GMV, no exposure/click**; snapshot not daily series | PARTIAL products list OK (manage page), **not product-analytics page** | PARTIAL plan T3 product table **not synced** yet; no rank view | MISSING no product rank | **P1**: products→T3 sync for sales/stock rank first; true GMV/traffic rank needs analytics collector |
| **M2a Product-card traffic-conv anomaly** | Exposure crash, CTR drop, conv crash, delist, violation | PARTIAL task shell `fact_tk_anomaly_task` + dict has product_delist/sales_drop/...; **no exposure/CTR/conv facts**; rules only **stock** stockout/low | PARTIAL products have status/stock; **no product-analytics / content GMV-split scrape** | PARTIAL anomaly task table synced (~19 rows); **no traffic-class anomaly data** | PARTIAL `tk-tasks` R/W anomaly task | **P1**: delist/zero-sales rules first (have source); traffic class **P2 after M3 collector** |
| **M2b Ads delivery anomaly** | Spend spike/drop, CTR drop, low ROI, review block | PARTIAL `fact_ads_campaign_daily`: spend/orders/roi/revenue/budget/CPA/status; **no CTR/impression/click**; dict 5 ads_*; rules implement **roi_low + spend_no_sale** (budget/cpa/plan in dict, rules not all on) | DONE ads plugin daily OK (colleague PC) | DONE T2 campaign daily + P/L tag/low-ROI views; can bind anomaly tasks | PARTIAL `tk-ads` has spend/ROI list-level | **P0**: add budget_burn/plan rules + D2 rebind; CTR/review **P2** (ads page extra cols or creative grain) |
| **M2c Affiliate anomaly** | Affiliate GMV drop, active creators drop, commission spike, throttle, sample fulfillment | MISSING no affiliate fact; dict **no affiliate_*** codes | MISSING no affiliate-center collector (P4) | MISSING no affiliate anomaly type/table | MISSING | **P2**: whole new domain; see dependency chain |
| **M3a Product-card channel board** | Exposure, click, GMV, orders, CVR; bar/funnel | MISSING no content/product_analytics daily | MISSING merchant "content analysis / product analytics" not built | MISSING no T_content | MISSING no TAB | **P2**: new collector → new schema → then Feishu TAB (**do not create empty tables first**) |
| **M3b Own short-video board** | Plays, product exposure, attributed GMV, SKU orders, watch CVR; video rank | MISSING no video/item fact (same gap as AI creative) | MISSING no short-video/item report scrape | PARTIAL Feishu `AI广告智能筛选分析表` empty ~6 rows, **not PG SoT** | MISSING | **P2/P3**: merge evaluation with AI creative/item collection |
| **M4a Affiliate summary** | Total GMV, units, commission, active creators; collab-type ring; 7d trend | MISSING | MISSING affiliate center analytics | MISSING | MISSING | **P2** same domain as M2c/M4b |
| **M4b Creator detail rank** | Creator GMV, ROI, commission; rank/bar | MISSING | MISSING | MISSING | MISSING | **P2** |
| **Side D3 AI creative S/A/B/C/D** | Grade, CPA, orders, human review | MISSING explicitly deferred (eval doc) | MISSING campaign-level has no item_id | PARTIAL standalone table `tblYpFKSJyIimUZ3` empty; **do not bind to D1/D2** | MISSING | **Later**: centralize only after item scrape or stable AI batch |

---

## 2. Current base (not XMind-primary but related)

| Capability | PG | Collector | Feishu | Console | vs XMind |
|------------|----|-----------|--------|---------|----------|
| Multi-shop daily wide T1 | shop_daily + ads rollup + health/finance join | shop-modules / ads | T1 `tblwh7EVeAFPfvuy` | weak tk-overview | **Covers M1a/M1c core**; not channel/hourly/product GMV rank |
| Ads campaign daily T2 | fact_ads_campaign_daily | ads plugin | T2 `tblXaQ871ZcrrTPL` | tk-ads | **Covers M2b ops + partial anomaly**; not content/affiliate |
| Anomaly tasks | fact_tk_anomaly_task + dim | ads/product rule jobs | `tblstt4IVNJihCd3` | tk-tasks | **Covers M2 collab shell**; metric sources incomplete |
| Orders | fact_tiktok_order | orders | not on cockpit tables | — | order structure only |
| Product snapshot | fact_tiktok_product | products | T3 not live | — | partial M1f/M2a |
| Health/finance | health_daily / finance_daily | shop-modules | folded into T1 cols | — | useful for patrol/boss; not separate XMind node |
| Organic vs ads (est.) | T1 extended-col logic | — | planned, approximate | — | **weak proxy** for channel mix; not content analysis |

Feishu Base: `C1iHbw6TVad6rUsbZnbc2gSDnHg`  
Sync `table_key`: `tk_shop_daily` / `tk_ads_campaign` / `tk_anomaly_task` (no content/affiliate/creative)

---

## 3. Dependency chains (collector before schema)

```text
[BLOCKED] M3 content channel board
  1) Survey merchant "content analysis / product analytics" fields + URLs
  2) New scraper (one domain one script) + ingest source (e.g. tiktok_content_daily)
  3) PG: tk.fact_tiktok_content_channel_daily (shop×day×channel or shop×product×day)
  4) Rules: exposure crash / CTR / conv (M2a traffic class)
  5) Feishu T_content + dashboard TAB
  6) Console TAB (optional; Feishu first)

[BLOCKED] M4 / M2c affiliate
  1) Survey affiliate center analytics-performance
  2) scraper + ingest tiktok_affiliate_*
  3) PG: creator daily summary + creator×shop detail (+ samples if needed)
  4) anomaly codes affiliate_* + rule job
  5) Feishu affiliate tables + zone page
  * Empty PG/Feishu without collector = same lesson as AI creative shell

[BLOCKED] M1b/M1e channel GMV ring
  -> depends on M3 (or multi-source rollup live+video+affiliate into shop-day)

[BLOCKED] M1d hourly GMV
  -> independent hour-level scrape; does not block daily MVP

[BLOCKED] M3b short video / AI creative
  -> stable item-level spend/plays? AI owner? human-review SoT?
  -> see docs/TK-AI素材分级-数据链路评估.md §4.4

[UNBLOCKED - do now]
  M1a/M1c: shop-modules daily run -> T1 real GMV (drop ads fallback) -> D1 rebind
  M2b: finish ads rules + D2 rebind + anomaly views
  M2a stock/delist: product stock* rules exist; add delist/zero_sales
  M1f weak: products -> Feishu T3 sales/stock rank (not traffic GMV rank)
```

---

## 4. Coverage summary

| Layer | DONE | PARTIAL | MISSING |
|-------|------|---------|---------|
| **XMind 4 modules** | — | M1 shop KPI/trend; M2 ads anomaly + task shell + stock | M1 channel/hourly/true product GMV rank; M2 traffic + affiliate anomaly; **entire M3, M4** |
| **PG tables** | ads / order / product / shop_daily / health / finance / anomaly_task | product no traffic cols; shop no channel | content / video / affiliate / creative / hourly |
| **Collector** | ads, orders, products, shop, health, finance | products ≠ product analytics | content analysis, short video, live, affiliate, hourly, item ads |
| **Feishu** | T1, T2, anomaly task schema+sync | D1/D2 UI rebind in progress; T1 was ads-fallback | T3 products, content TAB, affiliate zone, channel ring; AI table shell |
| **Console** | tk-ads / tk-tasks / tk-overview nav | not XMind-grade cockpit | content TAB, affiliate zone, channel structure |

**Rough:** ~**25–30%** of XMind metrics can be supported **directly or approximately** by T1+T2+anomaly tasks; **content + affiliate + channel structure ≈ 0%**.

---

## 5. Suggested priority order (not a build checklist)

| Order | Item | Why |
|-------|------|-----|
| **P0** | shop_daily daily fill + T1 real GMV; D1/D2 Feishu rebind; anomaly task widgets | Unlocks XMind M1 core cards/trends + M2b display; zero new collectors |
| **P0** | Ads rules budget_burn etc.; ROI cards must not average ROI column | Documented口径 |
| **P1** | Product T3 sync + product_delist/zero_sales rules | Weak M1f + non-traffic M2a |
| **P1** | shop_gmv_drop / health rules (table+dict exist) | Shop-level patrol |
| **P2** | **Content-analysis collector → schema → M3 + M2a traffic + M1 channel ring** | Largest XMind differentiator; one collector feeds many modules |
| **P2** | **Affiliate-center collector → M4 + M2c** | Second largest gap; can survey in parallel, ship serially |
| **P3** | Hourly GMV; short-video/AI creative centralization; live | Heavier deps or unproven ROI |

---

## 6. File anchors (absolute paths)

| Use | Path |
|-----|------|
| XMind outline | `E:\project\清泉跨境系统（企业级）\_xmind_tk_dash_new\outline.md` |
| Feishu schema (T1/T2, AMZ 2/3 map) | `E:\project\清泉跨境系统（企业级）\docs\TK-飞书驾驶舱建表方案.md` |
| Dashboard build / row counts | `E:\project\清泉跨境系统（企业级）\docs\TK-飞书驾驶舱仪表盘搭法.md` |
| Rebind + AI table boundary | `E:\project\清泉跨境系统（企业级）\docs\TK-飞书驾驶舱-仪表盘重绑清单.md` |
| AI creative eval | `E:\project\清泉跨境系统（企业级）\docs\TK-AI素材分级-数据链路评估.md` |
| Collector roadmap P0–P4 | `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\docs\TK-整站运营数据采集路线图.md` |
| PG tk tables | `E:\project\清泉跨境系统（企业级）\backend\migrations\007_*.sql` … `011_*.sql` |
| Console TK nav | `E:\project\清泉跨境系统（企业级）\web\src\App.vue` (tiktok: tk-overview/ads/report/tasks) |

---

## 7. One-line conclusion

Current PG + collectors + Feishu already support **"shop-day ops + ads campaigns + stock/ads anomaly tasks"** (≈ Feishu plan modules 2/3). Against the new TK XMind, **content-channel TAB, affiliate zone, channel GMV structure, and traffic-class patrol** are **whole-domain gaps** — each needs **new collector before schema/Feishu**, not empty tables first.

Read-only gap only; **no code changes**. If building next: clear P0→P1 display debt, then open P2 content-analysis domain survey.
