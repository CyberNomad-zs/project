# Research: 三平台汇总 / Cross-platform SKU / Unified Product

Read-only search of `E:\project\清泉跨境系统（企业级）` (docs/, backend/, web/, xmind extracts, goal drafts).  
Date of scan: 2026-08-05.

---

## Executive verdict

| Question | Answer |
|----------|--------|
| 三平台「数据汇总」需求文档？ | **有**，但是 **三套独立能力的历史盘点**，不是「跨平台 SKU 统一汇总」PRD |
| 跨平台统一商品/SKU 中心表？ | **未实现**。仅有字典草案 `product_platform_ref`；无 migration/API |
| AMZ ASIN vs SKU 建模？ | **已实现**：`fact_amz_link_daily` 双字段 + 生成列 `biz_key`（asin 优先，否则 sku） |
| 同事向多平台 API/导出？ | **部分**：店铺主数据、任务、Ingest、飞书 export 按平台分表；**无**统一 product/SKU API 或 CSV 导出 |

**一句话：** 仓库把「三平台」做成 **公共任务/店铺中枢 + 分平台事实表**；**没有**「内部货号/统一商品 → 多平台 ASIN/product_id/seller_sku」的落地主数据。

---

## 1. Docs / WIP describing 三平台 data summary

### 1.1 Primary: 三平台项目需求与问题汇总

- `E:\project\清泉跨境系统（企业级）\docs\三平台项目需求与问题汇总.md`
- Mirror: `归档\三平台项目需求与问题汇总.md`

**What it is:** 整理自三套独立旧项目（Temu / TikTok 广告 / 海外仓），对照表 + 迁入清泉的关系说明。

**What it is NOT:** 跨平台商品/SKU 汇总、统一货号、cross-listing 映射 PRD。

| 平台线 | 焦点 | 产出 |
|--------|------|------|
| Temu | 在售/限流/下架 | 飞书点名告警 |
| TikTok | 广告 5 字段 + 多店日报 | 飞书表 + Markdown 日报 |
| 海外仓 | 赛狐→WMS 发货闭环（服务 Temu 三店） | 自动下单/回传 |

关键摘录（与清泉关系）：本企业级仓库统一承接 collectors + 中心 API/任务引擎/飞书/店铺管理。

### 1.2 Architecture / 中台

| File | Relevance |
|------|-----------|
| `docs\架构方案.md` | 目标汇总 TK/Temu/AMZ；应用层列出「产品中心」但无表结构 |
| `docs\中台产品蓝图.md` | 老板驾驶舱；平台分域；横切统一 task，非统一商品 |
| `docs\字段映射字典.md` | **唯一** 写了 `product_platform_ref` 产品映射草案 |
| `docs\Phase0-实施计划.md` | 「三平台完整监控规则」不在 Phase0 |
| `docs\会议纪要-技术会.md` | AMZ 去重 = 同一 ASIN + 同一异常 |
| `docs\数据库现状说明.md` | public = 中心+AMZ；tk = TK 事实；无 product 中心表 |
| `docs\schema-tk-temu.md` | schema 分区：public / tk / temu(预留) |

### 1.3 Specs / goal drafts

| File | Meaning of「三平台」 |
|------|---------------------|
| `_goal_draft.txt` / `docs\specs\GOAL-ops-knowledge-ab.txt` | 三平台各 1 类异常骨架 |
| `docs\specs\INTENT-qingquan-platform.md` | 三平台汇总仅参考；不做完整跨境 ERP |
| `docs\specs\RESEARCH-qingquan-work-data.md` | 要「人与过程中台」，主动避开货品全家桶 |
| `docs\specs\SPEC-qingquan-work-os.md` / ARCHITECTURE | Case/Event 工作 OS |

### 1.4 XMind extracts

| Path | Content |
|------|---------|
| `_xmind_amz_extract\out\content.json` | AMZ 驾驶舱 SKU 筛选/滞销/断货/导出——单平台 |
| `_xmind_tk_dash_new\outline.md` | TK 仪表盘；「异常 ASIN」套用 AMZ 用语 |
| `技术会.xmind` → 会议纪要 | ASIN 级任务去重 |
| `中台.xmind` → 中台产品蓝图 | 组织/驾驶舱 |

---

## 2. Unified / center tables (public) for products/SKU

### 2.1 Designed but NOT built

`docs\字段映射字典.md` section 3 `product_platform_ref`:
- product_id (内部产品), platform, shop_id
- asin (AMZ), seller_sku / commodity_sku (赛狐/仓)
- parent_id / spu_id / product_id_ext, skc_id, goods_id (Temu), title

No CREATE TABLE in migrations. No API/domain code. `货号` essentially absent repo-wide.

### 2.2 What public actually has

**public:** org_*, shop, ingest_raw, anomaly_event, task*, sync_feishu_*, outbox, collector_node, audit_log, fact_amz_link_daily, amz_mom_*, listing_owner, fact_amz_shop_daily, fact_amz_risk_alert, KB tables, VIEW→tk.*

**tk:** fact_tiktok_product/order/ads/shop/health/finance, product_traffic, content, fact_tk_anomaly_task

**temu:** documented, not created in env snapshots

### 2.3 Closest identity layers

- Shop master: public.shop (cross-platform store only)
- AMZ: asin/seller_sku → biz_key
- listing_owner (multi-platform-capable, ASIN default)
- TK: shop + product_id
- task dedupe_key platform:biz_id:anomaly_type
- product_platform_ref: paper only

---

## 3. AMZ ASIN vs SKU model

`002_amz_mom_tasks.sql` fact_amz_link_daily:
- columns asin, seller_sku, parent_asin
- generated biz_key: asin preferred else sku:
- CHECK at least one of asin/sku
- UNIQUE (shop_external_id, biz_date, biz_key)

Task biz_id default ASIN; fallback seller_sku/commodity_id with biz_id_type.
dedupe: amazon:{biz_id}:{anomaly_type}
KB backfill joins fact_amz_link_daily WHERE asin = task.biz_id
listing_owner UNIQUE(platform, shop_id, biz_id_type, biz_id)
ingest amz_link_daily requires asin or seller_sku/sku
Feishu AMZ: ASIN/SKU columns; TK anomaly reuses ASIN column name for product_id

TK product fallback: product_id = sku:{seller_sku} or name:{title}

---

## 4. Colleague-facing API / export

Implemented:
- GET/POST /api/v1/shops (platform filter)
- GET/POST /api/v1/tasks (platform filter)
- /api/v1/kb/* (三骨架)
- POST /api/v1/ingest/{source}
- POST /api/v1/export/feishu table_keys: tasks|amz_*|tk_*
- /api/v1/tk/* ops and anomaly-tasks
- collectors heartbeat

Missing: /products, /sku, product-map, CSV multi-platform catalog

Colleague docs: docs\ops\生产环境-同事交接.md, SERVER.md, schema-tk-temu.md, openapi-v1.yaml

Web App.vue: multi-domain nav, no unified SKU UI

---

## 5. Absolute path index

Requirements:
- E:\project\清泉跨境系统（企业级）\docs\三平台项目需求与问题汇总.md
- E:\project\清泉跨境系统（企业级）\docs\架构方案.md
- E:\project\清泉跨境系统（企业级）\docs\中台产品蓝图.md
- E:\project\清泉跨境系统（企业级）\docs\字段映射字典.md
- E:\project\清泉跨境系统（企业级）\docs\AMZ环比异常-人维任务草案.md
- E:\project\清泉跨境系统（企业级）\docs\数据库现状说明.md
- E:\project\清泉跨境系统（企业级）\docs\schema-tk-temu.md
- E:\project\清泉跨境系统（企业级）\_goal_draft.txt
- E:\project\清泉跨境系统（企业级）\docs\specs\GOAL-ops-knowledge-ab.txt
- E:\project\清泉跨境系统（企业级）\docs\specs\INTENT-qingquan-platform.md
- E:\project\清泉跨境系统（企业级）\docs\specs\RESEARCH-qingquan-work-data.md
- E:\project\清泉跨境系统（企业级）\docs\specs\SPEC-qingquan-work-os.md
- E:\project\清泉跨境系统（企业级）\docs\specs\ARCHITECTURE-qingquan-work-os.md

Schema/code:
- E:\project\清泉跨境系统（企业级）\backend\migrations\001_init.sql
- E:\project\清泉跨境系统（企业级）\backend\migrations\002_amz_mom_tasks.sql
- E:\project\清泉跨境系统（企业级）\backend\migrations\006_tiktok_products.sql
- E:\project\清泉跨境系统（企业级）\backend\migrations\008_tk_schema.sql
- E:\project\清泉跨境系统（企业级）\backend\migrations\010_tk_anomaly_task.sql
- E:\project\清泉跨境系统（企业级）\backend\app\api\ingest.py
- E:\project\清泉跨境系统（企业级）\backend\app\api\export_feishu.py
- E:\project\清泉跨境系统（企业级）\backend\app\api\shops.py
- E:\project\清泉跨境系统（企业级）\backend\app\api\tasks.py
- E:\project\清泉跨境系统（企业级）\backend\app\api\tk_ops.py
- E:\project\清泉跨境系统（企业级）\backend\app\domain\kb.py
- E:\project\清泉跨境系统（企业级）\backend\app\adapters\feishu\bitable.py
- E:\project\清泉跨境系统（企业级）\backend\app\main.py

XMind:
- E:\project\清泉跨境系统（企业级）\_xmind_amz_extract\out\content.json
- E:\project\清泉跨境系统（企业级）\_xmind_tk_dash_new\outline.md

---

## 6. Gaps if building cross-platform SKU summary

1. No internal product / 货号 entity
2. No product_platform_ref migration/API
3. No join path AMZ ASIN ↔ TK product_id ↔ Temu goodsId except manual seller_sku coincidence
4. seller_sku never validated as global key
5. Specs deprioritize ERP product hub vs Case/work OS
6. Only paper design in 字段映射字典 + architecture one-liner 产品中心

## Plan status

Read-only research complete. No implementation in this pass.
