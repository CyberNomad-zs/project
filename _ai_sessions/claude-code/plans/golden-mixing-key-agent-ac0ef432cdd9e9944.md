# TK P2 Extension Reuse Map (Read-only findings)

**Scope:** Concrete reuse patterns for P2 tables (`fact_tiktok_content_daily`, `fact_tiktok_product_traffic_daily`, optional `fact_ads_creative_daily`) based on existing TK ingest / schema / anomaly / jobs / API / Feishu sync.

**Key docs (outside backend/):**
- `E:\project\清泉跨境系统（企业级）\docs\TK-整体开发计划.md` (P2 section)
- `E:\project\清泉跨境系统（企业级）\docs\TK-P1-广告细粒度POC结论.md`
- Sync CLI: `E:\project\清泉跨境系统（企业级）\scripts\feishu_tk_daily_sync.py` (repo root, not backend/scripts)

---

## 1. Ingest source registration pattern

**File:** `E:\project\清泉跨境系统（企业级）\backend\app\api\ingest.py`

### Envelope / entry
| Symbol | Role |
|--------|------|
| `IngestEnvelope` | `platform`, `shop_id`, `shop_name`, `biz_date`, `collected_at`, `idempotency_key`, `payload`, `evidence` |
| `IngestBatch` | `{ items: [...] }` max 500 |
| `POST /api/v1/ingest/{source}` -> `ingest()` | Auth: `require_ingest_key` |
| `_ingest_one()` | Write `public.ingest_raw` then `_dispatch_fact()` |
| `_dispatch_fact()` | Source -> processor switch |
| `_default_platform()` | `tiktok*` / `tk_*` -> platform=`tiktok` |
| `_resolve_shop_uuid()` | `shop.external_shop_id` + platform |
| `_shop_display_name()` | Prefer `public.shop.name` |
| `_opt_float()` | Shared optional numeric parse |
| `_maybe_auto_eval_after_ingest()` | Batch-end auto rules (ads/products only today) |

### Registered TK sources (today)

| `source` path param | Processor | Fact table | Natural key (ON CONFLICT) |
|---------------------|-----------|------------|---------------------------|
| `tiktok_ads` | `_process_tiktok_ads` | `tk.fact_ads_campaign_daily` | `(shop_external_id, campaign_name, biz_date)` |
| `tiktok_products` | `_process_tiktok_products` | `tk.fact_tiktok_product` | `(shop_external_id, product_id)` |
| `tiktok_shop_daily` | `_process_tiktok_shop_daily` | `tk.fact_tiktok_shop_daily` | `(shop_external_id, biz_date)` |
| `tiktok_orders` | `_process_tiktok_orders` | `tk.fact_tiktok_order` | `(shop_external_id, order_id)` |
| `tiktok_health_daily` | `_process_tiktok_health_daily` | `tk.fact_tiktok_health_daily` | `(shop_external_id, biz_date)` |
| `tiktok_finance_daily` | `_process_tiktok_finance_daily` | `tk.fact_tiktok_finance_daily` | `(shop_external_id, biz_date)` |
| `tiktok_anomaly_task` / `tk_anomaly_task` / `tiktok_risk_alert` | `_process_tiktok_anomaly_task` | `tk.fact_tk_anomaly_task` | `(task_key)` |

### Processor skeleton (copy for P2)
Every `_process_tiktok_*` follows:

1. Validate required fields (`shop_id`, `biz_date`, entity id)
2. `known = {camelCase + snake_case aliases}`; `extra = payload - known` -> `raw_extra` jsonb
3. `INSERT INTO tk.<fact> (...) VALUES (...) ON CONFLICT (<natural_key>) DO UPDATE SET ... COALESCE for soft fields, overwrite metrics, updated_at=now()`
4. Link `ingest_id`, `collected_at`, resolve `shop_name` via `_shop_display_name`

### P2 sources to add (per plan P2.2)
| source | planned table | suggested natural key |
|--------|---------------|----------------------|
| `tiktok_content` | `tk.fact_tiktok_content_daily` | `(shop_external_id, biz_date, channel, content_id)` |
| `tiktok_product_traffic` | `tk.fact_tiktok_product_traffic_daily` | `(shop_external_id, biz_date, product_id, channel)` |
| `tiktok_ads_creative` (optional) | `tk.fact_ads_creative_daily` | `(shop_external_id, biz_date, creative_id)` or +campaign |

**Touch points in `ingest.py` for each new source:**
1. New `_process_tiktok_content` / `_process_tiktok_product_traffic` / `_process_tiktok_ads_creative`
2. Branch in `_dispatch_fact`
3. Add to `refreshable` set in `_ingest_one` (so duplicate idempotency_key still UPSERTs facts)
4. Optionally extend `_maybe_auto_eval_after_ingest` with new settings flags (mirror `tk_ads_auto_eval_on_ingest` / `tk_product_auto_eval_on_ingest`)

### Anomaly type maps already in ingest (011-aligned)
- `_TK_ANOMALY_CN_TO_CODE` / `_TK_ANOMALY_CODE_TO_CN` / `_TK_ANOMALY_CODE_ALIASES`
- Used by `_process_tiktok_anomaly_task` only - not by rule jobs (rules call `tk_anomaly.create_anomaly_task` which reads `dim_tk_anomaly_type`)
- **P2 must extend all three maps** when new content/traffic codes land, or Chinese Feishu options will fall through to `other`

---

## 2. Schema / migration pattern

### Migration chain (TK-relevant)

| File | What |
|------|------|
| `migrations/001_init.sql` | `fact_ads_campaign_daily` base (public); `ingest_raw`, `shop`, `task`, `sync_feishu_*` |
| `migrations/003_tiktok_ads_p1_fields.sql` | ALTER ads: `plan_status`, `delivery_status`, `daily_budget`, `target_roi`, `net_cost`, `avg_order_cost` |
| `migrations/005_tiktok_orders.sql` | `fact_tiktok_order` |
| `migrations/006_tiktok_products.sql` | `fact_tiktok_product` |
| `migrations/007_tiktok_shop_kpi_health_finance.sql` | `fact_tiktok_shop_daily`, `health_daily`, `finance_daily` |
| `migrations/008_tk_schema.sql` | `CREATE SCHEMA tk`; move 6 fact tables public->tk; public compatibility VIEWs |
| `migrations/010_tk_anomaly_task.sql` | `tk.fact_tk_anomaly_task` + `tk.dim_tk_anomaly_type` (minimal seed) |
| `migrations/011_tk_anomaly_types_specialize.sql` | Full TK codes; deprecate AMZ-ish codes |

### Common fact-table columns (reuse template)

```
id UUID PK DEFAULT gen_random_uuid()
shop_id UUID REFERENCES public.shop(id)
shop_external_id TEXT NOT NULL
shop_name TEXT
biz_date DATE NOT NULL          -- snapshot tables (product) may omit
... domain metrics NUMERIC(18,4|6) ...
currency TEXT DEFAULT 'GBP'
source_url TEXT
raw_extra JSONB NOT NULL DEFAULT '{}'
collected_at TIMESTAMPTZ
ingest_id UUID REFERENCES public.ingest_raw(id)
created_at / updated_at TIMESTAMPTZ
UNIQUE (<grain>)
INDEX on (biz_date DESC) and/or (shop_external_id, biz_date)
```

### 008 schema move pattern
`008_tk_schema.sql` table list currently:
`fact_ads_campaign_daily`, `fact_tiktok_order`, `fact_tiktok_product`, `fact_tiktok_shop_daily`, `fact_tiktok_health_daily`, `fact_tiktok_finance_daily`

**P2 preference:** create new tables **directly in `tk`** (like 010), grant to `qingquan`, optional `public.*` VIEW for compat. If following 005-007 style (create in public then 008-move), also extend the 008 arrays - but new migration `012_...` creating in `tk` is cleaner.

### Existing grain reference

| Table | Grain UNIQUE |
|-------|--------------|
| `tk.fact_ads_campaign_daily` | shop x campaign_name x biz_date |
| `tk.fact_tiktok_product` | shop x product_id (**snapshot**, no biz_date) |
| `tk.fact_tiktok_shop_daily` | shop x biz_date |
| `tk.fact_tiktok_order` | shop x order_id |
| `tk.fact_tk_anomaly_task` | `task_key`; partial unique open `dedupe_key` |

---

## 3. What NEW migration/schema P2 needs

Per `docs/TK-整体开发计划.md` P2.1 draft + existing conventions:

### A. `tk.fact_tiktok_content_daily` (required for domain 2)

Suggested columns (plan draft + house style):

| Column | Notes |
|--------|-------|
| standard shop/biz/meta block | as above |
| `channel` TEXT | `short_video | live | photo | other` + CHECK |
| `content_id` TEXT NOT NULL | video/photo id |
| `content_title` TEXT | |
| `attributed_gmv` NUMERIC | video attributed GMV |
| `attributed_sku_orders` NUMERIC | video attributed SKU orders |
| `impressions`, `clicks`, `ctr`, `play_count`, `customers` | |
| `product_id` TEXT NULL | link to product |
| `ad_creative_id` TEXT NULL | link to creative if known |
| `currency`, `source_url`, `raw_extra`, ... | |
| **UNIQUE** | `(shop_external_id, biz_date, channel, content_id)` |

Note: plan wrote `coalesce(content_id,'')` - prefer NOT NULL content_id or use generated column; PG UNIQUE treats NULLs as distinct.

Indexes: `(biz_date DESC)`, `(shop_external_id, biz_date)`, optional `(product_id)` where not null.

### B. `tk.fact_tiktok_product_traffic_daily` (required for product-card CTR/CVR)

| Column | Notes |
|--------|-------|
| standard shop/biz/meta | |
| `product_id` TEXT NOT NULL | align with `fact_tiktok_product.product_id` |
| `product_name` / `seller_sku` optional | denormalized for UI |
| `channel` TEXT | `product_card | ads_link | short_video | live | other` |
| `impressions`, `clicks`, `ctr`, `orders`, `gmv`, `cvr` | |
| **UNIQUE** | `(shop_external_id, biz_date, product_id, channel)` |

### C. `tk.fact_ads_creative_daily` (OPTIONAL - gate = P1.7)

**Gate from `TK-P1-广告细粒度POC结论.md`:** do NOT create empty table until:
1. >=3 days samples in `ingest_raw` from creative/group report page or API
2. Field dictionary signed (id, name, spend/orders/revenue/ROI, optional impress/click, parent campaign_id)
3. Association strategy documented (FK/map vs separate display)

If gate passes, suggested grain:

| Column | Notes |
|--------|-------|
| standard + `biz_date` | |
| `creative_id` TEXT NOT NULL | |
| `creative_name` TEXT | |
| `campaign_name` / `campaign_id` | parent series |
| `adgroup_id/name` optional | if group view exists |
| `spend`, `orders`, `roi`, `revenue` | mirror campaign daily |
| `impressions`, `clicks`, `ctr` optional | |
| `content_id` / `product_id` nullable | P2.6 association |
| P1 campaign extras optional | budget/cpa if present at creative grain |
| **UNIQUE** | `(shop_external_id, creative_id, biz_date)` |

**Explicitly forbidden (P1.7):** cloning campaign rows as fake creative rows; mixing AI S/A/B/C/D into ops disk.

### D. Same migration should also (if codes known)

Extend `tk.dim_tk_anomaly_type` with content/traffic codes (see section 5) via `INSERT ... ON CONFLICT DO UPDATE` pattern from 011 - or ship `013_tk_content_anomaly_types.sql`.

### E. 008 / grants
- `GRANT SELECT, INSERT, UPDATE, DELETE ON tk.<new> TO qingquan;`
- Optional `CREATE VIEW public.<name> AS SELECT * FROM tk.<name>;`
- No need to re-run 008 if tables born in `tk`

### F. What does NOT need new schema
- `fact_tk_anomaly_task` already supports `object_type` in (`product`,`campaign`,`shop`,`order`,`other`) - content may need **CHECK expand** to `'content'` or map content anomalies to `object_type='other'` / product. **Decision point for P2.**
- `public.task` / `anomaly_event` reuse via `task_engine.upsert_task_from_anomaly`
- `sync_feishu_map` / `sync_feishu_job` already generic by `table_key`

---

## 4. Anomaly classification + eval job pattern

### Domain layer trio (clone this)

| Domain | Classify (pure) | Fetch | Evaluate | Codes written |
|--------|-----------------|-------|----------|---------------|
| `app/domain/tk_ads_rules.py` | `classify_ads_row` | `fetch_ads_rows` | `evaluate_ads_anomalies` | `ads_spend_no_sale`, `ads_roi_low`, `ads_cpa_high`, `ads_budget_burn` |
| `app/domain/tk_product_rules.py` | `classify_product_row` | `fetch_product_rows` | `evaluate_product_anomalies` | `product_stockout`, `product_stock_low` |
| `app/domain/tk_shop_rules.py` | `classify_shop_pair` | `fetch_shop_daily_rows` + `fetch_prev_shop_daily_map` | `evaluate_shop_anomalies` | `shop_gmv_drop`, `shop_order_drop` |

**Shared pattern:**
1. Pure `classify_*` returns `list[{anomaly_code, priority, summary, metric_snapshot, detail}]`
2. `EvalStats` dataclass -> `as_dict()` with hit counters + samples[:10] + errors[:20]
3. `evaluate_*` loads Settings thresholds from `app/config.py`
4. Skip test smoke names (`schema-tk-smoke`, `[test]`)
5. Persist via `tk_anomaly.create_anomaly_task(...)` with:
   - `dedupe_key=f"tiktok:{object_ref}:{code}"`
   - `object_type` in campaign|product|shop
   - `project_center_task` flag
   - open-dedupe update path (refresh summary/metric, keep open)
6. `dry_run` counts without write
7. Single-row try/except - batch continues

### Write path core
**File:** `app/domain/tk_anomaly.py`
| Function | Role |
|----------|------|
| `list_anomaly_types` | Read `tk.dim_tk_anomaly_type` |
| `list_anomaly_tasks` / `get_anomaly_task` | Filtered list + status summary |
| `create_anomaly_task` | Lookup dim -> open dedupe -> optional `task_engine.upsert_task_from_anomaly` -> INSERT |
| `update_progress` / `resolve_task` | Collaboration; mirrors center task |
| `_lookup_type` | code/name_cn -> defaults from dim |
| `_make_task_key` | `T{YYYYMMDD}-{shop}-{obj}-{code}` |

### CLI jobs (thin wrappers)
| Job module | Calls |
|------------|-------|
| `app/jobs/tk_ads_anomaly_eval.py` | `evaluate_ads_anomalies` |
| `app/jobs/tk_product_anomaly_eval.py` | `evaluate_product_anomalies` |
| `app/jobs/tk_shop_anomaly_eval.py` | `evaluate_shop_anomalies` |

CLI flags standard: `--biz-date`, `--shop-external-id`, `--dry-run`, `--no-center-task`

### Config thresholds (`app/config.py`)
```
tk_ads_min_spend, tk_ads_global_min_roi, tk_ads_roi_target_ratio, tk_ads_roi_target_slack,
tk_ads_budget_burn_ratio, tk_ads_budget_min, tk_ads_max_cpa, tk_ads_cpa_aov_ratio,
tk_ads_auto_eval_on_ingest,
tk_product_stockout_qty, tk_product_stock_low_qty, tk_product_auto_eval_on_ingest,
tk_shop_gmv_drop_ratio, tk_shop_order_drop_ratio, tk_shop_min_gmv_base,
tk_shop_min_orders_base, tk_shop_p0_drop_ratio,
tk_rules_project_center_task
```

**P2 add:** e.g. `tk_content_*` drop ratios / min baseline / auto_eval flags - same style.

### P2 rules to add (plan P2.3)
New module e.g. `app/domain/tk_content_rules.py` (+ optional `tk_traffic_rules.py`):

| Direction (plan) | Suggested code | object_type | Fact source |
|------------------|----------------|-------------|-------------|
| video attributed GMV drop | `content_gmv_drop` | content/other | content_daily DoD like shop |
| video attributed order drop | `content_order_drop` | content/other | content_daily |
| impressions collapse | `content_impressions_drop` | content/other | content_daily |
| impressions no order | `content_impr_no_order` | content/other | impressions>0 and orders=0 |
| CTR/CVR collapse | `traffic_ctr_drop` / `traffic_cvr_drop` | product | product_traffic_daily |
| click no order | `traffic_click_no_order` | product | product_traffic_daily |

Reuse **shop pair pattern** (`classify_shop_pair` + `fetch_prev_*_map` with `DISTINCT ON`) for DoD drops; reuse **ads absolute threshold pattern** for "impressions no order".

Job: `app/jobs/tk_content_anomaly_eval.py` mirroring shop/ads CLI.

---

## 5. Anomaly type dictionary pattern (011)

### Tables
- **Authoritative:** `tk.dim_tk_anomaly_type`
  Columns: `code PK`, `name_cn`, `object_type`, `severity_default`, `priority_default`, `description`, `enabled`, `sort_order`
- Created: `010_tk_anomaly_task.sql`
- Specialized: `011_tk_anomaly_types_specialize.sql`

### 011 algorithm
1. `UPDATE ... SET enabled=FALSE` on old AMZ-ish codes (`stock_low`, `roi_low`, ...)
2. `INSERT ... ON CONFLICT (code) DO UPDATE` full TK set
3. Annotate old rows with alias mapping in description
4. Keep old rows for historical `anomaly_code` references

### Current enabled code catalog (011)

| Domain | codes |
|--------|-------|
| Ads | `ads_roi_low`, `ads_spend_no_sale`, `ads_budget_burn`, `ads_cpa_high`, `ads_plan_anomaly` |
| Product | `product_stockout`, `product_stock_low`, `product_overstock`, `product_sales_drop`, `product_zero_sales`, `product_delist`, `product_price_anomaly` |
| Shop ops | `shop_gmv_drop`, `shop_order_drop`, `shop_refund_spike` |
| Health | `shop_health_low`, `shop_late_dispatch`, `shop_neg_feedback` |
| Finance | `finance_pending_high`, `finance_refund_high` |
| Fallback | `other` |

### Dual maintenance (easy to miss)
When adding codes, update **all** of:
1. `migrations/01x_....sql` -> `dim_tk_anomaly_type`
2. `ingest.py` `_TK_ANOMALY_CN_TO_CODE` + `_TK_ANOMALY_CODE_TO_CN` (+ aliases if renaming)
3. `bitable.py` `_TK_ANOMALY_TYPE_CN` (partial map today - incomplete vs 011)
4. Feishu bitable anomaly-type single-select options (ops script `scripts/feishu-tk-create-fields.ps1`)
5. Rule `classify_*` hit codes must match dim `code` exactly (`_lookup_type` falls back to `other`)

### object_type CHECK gap for P2
`fact_tk_anomaly_task.object_type` CHECK: `'product','campaign','shop','order','other'`
Plan wants filter domain for video content. Options:
- a) ALTER CHECK add `'content'` (cleanest for task-desk filter)
- b) use `other` + encode domain in `anomaly_code` prefix `content_*` / filter by code prefix
- c) use `product` for traffic, `other` for video

Recommend **(a)** in same P2 migration as content facts.

---

## 6. API list patterns (`tk_ops` + `tk_anomaly_tasks`)

### `app/api/tk_ops.py` - prefix `/api/v1/tk`

| Endpoint | Pattern to clone |
|----------|------------------|
| `GET /shop-daily` | Wide join shop+ads rollup+health+finance; **fallback** ads rollup if shop_daily empty; summary + `available_dates`; pagination |
| `GET /ads/campaigns` | Day grain list + LATERAL open anomaly markers; summary spend/orders/revenue/roi |
| `GET /products/ranking` | Snapshot rank by `sales_qty`; note non-daily GMV |
| `POST|GET /ads/anomaly-eval` | Body/query -> domain evaluate; GET defaults `dry_run=True` |
| `POST|GET /products/anomaly-eval` | same |
| `POST|GET /shop/anomaly-eval` | same |

**P2 API adds (plan P2.5):**
- `GET /content/daily` or `/content/ranking` - list from `fact_tiktok_content_daily`
- `GET /products/traffic` - multi-channel CTR/CVR compare
- `POST|GET /content/anomaly-eval` (+ traffic)
- Optional `GET /ads/creatives` if creative table exists

Auth: `get_current_user` (JWT), not ingest key.

### `app/api/tk_anomaly_tasks.py` - prefix `/api/v1/tk/anomaly-tasks`
CRUD on anomaly tasks; `GET /types` -> dim dictionary.
List already filters `object_type` / `anomaly_code` - content domain works once codes + object_type exist.
No API change strictly required for P2 outbox if filters by code prefix.

Registered in `app/main.py`: `tk_ops`, `tk_anomaly_tasks`, `ingest`.

---

## 7. Feishu sync pattern

### Engine: `app/jobs/tk_feishu_sync.py`
| Symbol | Role |
|--------|------|
| `TABLE_SPECS` | `table_key` -> `{local_table, date_col, mapper, select, fallback_*}` |
| `sync_table()` | incremental by `updated_at`/`biz_date` lookback; content_hash skip; `sync_feishu_map` upsert |
| `run_feishu_job()` | worker entry for `sync_feishu_job` rows |
| `resolve_tk_app_token` / `resolve_table_id` | settings |

**Current keys:** `tk_shop_daily`, `tk_ads_campaign`, `tk_anomaly_task`

### Mappers: `app/adapters/feishu/bitable.py`
- `tk_shop_daily_to_fields`, `tk_ads_campaign_to_fields`, `tk_anomaly_task_to_fields`
- `content_hash(fields)` for change detection
- Chinese column names match Feishu base

### CLI: `E:\project\清泉跨境系统（企业级）\scripts\feishu_tk_daily_sync.py`
- Adds backend to `sys.path`, loops keys, calls `sync_table`
- Flags: `--lookback-days`, `--limit`, `--dry-run`, `--ads-only`, `--shop-only`, `--anomaly-only`

**P2 Feishu extension steps:**
1. Config: `feishu_bitable_table_tk_content_daily` (+ traffic/creative)
2. `TABLE_SPECS["tk_content_daily"]` + SELECT SQL + mapper
3. Extend CLI key list / `--content-only`
4. Create Feishu table fields (existing ps1 pattern)
5. Plan D3/T4 separate dashboard from D1/D2

Worker already routes tk jobs via `app/jobs/worker.py` -> `run_feishu_job`.

---

## 8. P2 plan + P1.7 POC - decisions that constrain schema

### From overall plan P2
Pipeline order locked: collect stable -> schema -> ingest -> rules/sync -> board
Gate: no empty schema if content-analysis pages not stably scrapeable.

Work items: P2.0 POC -> P2.1 schema -> P2.2 ingest sources -> P2.3 rules domain video content -> P2.4 Feishu -> P2.5 task desk -> P2.6 association keys.

### From P1.7 POC conclusion
- Campaign daily = steady; creative/group = not proven
- Full creative fact **deferred to P2** and **same batch as content association** (one key system)
- Do not invent creative rows from campaign
- Transition ops keep series rules only

---

## 9. End-to-end reuse checklist for one new P2 domain

Example: **content daily**

1. **Collector** -> POST `/api/v1/ingest/tiktok_content` with envelope + idempotency_key
2. **Migration 012** -> `tk.fact_tiktok_content_daily` (+ optional object_type CHECK; dim codes)
3. **ingest.py** -> `_process_tiktok_content`, dispatch, refreshable, optional auto_eval
4. **config.py** -> thresholds + `tk_content_auto_eval_on_ingest`
5. **tk_content_rules.py** -> classify + evaluate -> `create_anomaly_task`
6. **tk_content_anomaly_eval.py** CLI
7. **tk_ops.py** -> list + anomaly-eval endpoints
8. **tk_feishu_sync.py** + bitable mapper + settings table id
9. **feishu_tk_daily_sync.py** keys
10. **Tests** mirror `tests/test_tk_ads_rules.py` / `test_tk_anomaly_tasks.py`
11. **011-style** dim + ingest CN maps + Feishu anomaly-type options
12. **Do not** ship schema before P2.0 samples in `ingest_raw`

Same strip for `product_traffic`; creative only after P1.7 gate.

---

## 10. File index (absolute paths)

### Backend core
- `E:\project\清泉跨境系统（企业级）\backend\app\api\ingest.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\api\tk_ops.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\api\tk_anomaly_tasks.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\domain\tk_ads_rules.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\domain\tk_product_rules.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\domain\tk_shop_rules.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\domain\tk_anomaly.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\jobs\tk_ads_anomaly_eval.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\jobs\tk_product_anomaly_eval.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\jobs\tk_shop_anomaly_eval.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\jobs\tk_feishu_sync.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\adapters\feishu\bitable.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\config.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\main.py`

### Migrations
- `E:\project\清泉跨境系统（企业级）\backend\migrations\001_init.sql`
- `E:\project\清泉跨境系统（企业级）\backend\migrations\003_tiktok_ads_p1_fields.sql`
- `E:\project\清泉跨境系统（企业级）\backend\migrations\005_tiktok_orders.sql` through `007_...sql`
- `E:\project\清泉跨境系统（企业级）\backend\migrations\008_tk_schema.sql`
- `E:\project\清泉跨境系统（企业级）\backend\migrations\010_tk_anomaly_task.sql`
- `E:\project\清泉跨境系统（企业级）\backend\migrations\011_tk_anomaly_types_specialize.sql`

### Docs / scripts (repo root)
- `E:\project\清泉跨境系统（企业级）\docs\TK-整体开发计划.md`
- `E:\project\清泉跨境系统（企业级）\docs\TK-P1-广告细粒度POC结论.md`
- `E:\project\清泉跨境系统（企业级）\scripts\feishu_tk_daily_sync.py`

---

## 11. Summary: minimal net-new for P2 backend

| Layer | Required new | Optional (creative gate) |
|-------|--------------|---------------------------|
| Migration | `fact_tiktok_content_daily`, `fact_tiktok_product_traffic_daily`; dim codes; maybe object_type CHECK | `fact_ads_creative_daily` |
| Ingest sources | `tiktok_content`, `tiktok_product_traffic` | `tiktok_ads_creative` |
| Rules/jobs | content (+ traffic) classify/eval/CLI | creative-level rules later |
| API | content list, traffic compare, eval triggers | creatives list |
| Feishu | T4/content table_key + mapper + env | creative table |
| Config | content/traffic thresholds + auto_eval | - |

**Do not reinvent:** envelope/idempotency, shop resolve, raw_extra, ON CONFLICT upsert, `create_anomaly_task` dedupe, EvalStats/dry_run, Feishu content_hash map, public.task projection.
