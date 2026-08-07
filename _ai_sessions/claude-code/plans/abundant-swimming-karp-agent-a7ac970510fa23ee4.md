# Findings: Traffic/限流 Detection & Product Fields

Research only — no code changes. Covers temu-plugin + temu-monitor for new rule feasibility:
VIP-prefix SKU / 7-day sales >20 / black-cat channel.

---

## 1. How traffic / 限流 is detected today

### temu-plugin (primary, live Chrome extension)

| Signal | Source | Detection | Alert path |
|--------|--------|-----------|------------|
| 商品流量待关注 | DOM chip use-quick-field_tsx_card + countDistance | readChipCount('商品流量待关注') | chipStats → _diffAndAlert |
| 商品流量近期有下降 | Per-row red badge text | countDeclineBadges / scanProducts flags | same |
| 在售过滤 | Row text 在售 / 已下架… | detectSaleStatus | only saleStatus==='onSale' alerts |
| countStatus | API hook | onSale etc. for display | delist OFF (DELIST_IN_PLUGIN=false) |

**Key files / functions**

- E:\project\temu\temu-plugin\content.js
  - scanProducts(), readChipCount(), countDeclineBadges(), detectSaleStatus(), onlyOnSale(), readTraffic(), scanWatchList(), scanOnSaleList()
  - Passive poll every 2s → chrome.runtime.sendMessage({ type:'chipStats', ... })
- E:\project\temu\temu-plugin\inject.js
  - Hooks fetch + XHR; posts { __temuMon, kind, url, body, mallId }
- E:\project\temu\temu-plugin\background.js
  - parseCountStatus, parsePageQuery, normalizeSku, extractSkusFromProduct
  - _diffAndAlert / diffAndAlert (traffic alerts)
  - diffProductSkus (SKU disappearance — separate from traffic)
  - sendMustRemind / setupMustRemindAlarms
  - Message: chipStats, capture, mustRemindNow

**Traffic alert logic (v15)** — _diffAndAlert:

1. Seed baselines on first see (alertedWatchIds / alertedDeclineIds) — no Feishu.
2. Watch: chip rise OR passive on-sale watch items → optional scanWatchViaTab → pickFreshItems (6h cooldown by productId).
3. Decline: only fresh on-sale declineItems productIds (no 0↔1 count thrash).
4. Alert lines: name + edit link + SKC only via itemLines.

**Important:** Traffic = DOM badges/chips, not pageQuery.flowLimit*. Those API fields exist but are unused and were null in the capture sample.

### temu-monitor (Playwright port)

- E:\project\temu\temu-monitor\src\domScan.js — port of content.js helpers (scanProducts without saleStatus).
- E:\project\temu\temu-monitor\src\monitor.js — scanStore, attachCountStatusCapture.
- E:\project\temu\temu-monitor\src\state.js — diffStore (watch/decline count up).
- OpenAPI path: openapi/goods.js + openapi/diff.js
  - tags: goodsSearchTags 1=low, 4=restricted
  - fields: lowTrafficTag, restrictedTrafficTag
  - normalized: goodsId, name, active, lowTraffic, restrictedTraffic, outGoodsSn, …
- Sellfox: delist only; comment says 限流/待关注 not available → use plugin. Has extCode on parent.

---

## 2. inject.js — APIs captured

MATCH regex / kindOf:

| kind | URL fragment |
|------|----------------|
| countStatus | visage-agent-seller/product/skc/countStatus |
| pageQuery | visage-agent-seller/product/skc/pageQuery |
| skuSpecList | anniston-agent-seller/sku/spec/parent/list |
| skuPriceQuery | visage-agent-seller/product/sku/site/suggestedPrice/gray/query |

Also sees (not matched by inject): pageQueryForHKHistory, de/onSale/pageQuery, draft/import pageQueries, etc.

**countStatus parse** (parseCountStatus):
- result.skcTopStatusCountList[]: skcTopStatus, skcTotal
- Mapped: 100→onSale, 0→unpublished, 200→removed, 300→deleted

**pageQuery parse** (parsePageQuery) — currently kept only:

Product: productId, productSkcId→skc, productName→name, productSkuSummaries→skus, skuCount
SKU (normalizeSku): productSkuId→skuId, spec name from productSkuSpecList, thumbUrl→img, realStock/virtualStock→stock, parent productId/skc/name

Not parsed today (but present in API — see section 3).

---

## 3. pageQuery real fields (from temu-monitor/capture/hit-068.json)

Endpoint: POST .../product/skc/pageQuery
Shape: { success, result: { total, pageItems[] } } — sample total=399, page=20.

### Product-level (high value for rules)

| Field | Type (sample) | Notes |
|-------|---------------|-------|
| productId | number | SPU; DOM SPU ID; edit link |
| productSkcId | number | SKC |
| productName | string | |
| goodsId | number | OpenAPI-style id |
| extCode | string | SKC-level 货号; often empty when SKU has codes |
| productTotalSalesVolume | number | always present; sample all 0 |
| last7DaysSalesVolume | number or null | 7-day sales; sample all null |
| skcTopStatus | number | 0/100/200 align countStatus |
| skcStatus / skcSiteStatus | number | |
| flowLimitStatus | null sample | traffic-limit candidate |
| flowLimitStyle | null sample | |
| flowAllowanceStatus | number | sample 1 |
| productSemiManaged.bindSites[] | siteId, siteName | e.g. 英国站#102 — site not 黑猫 channel |
| supplierSourceType | number | sample 4000 |
| productTags / goodsAdvantageLabelVOList / productPrivilegeInfo | null in sample | possible label hooks |
| hotSaleGoodsLabelStyle | number or null | rare |
| leafCat / categories | cat tree | not channel |

### SKU-level (productSkuSummaries[])

| Field | Type | Notes |
|-------|------|-------|
| productSkuId | number | |
| extCode | string | SKU 货号 — primary for VIP rule |
| productSkuSpecList[] | parentSpecName, specName | |
| todaySalesVolume | number or null | sample all null |
| virtualStock / realStock | | |
| flowLimit / preLimitTime | null sample | SKU-level limit? |
| punishInfo / toPrivilege | null | |
| siteSupplierPrices[] | price by siteId | |

### VIP evidence in capture

- 11/37 SKUs had VIP-like extCode: VIP2WCX, VIPR956, vip-Black & Red, vip-Grey-2m / 6.6ft, …
- Product-level extCode often empty; match on SKU extCode.

### Sales evidence in capture

- productTotalSalesVolume always 0 on that page (mixed statuses).
- last7DaysSalesVolume / todaySalesVolume keys exist, values null — may only fill for on-sale / certain filters. Must re-capture on 在售中 tab before trusting >20 rule.

### Black cat / 渠道

- No 黑猫, channel name, warehouse-channel field in pageQuery sample or plugin/monitor code.
- Closest: productSemiManaged.bindSites[].siteName (站点), supplierSourceType — not 黑猫.
- Menu capture only has SKU货号匹配规则, 销量分析 labels — not product channel.

---

## 4. DOM fields (scanProducts / chips)

Parsed from row text / structure:

- productId ← /SPU\s*ID[:：]\s*(\d+)/
- skc ← /SKC\s*ID[:：]\s*(\d+)/
- name ← Chinese text in info td (6–80 chars)
- watch ← text includes 商品流量待关注
- decline ← text includes 商品流量近期有下降
- saleStatus ← 在售 | 已下架/已终止/已删除 | unknown (plugin only; monitor scan omits)

Not scraped from DOM:

- 货号 / SKU extCode
- 销量 / 7日销量 / 今日销量
- 渠道 / 黑猫
- VIP as structured field

Chip / tab DOM:

- Quick filter: [class*="use-quick-field_tsx_card__"] + [class*="countDistance"]
- Rows: [data-testid="beast-core-table-body-tr"]
- Tabs: [data-testid="beast-core-tab-itemLabel"] e.g. 在售中 N
- Footer: 共有 N 条

---

## 5. background alert / mustRemind flow

inject postMessage
  → content forwards type:capture + store
  → bg parseCountStatus | parsePageQuery | parseSkuSpecList | parseSkuPriceQuery
  → updateStoreLatest; pageQuery also diffProductSkus

content setInterval 2s
  → type:chipStats { trafficWatch, trafficDecline, watchItems, declineItems }
  → updateStoreLatest → diffAndAlert(name)

diffAndAlert / _diffAndAlert
  → seed or pickFreshItems (6h) → sendFeishu
  → snapshot: trafficWatch/Decline, alertedWatchIds, alertedDeclineIds

mustRemind (independent of anomaly)
  DEFAULT mustRemindEnabled:true, times ['09:30','16:30']
  setupMustRemindAlarms → alarm name mustRemind|HH:MM
  onAlarm → sendMustRemind(slot) → per-store 在售/待关注/下降/总数 + last cycle
  → reschedule next day
  Manual: msg type mustRemindNow

Idle poll alarm poll every intervalMinutes (default 15) → if idle/locked → cycleStores (traffic refresh only).

---

## 6. New rules: available vs missing

| Rule | Available? | Where | Gap |
|------|------------|-------|-----|
| VIP prefix SKU | Yes in raw API | pageItems[].productSkuSummaries[].extCode | Not extracted by parsePageQuery/normalizeSku; DOM ignores 货号; no rule engine |
| 7-day sales > 20 | Field exists, unproven | last7DaysSalesVolume (product); todaySalesVolume (SKU); productTotalSalesVolume | Sample all null/0; not parsed; may need 在售 list or 销量分析 API |
| Black cat channel | Missing | — | No field in pageQuery/DOM/OpenAPI/Sellfox path reviewed |
| Traffic 待关注/下降 (existing) | Yes | DOM chips/badges | Works; not tied to VIP/sales/channel |

### Implementation sketch (if building rules later)

1. Extend normalizeSku / parsePageQuery to keep extCode, last7DaysSalesVolume, productTotalSalesVolume, todaySalesVolume; optionally flowLimitStatus, flowLimit, skcTopStatus, goodsId, bindSites.
2. Re-capture pageQuery on 在售中 to validate sales non-null.
3. VIP rule: /^vip/i.test(extCode) on any SKU (or product) extCode.
4. Sales rule: Number(last7DaysSalesVolume) > 20 once values confirmed.
5. Black cat: needs product research — blocked on platform fields today.
6. Compose with traffic only after pageQuery commercial fields flow into alert path.

### Cross-system field map

| Concept | Plugin DOM | Plugin pageQuery raw→kept | OpenAPI | Sellfox |
|---------|------------|---------------------------|---------|---------|
| product id | productId (SPU) | productId kept | goodsId | parentId/skcId |
| SKC | skc | productSkcId→skc | — | skcId |
| name | name | productName→name | goodsName | productName |
| 货号 | not read | extCode raw only | outGoodsSn | extCode kept |
| 7日销量 | not read | last7DaysSalesVolume raw only | — | — |
| 今日销量 | not read | todaySalesVolume raw only | — | — |
| VIP | not read | via extCode prefix | — | via extCode |
| 黑猫/渠道 | not read | absent | absent | absent |
| 限流/待关注 | chip+badge | flowLimit* unused/null | restrictedTrafficTag / tag 4 | N/A |
| 在售 | saleStatus / tab | skcTopStatus 100 | active filters | selectStatus 12 |

---

## 7. Key absolute paths

Plugin:
- E:\project\temu\temu-plugin\content.js
- E:\project\temu\temu-plugin\inject.js
- E:\project\temu\temu-plugin\background.js
- E:\project\temu\temu-plugin\使用说明.txt

Monitor:
- E:\project\temu\temu-monitor\src\domScan.js
- E:\project\temu\temu-monitor\src\monitor.js
- E:\project\temu\temu-monitor\src\state.js
- E:\project\temu\temu-monitor\src\openapi\goods.js
- E:\project\temu\temu-monitor\src\openapi\diff.js
- E:\project\temu\temu-monitor\src\sellfox\products.js
- E:\project\temu\temu-monitor\capture\hit-068.json (pageQuery gold sample)
- E:\project\temu\temu-monitor\capture\hit-086.json (countStatus)

---

## 8. Recommended next steps (not done)

1. Capture skc/pageQuery while 在售中 filter active; dump non-null last7DaysSalesVolume / todaySalesVolume / flowLimit*.
2. Manually inspect goods list UI for 货号 / 销量 / 渠道 / 黑猫 columns; note extra XHR when sorting by sales.
3. If black cat is seller-defined tag in 货号 or title, define convention — not in platform fields today.
4. Only then extend parse + rule layer.

**Bottom line:** VIP-prefix is ready from raw extCode with a small parser change. 7-day sales field name is known but data quality unproven. Black-cat channel is not available in current capture surface.
