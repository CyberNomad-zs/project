# P3 Affiliate — Copy-This-Chain from P2 Content / Shop Modules

Read-only map of the existing TK end-to-end pattern. **No affiliate code exists today** (expected). Use content (P2) + shop-modules (violation/reviews) as the dual templates.

---

## 0. Domain intent (from docs only)

Source of truth for P3 scope (not implemented):

- `E:\project\清泉跨境系统（企业级）\docs\TK-整体开发计划.md` — P3 section
  - Path: 商家中心 **联盟** → 联盟中心 → **数据分析 → 表现**
  - Planned facts: `fact_tiktok_affiliate_daily`, `fact_tiktok_affiliate_creator_daily`
  - Anomaly domain: **达人表现** (`object_type` not yet in CHECK — only `product|campaign|shop|order|content|other`)
  - Feishu: T5 / D4 (not wired)
- XMind outline also lists 达人带货（联盟）异常 metrics — design only

**Affiliate is MISSING everywhere in code** (no `*affiliate*` files, no source, no migrate, no rules, no API, no Feishu table key).

---

## 1. Collectors pattern (Ziniao scrape → Qingquan ingest)

Root: `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\`

### 1.1 Two runner families (both valid templates)

| Family | Runner | Modules | Default ingest | Best for affiliate |
|--------|--------|---------|----------------|--------------------|
| **Shop modules** (production daily) | `run-shop-modules.ps1` + `run-shop-modules-daily.ps1` + `install-shop-modules-daily-task.ps1` | `shop_daily,health_daily,finance_daily,violation,reviews` | ON | Good if affiliate is a stable seller-center page like violation |
| **Content POC → production** | `run-content-poc.ps1` (+ deep helpers) | `content_overview,product_traffic,video_list,...` | **OFF** (`-SkipIngest` default `$true`) | Better if 联盟中心 is SPA / multi-hop like content |

Full-site daily (`run-full-site-daily.ps1`) currently chains shop-modules etc.; **does not call content runner**.

### 1.2 How a module is wired (checklist skeleton)

For each new domain module you need:

1. **Scrape JS** — page DOM → payload JSON  
   Examples:
   - Content: `scrape-content-overview-page.js`, `scrape-product-traffic-page.js`, `scrape-video-list-page.js`
   - Shop: `scrape-shop-daily-page.js`, `scrape-health-daily-page.js`, `scrape-finance-daily-page.js`, `scrape-violation-page.js`, `scrape-product-reviews-page.js`
2. **Runner module key** in `$scriptMap` + `Get-ModuleUrl` mapKey  
3. **Config URL key** on `stores.config.json` (top-level block with `.default` / `.byPlatform`, or `cfg.urls.<module>`)
4. **Hardcoded UK default URL** fallback in `Get-ModuleUrl`
5. **`ConvertTo-Qingquan*IngestItems`** in `qingquan-client.ps1`
6. **`Send-QingquanIngest -Source '<source_name>'`**
7. Optional: daily task installer + include in full-site chain

### 1.3 URL config keys (existing)

**Shop modules** (`run-shop-modules.ps1` → `Get-ModuleUrl`):

| moduleKey | config key | default URL (UK) | ingest source |
|-----------|------------|------------------|---------------|
| `shop_daily` | `shopDailyUrl` | compass data overview | `tiktok_shop_daily` |
| `health_daily` | `healthUrl` | health center | `tiktok_health_daily` |
| `finance_daily` | `financeUrl` | finance | `tiktok_finance_daily` |
| `violation` | `violationUrl` | `.../health-center` | `tiktok_violation` |
| `reviews` | `productReviewsUrl` | `.../product/rating` | `tiktok_review` |

**Content** (`run-content-poc.ps1` → `Get-ModuleUrl`):

| moduleKey | config key | default URL | ingest source |
|-----------|------------|-------------|---------------|
| `content_overview` | `contentUrl` | `compass/video-analytics` | **no row fact** (KPI only; skip) |
| `product_traffic` | `productTrafficUrl` | `compass/product-card-analytics` | `tiktok_product_traffic` |
| `video_list` | `videoListUrl` | `compass/video-analytics/video-details` | `tiktok_content` |
| `content_probe` / `content_nav_discover` | probe only | homepage / contentUrl | none |

Resolution order (both runners): `cfg.<UrlKey>.byPlatform[plat]` → `cfg.<UrlKey>.default` → `cfg.urls.<moduleKey>` → hardcoded defaults.

### 1.4 ConvertTo-Qingquan* (qingquan-client.ps1)

File: `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\qingquan-client.ps1`

| Function | Source | Idempotency pattern | Stable business key |
|----------|--------|---------------------|---------------------|
| `ConvertTo-QingquanProductTrafficIngestItems` | `tiktok_product_traffic` | `tiktok_product_traffic:{store}:{bizDate}:{productId}:{channel}` | product_id |
| `ConvertTo-QingquanContentIngestItems` | `tiktok_content` | `tiktok_content:{store}:{bizDate}:{contentId}:{channel}` | content_id from `video-detail-item?id=` (skip if missing) |
| `ConvertTo-QingquanViolationIngestItems` | `tiktok_violation` | `tiktok_violation:{store}:{vkey}` | violation_key |
| `ConvertTo-QingquanReviewIngestItems` | `tiktok_review` | `tiktok_review:{store}:{rkey}` | review_key |
| (+ shop/health/finance/orders/products/ads…) | | | |

Shared helpers: `ConvertTo-QingquanIngestJson`, `Send-QingquanIngest`.

**Content special rules to copy:**
- Window snapshot semantics (do **not** explode 近N天 into N daily rows)
- Skip rows without stable ID
- `biz_date` = window anchor day from runner dateMode (yesterday/today)

**Violation/review special rules to copy:**
- Event/entity tables (not pure daily grain)
- Empty payload OK (`emptyOk`) — skip ingest when 0 rows
- `first_seen_at` driven "new within hours" alerts on backend

### 1.5 Content runner ingest branch (pattern)

In `run-content-poc.ps1` after scrape success (~line 508+):

- `product_traffic` → `ConvertTo-QingquanProductTrafficIngestItems` → source `tiktok_product_traffic`
- `video_list` → `ConvertTo-QingquanContentIngestItems` → source `tiktok_content`
- `content_overview` → explicitly **skip** row ingest

Gated by `-SkipIngest` (POC default true) and config `options.dryRun`.

### 1.6 Shop-modules ingest branch (pattern)

In `run-shop-modules.ps1` switch on `$mod`:

- `shop_daily` / `health_daily` / `finance_daily` / `violation` / `reviews` → matching ConvertTo + `sourceMap[$mod]`

Default modules string includes violation+reviews. Daily wrapper just forwards `-Modules`.

---

## 2. Backend ingest registration

File: `E:\project\清泉跨境系统（企业级）\backend\app\api\ingest.py`

### 2.1 Per-item flow

`POST /{source}` → `ingest()` → `_ingest_one()` → write `ingest_raw` → `_dispatch_fact()` → mark processed  
Batch end: `_maybe_auto_eval_after_ingest()` → optional `auto_anomaly_eval` in response.

### 2.2 refreshable set (duplicate idempotency still UPSERTs fact)

Must add new source names here (around lines 2555–2579), e.g. existing:

- `tiktok_product_traffic`, `tiktok_content`
- `tiktok_violation`, `tiktok_violations`
- `tiktok_review`, `tiktok_reviews`, `tiktok_product_reviews`

### 2.3 `_dispatch_fact` branches

| source alias(es) | processor |
|------------------|-----------|
| `tiktok_product_traffic` | `_process_tiktok_product_traffic` |
| `tiktok_content` | `_process_tiktok_content` |
| `tiktok_shop_daily` | `_process_tiktok_shop_daily` |
| `tiktok_health_daily` | `_process_tiktok_health_daily` |
| `tiktok_finance_daily` | `_process_tiktok_finance_daily` |
| `tiktok_violation` / `tiktok_violations` | `_process_tiktok_violation` |
| `tiktok_review` / `tiktok_reviews` / `tiktok_product_reviews` | `_process_tiktok_review` |

### 2.4 Processor conventions (copy from content or violation)

**Window daily grain (content/traffic):**

- Require `shop_id`, `biz_date`, entity id
- UPSERT `ON CONFLICT (shop_external_id, biz_date, channel, content_id)` (content)
- Metrics `COALESCE(EXCLUDED.x, existing.x)`
- Put window/publish metadata in `raw_extra` JSONB
- Link `ingest_id`

Functions:

- `_process_tiktok_product_traffic` (~1705)
- `_process_tiktok_content` (~1829)

**Event/entity grain (violation/review):**

- Stable key required (or hash fallback)
- `UNIQUE (shop_external_id, violation_key)`
- `first_seen_at` preserved on conflict
- Optional `biz_date` from event timestamp

Functions:

- `_process_tiktok_violation` (~2124)
- `_process_tiktok_review` (~2262)

### 2.5 Auto-eval after ingest (`_maybe_auto_eval_after_ingest`)

Wired today for: ads, products, **content**, health, **violation**, **review**.  
**Not** wired for `tiktok_product_traffic` or shop_daily in this function (shop has separate API eval).

Pattern:

```
if source == "tiktok_content" and settings.tk_content_auto_eval_on_ingest:
    from app.domain.tk_content_rules import evaluate_content_anomalies
    return {"kind": "content", **(await evaluate_content_anomalies(...))}
```

Failures swallowed → `{kind, error}` so ingest result stays OK.

---

## 3. Migrations pattern

Dir: `E:\project\清泉跨境系统（企业级）\backend\migrations\`

| # | File | Role |
|---|------|------|
| 008 | `008_tk_schema.sql` | tk schema baseline |
| 010 | `010_tk_anomaly_task.sql` | `fact_tk_anomaly_task` + dim; object_type CHECK initially without content |
| 011 | `011_tk_anomaly_types_specialize.sql` | specialized anomaly codes |
| **012** | `012_tk_product_traffic_daily.sql` | fact + public view + grants |
| **013** | `013_tk_content_daily.sql` | fact content daily |
| **014** | `014_tk_content_anomaly.sql` | expand object_type CHECK **+ content**; INSERT dim codes |
| 019 | `019_tk_health_anomaly_types.sql` | health codes |
| **020** | `020_tk_violation_review.sql` | fact violation + fact review + dim codes (`shop_violation`, `shop_bad_review`) |

### 3.1 Fact table recipe (013 content)

- `CREATE SCHEMA IF NOT EXISTS tk`
- Table `tk.fact_tiktok_*` with: id UUID, shop_id FK, shop_external_id, shop_name, biz_date, grain keys, metrics NUMERIC, currency, source_url, raw_extra JSONB, collected_at, ingest_id, created_at/updated_at
- `UNIQUE (...)` natural key
- Indexes on date / shop / entity id
- `COMMENT ON TABLE/COLUMN` documenting window semantics
- `CREATE OR REPLACE VIEW public.fact_* AS SELECT * FROM tk.fact_*`
- Optional `GRANT` to role `qingquan`

### 3.2 Anomaly codes recipe (014 content)

1. Drop/recreate CHECK on `tk.fact_tk_anomaly_task.object_type` to add new type
2. `INSERT INTO tk.dim_tk_anomaly_type (...) ON CONFLICT (code) DO UPDATE`

Content codes:

- `content_gmv_drop` (object_type=`content`)
- `content_play_drop`
- `content_imp_no_order`

Violation codes (020, object_type stays `shop` / `product`):

- `shop_violation`
- `shop_bad_review`

**P3 will need a new object_type** (plan says 达人表现) — likely `creator` or `affiliate` — via a 014-style CHECK migration. Today CHECK is only: `product|campaign|shop|order|content|other`.

---

## 4. Domain rules + CLI jobs

### 4.1 Rules modules

| File | Entry | Codes / behavior |
|------|-------|------------------|
| `backend/app/domain/tk_content_rules.py` | `evaluate_content_anomalies`, `classify_content_pair` | window WoW drop + imp_no_order; dedupe `tiktok:{shop}:{content_id}:{code}`; object_type=`content` |
| `backend/app/domain/tk_violation_rules.py` | `evaluate_violation_anomalies` | new within hours via first_seen; notify Feishu bot |
| `backend/app/domain/tk_review_rules.py` | `evaluate_review_anomalies` | bad rating + unreplied |
| `backend/app/domain/tk_shop_rules.py` / `tk_ads_rules.py` / `tk_product_rules.py` / `tk_health_rules.py` | same shape | older domains |
| `backend/app/domain/tk_anomaly.py` | shared upsert into `fact_tk_anomaly_task` (+ optional center task) | **reuse for affiliate** |

### 4.2 CLI jobs (thin wrappers)

| Job module | Calls |
|------------|-------|
| `backend/app/jobs/tk_content_anomaly_eval.py` | `evaluate_content_anomalies` |
| `backend/app/jobs/tk_violation_anomaly_eval.py` | `evaluate_violation_anomalies` |
| `backend/app/jobs/tk_review_anomaly_eval.py` | reviews |
| (+ ads/product/shop/health) | |

CLI flags pattern: `--biz-date`, `--shop-external-id`, `--dry-run`, `--no-center-task` (+ `--no-notify` for bot domains).

`worker.py` is mostly Feishu job runner — anomaly eval is **not** a separate worker type; triggered by ingest auto-eval, HTTP, or `python -m app.jobs.*`.

---

## 5. API / 任务台 TAB pattern

File: `E:\project\清泉跨境系统（企业级）\backend\app\api\tk_ops.py`  
Doc: `E:\project\清泉跨境系统（企业级）\docs\TK-P2-任务台内容TAB.md`

### Content surface area

| Route | Handler | Purpose |
|-------|---------|---------|
| `GET /content` | `list_content_daily` | video window rows + KPI agg |
| `GET /product-traffic` | `list_product_traffic` | product card traffic |
| `POST/GET /content/anomaly-eval` | `run_content_anomaly_eval[_get]` | wrap rules; GET default dry_run |
| data-freshness block | uses `MAX(biz_date)` on content + traffic | stale flags `content` / `traffic` |

Also: `GET/POST` anomaly-eval for ads/products/shop (same style).

Frontend note (from doc): nav key **内容分析** `tk-content` with two subpages (video list + product traffic). P3 plan wants 达人 TAB + anomaly filter option **达人表现**.

Tests to mirror: `backend/tests/test_tk_content_ingest.py`, `test_tk_content_api.py`, `test_tk_content_rules.py`, `test_tk_content_anomaly_api.py`, `test_tk_product_traffic_api.py`.

---

## 6. Feishu sync (T6 content as template for T5 affiliate)

### 6.1 Runtime sync

| Piece | Path / symbol |
|-------|----------------|
| Job core | `backend/app/jobs/tk_feishu_sync.py` |
| TABLE_SPECS key | `tk_content_daily` → local `tk.fact_tiktok_content_daily`, mapper `bitable.tk_content_daily_to_fields`, select `_CONTENT_DAILY_SELECT` |
| Table id resolve | `resolve_table_id`: `s.feishu_bitable_table_tk_content_daily` |
| Mapper | `backend/app/adapters/feishu/bitable.py` → `tk_content_daily_to_fields` |
| Daily CLI | `scripts/feishu_tk_daily_sync.py` — default keys include `tk_content_daily`; flag `--content-only` |
| PS wrapper | `scripts/feishu-tk-daily-sync.ps1` |

Other TABLE_SPECS today: `tk_shop_daily`, `tk_ads_campaign`, `tk_anomaly_task`, `tk_content_daily` only. **No affiliate / T5.**

### 6.2 One-time Feishu table bootstrap

| Script | Creates |
|--------|---------|
| `scripts/feishu-tk-create-t6-content.py` | 多维表「内容日」+ views; prints `FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY=tbl...` |
| `scripts/feishu-tk-create-store-tables.py` + `config/feishu-tk-store-tables.json` | per-store table map (optional dual-write) |
| `scripts/feishu-tk-create-fields.ps1` / `feishu-tk-create-views.py` | older field helpers |

T6 field list (create script): 日期/店铺/店铺ID/内容ID/视频标题/渠道/商品ID/归因GMV/…/窗口/发布时间/本地ID.

Sync map uses `sync_feishu_map` content_hash skip for incremental upserts.

---

## 7. Config / settings thresholds

File: `E:\project\清泉跨境系统（企业级）\backend\app\config.py` → class `Settings`

### Feishu table ids

- `feishu_bitable_app_token_tk`
- `feishu_bitable_table_tk_shop_daily` / `_tk_ads_campaign` / `_tk_anomaly_task`
- **`feishu_bitable_table_tk_content_daily`** (T6)
- `feishu_tk_store_tables_json`

### Content thresholds

- `tk_content_gmv_drop_ratio` = 0.3
- `tk_content_play_drop_ratio` = 0.3
- `tk_content_min_gmv_base` = 5.0
- `tk_content_min_play_base` = 50.0
- `tk_content_min_impressions_no_order` = 200.0
- `tk_content_p0_drop_ratio` = 0.5
- `tk_content_auto_eval_on_ingest` = True

### Violation / review thresholds

- `tk_violation_auto_eval_on_ingest` = True
- `tk_violation_new_within_hours` = 48.0
- `tk_review_auto_eval_on_ingest` = True
- `tk_review_bad_max_rating` = 2.0
- `tk_review_new_within_hours` = 72.0
- `tk_review_only_unreplied` = True
- `feishu_bot_webhook_tk_health` (shared bot for health/violation/review notify)
- `tk_rules_project_center_task` = True

**No `tk_affiliate_*` settings.**

---

## 8. End-to-end chain diagram (content as reference)

```
[stores.config.json URL keys]
        |
        v
scrape-*-page.js  --page.exec-->  run-content-poc.ps1 / run-shop-modules.ps1
        |                              |
        |                     ConvertTo-Qingquan*IngestItems
        |                              |
        |                     Send-QingquanIngest -Source tiktok_*
        v                              v
              POST /api/v1/ingest/{source}  (ingest.py)
                       |
          ingest_raw + _dispatch_fact -> tk.fact_*
                       |
          _maybe_auto_eval_after_ingest
                       |
          domain/tk_*_rules.evaluate_* -> tk.fact_tk_anomaly_task
                       |
          tk_ops.py list + anomaly-eval  |  jobs/tk_*_anomaly_eval.py
                       |
          jobs/tk_feishu_sync.TABLE_SPECS -> Feishu T6
                       |
          scripts/feishu_tk_daily_sync.py (--content-only)
```

---

## 9. Recommended "copy this chain" checklist for P3 Affiliate

Prefer **content-style** if 联盟中心 is multi-hop SPA; prefer **shop-modules** once path is stable and should join nightly Task Scheduler.

### Phase A — POC gate (like P2.0)

- [ ] Doc path confirmation: 联盟中心 → 数据分析 → **表现** (and creator/video/sample as needed)
- [ ] `scrape-affiliate-performance-page.js` (and optional `_probe-affiliate-*.js`, `_discover-affiliate-nav.js`)
- [ ] `run-affiliate-poc.ps1` cloned from `run-content-poc.ps1`
  - modules e.g. `affiliate_overview`, `affiliate_creators`
  - URL keys: `affiliateUrl` / `affiliateCreatorUrl` (names TBD)
  - default `SkipIngest=$true`, debug JSON only
- [ ] Prove stable **creator_id** (or equivalent) before schema — same gate as content_id

### Phase B — Schema (like 012/013 + 014)

- [ ] `migrations/02x_tk_affiliate_daily.sql`
  - `tk.fact_tiktok_affiliate_daily` (shop x biz_date window KPIs)
  - `tk.fact_tiktok_affiliate_creator_daily` (shop x biz_date x creator_id)
  - public views + grants + comments (window semantics)
- [ ] `migrations/02y_tk_affiliate_anomaly.sql`
  - Expand `object_type` CHECK with `creator` or `affiliate`
  - dim codes e.g. `affiliate_gmv_drop`, `affiliate_creator_no_order`, `affiliate_active_creators_drop`, `affiliate_commission_spike` (align with plan: 有投入无成交 / 归因GMV下滑 / 动销达人降 / 佣金退款)
- [ ] Apply via existing `scripts/apply_sql_migration.py` pattern

### Phase C — Collector production path

- [ ] `ConvertTo-QingquanAffiliateIngestItems` (+ creator variant) in `qingquan-client.ps1`
  - idempotency: `tiktok_affiliate:{store}:{bizDate}:{grain...}`
  - skip rows without creator_id when row-level
- [ ] Wire runner ingest: `Send-QingquanIngest -Source 'tiktok_affiliate'` / `tiktok_affiliate_creator`
- [ ] Config: URL blocks on `stores.config*.json`
- [ ] Optional: add modules to `run-shop-modules.ps1` **or** `run-affiliate-daily.ps1` + install task
- [ ] Optional: hook into `run-full-site-daily.ps1`

### Phase D — Ingest + rules

- [ ] `ingest.py`: `_process_tiktok_affiliate[_creator]`, refreshable, `_dispatch_fact`, auto-eval branch
- [ ] `app/domain/tk_affiliate_rules.py` — `evaluate_affiliate_anomalies` using `tk_anomaly` helpers
- [ ] `app/jobs/tk_affiliate_anomaly_eval.py` CLI
- [ ] `config.py`: `tk_affiliate_*` thresholds + `tk_affiliate_auto_eval_on_ingest`
- [ ] Tests: ingest / rules / API (clone content tests)

### Phase E — Ops API + 任务台 TAB

- [ ] `tk_ops.py`: `GET /affiliate` (+ creator list), `POST/GET /affiliate/anomaly-eval`
- [ ] Freshness: `MAX(biz_date)` affiliate in data-quality endpoint
- [ ] Frontend: 达人 TAB + anomaly domain filter **达人表现** (see P2 content TAB doc)
- [ ] Doc: `docs/TK-P3-...` acceptance list

### Phase F — Feishu T5 (clone T6)

- [ ] `scripts/feishu-tk-create-t5-affiliate.py` (clone `feishu-tk-create-t6-content.py`)
- [ ] Settings: `feishu_bitable_table_tk_affiliate_daily` (+ creator table if split)
- [ ] `bitable.tk_affiliate_daily_to_fields`
- [ ] `tk_feishu_sync.TABLE_SPECS["tk_affiliate_daily"]` + `resolve_table_id`
- [ ] `feishu_tk_daily_sync.py`: add key + `--affiliate-only`
- [ ] Optional store-table mapping JSON entries

### Phase G — Ops hardening

- [ ] Quality check script hooks (`scripts/tk_daily_quality_check.py` if extended)
- [ ] Feishu anomaly option labels (`scripts/_feishu_tk_anomaly_options.py`) if used for 达人表现
- [ ] Threshold sign-off with ops (plan explicitly requires 阈值签字)

---

## 10. What is MISSING for affiliate (inventory)

| Layer | Status |
|-------|--------|
| collectors scrape/run/convert | **absent** |
| config URL keys | **absent** |
| ingest source / process / refreshable / auto-eval | **absent** |
| migrations fact + anomaly codes + object_type | **absent** (only planned names in docs) |
| domain rules + jobs | **absent** |
| tk_ops routes / frontend 达人 TAB | **absent** |
| Feishu T5 table create + TABLE_SPECS + settings | **absent** |
| config thresholds `tk_affiliate_*` | **absent** |
| tests | **absent** |

Present only as **product plan / xmind / field dictionary mentions** (`docs/TK-整体开发计划.md`, `docs/字段映射字典.md` creator_sample row, xmind 联盟异常).

---

## 11. Best template pairing (practical advice)

| Affiliate concern | Copy from |
|-------------------|-----------|
| Multi-hop SPA + ID gate + window snapshot | **Content** (`run-content-poc.ps1`, 013/014, content_rules, T6) |
| Nightly multi-module Task Scheduler packaging | **Shop-modules** (`run-shop-modules*.ps1`) |
| "New entity appears → alert + Feishu bot" | **Violation/review** (020, first_seen, notify) |
| Anomaly task upsert / center task projection | **tk_anomaly.py** shared |
| Feishu incremental sync | **tk_content_daily** TABLE_SPECS + create-t6 script |
| API list + manual eval | **tk_ops** `/content` + `/content/anomaly-eval` |

Suggested source names (consistent with existing):

- `tiktok_affiliate` or `tiktok_affiliate_daily`
- `tiktok_affiliate_creator` / `tiktok_affiliate_creator_daily`

Suggested fact names (from plan):

- `tk.fact_tiktok_affiliate_daily`
- `tk.fact_tiktok_affiliate_creator_daily`

---

## 12. Concrete absolute paths (quick index)

**Collectors**

- `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\qingquan-client.ps1`
- `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\run-shop-modules.ps1`
- `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\run-shop-modules-daily.ps1`
- `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\run-content-poc.ps1`
- `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\scrape-video-list-page.js`
- `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\scrape-product-traffic-page.js`
- `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\scrape-violation-page.js`
- `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\scripts\scrape-product-reviews-page.js`

**Backend**

- `E:\project\清泉跨境系统（企业级）\backend\app\api\ingest.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\api\tk_ops.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\config.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\domain\tk_content_rules.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\domain\tk_violation_rules.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\domain\tk_anomaly.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\jobs\tk_content_anomaly_eval.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\jobs\tk_violation_anomaly_eval.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\jobs\tk_feishu_sync.py`
- `E:\project\清泉跨境系统（企业级）\backend\app\adapters\feishu\bitable.py`
- `E:\project\清泉跨境系统（企业级）\backend\migrations\012_tk_product_traffic_daily.sql`
- `E:\project\清泉跨境系统（企业级）\backend\migrations\013_tk_content_daily.sql`
- `E:\project\清泉跨境系统（企业级）\backend\migrations\014_tk_content_anomaly.sql`
- `E:\project\清泉跨境系统（企业级）\backend\migrations\020_tk_violation_review.sql`

**Scripts / docs**

- `E:\project\清泉跨境系统（企业级）\scripts\feishu_tk_daily_sync.py`
- `E:\project\清泉跨境系统（企业级）\scripts\feishu-tk-create-t6-content.py`
- `E:\project\清泉跨境系统（企业级）\docs\TK-整体开发计划.md`
- `E:\project\清泉跨境系统（企业级）\docs\TK-P2-任务台内容TAB.md`
- `E:\project\清泉跨境系统（企业级）\docs\TK-P2-内容分析POC结论.md`

---

## Implementation note

This plan is a **pattern map only** (read-only exploration). No code changes. When implementing P3, start at Phase A POC gate before any migration — same lesson as content_id gate.
