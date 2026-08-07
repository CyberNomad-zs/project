# TK P2 Content/Video — Frontend & Docs Exploration

Read-only survey of task-console TK pages and Feishu dashboard docs for adding **content/video (P2)**. No code changes.

---

## 1. Frontend: `web/src/App.vue` (monolith — only TK UI)

**Path:** `E:\project\清泉跨境系统（企业级）\web\src\App.vue`

There is **no** separate TK route/components tree; all TikTok console lives in this single SFC.

### Nav (TikTok domain children) — lines ~34–43

| Tab id | Label | Status vs P2 content |
|--------|--------|----------------------|
| `tk-overview` | 平台总览 | Has shop-daily + product ranking blocks |
| `tk-ads` | 广告投流 | Campaign list live |
| `tk-report` | 日报 / AI 简报 | Shell to AI brief |
| `tk-tasks` | 异常任务 | Filters shop/campaign/product only |
| *(missing)* | 内容/视频 | **No nav item** — P2.5 target |

### State / loaders (extension templates)

| Concern | Reactive | Loader | API |
|---------|----------|--------|-----|
| Anomaly list | `tkFilters` (+ `object_type`) | `loadTkTasks` | `GET /api/v1/tk/anomaly-tasks` |
| Ads | `tkAdsFilters` / `tkAdsItems` | `loadTkAds` | `GET /api/v1/tk/ads/campaigns` |
| Shop daily | `tkShopDaily*` | `loadTkShopDaily` | `GET /api/v1/tk/shop-daily` |
| Product rank | `tkProductRank*` | `loadTkProductRanking` | `GET /api/v1/tk/products/ranking` |
| Content list | **none** | **none** | **none** |

### Section structure (where to add content list)

1. **`tk-overview`** (`v-show="activeTab.endsWith('-overview')"` + `activePlatformKey === 'tiktok'`)
   - Shop-daily KPI cards + table
   - Product ranking TOP card
   - Platform shops + recent anomalies
   - **Extension:** third card after product ranking (content TOP / attributed GMV), same pattern as product rank; or quick-link button to new tab.

2. **`tk-ads`**
   - Campaign daily table + anomaly badges + eval actions
   - Not the home for organic content; P2 may later link creative to content.

3. **`tk-tasks`**
   - Domain filter UI (see section 4)
   - Eval buttons only for ads + product (no content eval)

4. **New tab (recommended for P2.5 full list)**
   - Add `{ id: 'tk-content', label: '内容 / 视频', ... }` under TikTok `children`
   - Mirror `tk-ads`: filters (`biz_date`, `shop_external_id`, `q`, page) + table + summary
   - Wire `switchTab` / `refreshActive` / `show*Actions` branches like `tk-ads` (~655-720, ~1280-1320)

### Label maps already half-ready

- `objectTypeLabel`: `campaign` to 广告, `product` to 库存, `shop` to 店铺分析 — **no content/video**
- `anomalyCodeLabel`: ads_* / product_stock* / shop_*gmv|order* only

---

## 2. Feishu docs — T4 / D3 naming collision (important)

### A. Original cockpit schema (MVP tables) — not P2 content

**Path:** `E:\project\清泉跨境系统（企业级）\docs\TK-飞书驾驶舱建表方案.md`

| Code | Meaning in this doc | P2 content? |
|------|---------------------|-------------|
| T1 | 店铺日经营 | No (exists) |
| T2 | 广告活动日明细 | No (exists) |
| T3 | 商品日/快照 | Product, not video |
| **T4** | **账号健康日** | **No** — health, mergeable into T1 |
| T5 | 财务结算日 | No |
| D1 | 多店对比 from T1 | |
| D2 | 广告投放 from T1+T2 | |
| **D3** | **商品（后） from T3** | **Product board, not content** |

Live table_ids (same doc + 搭法):

- T1 `tblwh7EVeAFPfvuy`
- T2 `tblXaQ871ZcrrTPL`
- Anomaly `tblstt4IVNJihCd3`
- AI material (separate) `tblYpFKSJyIimUZ3`

### B. P2 plan reuses "D3 / T4" for video content

**Path:** `E:\project\清泉跨境系统（企业级）\docs\TK-整体开发计划.md` (section P2 ~204-252)

| P2 item | Intent |
|---------|--------|
| P2.1 Schema | `fact_tiktok_content_daily`, `fact_tiktok_product_traffic_daily`, optional `fact_ads_creative_daily` |
| P2.4 | Feishu **D3 / T4** — content board, split from D1/D2; multi-channel CTR |
| P2.5 | Task console: video/traffic list; filter **视频内容**; shop drill to content analysis |

XMind gap map in same doc maps "视频内容分析" to T4/D3 — here T4/D3 mean **content**, conflicting with 建表方案 T4=health / D3=product.

### C. Rebind / 搭法 docs

| Path | Notes |
|------|--------|
| `docs\TK-飞书驾驶舱仪表盘搭法.md` | Live T1/T2/anomaly only; points AI material to separate doc; **no content table** |
| `docs\TK-飞书驾驶舱-仪表盘重绑清单.md` | D1/D2 ops; optional **D3 AI 素材** binds AI广告智能筛选分析表 — **third meaning of D3** (AI grade, not ops content, not product) |
| `docs\TK-AI素材分级-数据链路评估.md` | P4 optional; keep off ops boards |

**Extension guidance:** When implementing P2.4, do not reuse bare "T4/D3" without a qualifier. Prefer new codes e.g. **T6 内容/视频日**, **D4 视频内容分析**, and reserve:

- T4 = health (or folded into T1)
- D3-product vs D3-AI vs P2-content — document explicitly to avoid binding the wrong base table

**No Feishu content/video bitable exists yet**; only draft schema in 整体开发计划.

---

## 3. Anomaly `object_type` filters

### PG CHECK (authoritative)

**Path:** `E:\project\清泉跨境系统（企业级）\backend\migrations\010_tk_anomaly_task.sql`

```text
object_type IN ('product', 'campaign', 'shop', 'order', 'other')
```

**No `content` / `video`.** Adding domain requires migration to widen CHECK (+ optional dim rows).

### Dictionary (011)

**Path:** `E:\project\清泉跨境系统（企业级）\backend\migrations\011_tk_anomaly_types_specialize.sql`

| object_type | Domain (UI label) | Example codes |
|-------------|-------------------|---------------|
| `campaign` | 广告 | ads_roi_low, ads_spend_no_sale, ... |
| `product` | 库存 | product_stockout, product_stock_low, ... |
| `shop` | 店铺分析 (+ health/finance) | shop_gmv_drop, shop_health_low, finance_* |
| `other` | 其它 | other |

Health/finance anomalies share `object_type='shop'` — UI "店铺分析" is broader than pure GMV.

### Docs

**Path:** `E:\project\清泉跨境系统（企业级）\docs\TK-异常任务-PG建表说明.md`
Sections 3.1-3.5 same domains; **no content section**.

**Path:** `E:\project\清泉跨境系统（企业级）\docs\TK-整体开发计划.md`
Target filter set over phases:

```text
店铺分析 | 视频内容 | 达人表现 | 广告 | 库存
```

P2 enables **视频内容**; P3 adds 达人. Machine value not fixed — candidates `content` vs `video` (prefer one; align dim + CHECK + Feishu sync).

P2.3 rule ideas (not implemented): attributed GMV/order drop, impression collapse, expose-no-order, CTR/CVR crash.

### Backend API filter

List endpoint already accepts `object_type` query (`tkFilters.object_type` to `/api/v1/tk/anomaly-tasks`). Once DB allows `content`, **filter plumbing works without new query param** — only option + labels + types seed.

---

## 4. How UI domain filter works today — add "content"

**Location:** `App.vue` ~2295-2302 (`tk-tasks` filter row)

- Select bound to `tkFilters.object_type`
- Options: empty / shop / campaign / product
- Flow: `onTkFilterChange` -> page=1 -> `loadTkTasks` -> query includes `object_type`
- Row display uses `objectTypeLabel(t.object_type)` (~921-927)

**To add 视频内容 (minimal UI):**

1. option `value="content"` label 视频内容 (or `video` — match PG)
2. `objectTypeLabel` map entry
3. Help text ~2217-2220 append 视频内容
4. Optional content anomaly eval buttons (parallel ads/product) — needs backend job first
5. **Blocked until:** CHECK constraint + `dim_tk_anomaly_type` content codes + rules/ingest

**Not the same as:** nav content list page (P2.5 list of videos). Domain filter only slices anomaly tasks.

---

## 5. Extension-point checklist

| Layer | Path / hook | Action for P2 content |
|-------|-------------|------------------------|
| Plan/schema | `docs/TK-整体开发计划.md` P2.1 | Migrate `fact_tiktok_content_daily` etc. |
| Anomaly dim | `migrations/011_*` + new migration | Widen `object_type`; seed content_* codes |
| Anomaly docs | `docs/TK-异常任务-PG建表说明.md` | New section 视频内容 |
| Feishu | `docs/TK-飞书驾驶舱建表方案.md` | New Tn (avoid T4=health clash); D-page not AI D3 |
| API list | `backend/app/api/tk_ops.py` | `GET .../content` or `/contents/ranking` |
| Rules | mirror `tk_ads_rules` / `tk_product_rules` | content anomaly eval |
| UI nav + page | `web/src/App.vue` DOMAIN_NAV + section | `tk-content` tab + loaders |
| UI filter | `tkFilters.object_type` select + labels | option 视频内容 |
| Overview teaser | overview product-rank card sibling | optional TOP content |

---

## 6. Key absolute paths

| Role | Path |
|------|------|
| Task console UI (all TK) | `E:\project\清泉跨境系统（企业级）\web\src\App.vue` |
| P2 content scope + draft tables + D3/T4 (content sense) | `E:\project\清泉跨境系统（企业级）\docs\TK-整体开发计划.md` |
| Feishu T1-T5 / D1-D3 (product/health sense) | `E:\project\清泉跨境系统（企业级）\docs\TK-飞书驾驶舱建表方案.md` |
| Live Feishu table_ids / 搭法 | `E:\project\清泉跨境系统（企业级）\docs\TK-飞书驾驶舱仪表盘搭法.md` |
| Dashboard rebind; D3=AI material | `E:\project\清泉跨境系统（企业级）\docs\TK-飞书驾驶舱-仪表盘重绑清单.md` |
| Anomaly object_type domains | `E:\project\清泉跨境系统（企业级）\docs\TK-异常任务-PG建表说明.md` |
| CHECK object_type | `E:\project\清泉跨境系统（企业级）\backend\migrations\010_tk_anomaly_task.sql` |
| Dim seed object_type | `E:\project\清泉跨境系统（企业级）\backend\migrations\011_tk_anomaly_types_specialize.sql` |
| TK ops APIs | `E:\project\清泉跨境系统（企业级）\backend\app\api\tk_ops.py` |
| TK anomaly API | `E:\project\清泉跨境系统（企业级）\backend\app\api\tk_anomaly_tasks.py` |
| AI material (P4, separate) | `E:\project\清泉跨境系统（企业级）\docs\TK-AI素材分级-数据链路评估.md` |

---

## 7. Bottom line

- **UI today:** overview (shop-daily + product rank), ads, report shell, anomaly tasks with domain filter `shop | campaign | product`. **No content/video page or API.**
- **Feishu today:** T1/T2/anomaly (+ AI material table). **No content bitable.** Docs overload **T4/D3** (health/product vs P2 video vs AI material) — rename before P2.4 build.
- **Add "content" filter:** one option + label map after DB allows `object_type`; full P2 needs schema, ingest, rules, list API, and preferably a `tk-content` nav section cloned from `tk-ads` / product-ranking patterns.
