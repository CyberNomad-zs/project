# Research: sellfox/openapi product fields for traffic severity ranking

## Goal
Determine whether sellfox and Temu OpenAPI can supply ranking signals: SKU货号 (VIP*), 近7天销量, channel (黑猫), on-sale status.

## Sources checked
- `E:\project\temu\temu-monitor\SELLFOX.md`, `OPENAPI.md`, configs
- `src/sellfox/products.js`, `client.js`, `monitor.js`, `diff.js`
- `src/openapi/goods.js`, `monitor.js`, `diff.js`
- sellfox-bridge probe: `logs/probe_updateDate.json`, `bridge/clients/sellfox.py`
- agentseller capture: `capture/hit-068.json` (`product/skc/pageQuery`)

## Verdict matrix

| Field | Sellfox OpenAPI | Temu Partner OpenAPI | Browser pageQuery (not sellfox/openapi) |
|-------|-----------------|----------------------|------------------------------------------|
| SKU 货号 VIP* | Partial: parent `extCode` exists; not in onSaleMap; no VIP samples in probe dump | Possible via `outGoodsSn` (normalized only; no live sample values in repo) | **Yes**: `productSkuSummaries[].extCode` has VIP*, JMCAT*, vip-* |
| 近7天销量 | **No** | **No** (not documented/used) | Field exists: `last7DaysSalesVolume` (+ `productTotalSalesVolume`, sku `todaySalesVolume`); sample page all null/0 |
| channel 黑猫 | **No** dedicated field; only `marketplaceName` | **No** | **No** 黑猫 string; may be business-encoded in SKU prefix (JMCAT/VIP) |
| on-sale filter | **Yes** `selectStatus==="12"` | **Yes** ACTIVE / status4VO=1 | skcStatus / productSelected / removeStatus (different enum) |

## Sellfox available API fields

### Endpoint used
`POST /api/multiplatform/temu/product/getParentPageList.json`

### Real field union (probe_updateDate.json)
`createTime, extCode, marketplaceName, matchJitMode, parentId, productName, selectStatus, shopId, shopName, skcId, trusteeship, updateTime`

### Normalized in `products.js` normalizeParent
- parentId, skcId, shopId, shopName, productName, selectStatus, trusteeship, createTime, updateTime, **extCode**

### Kept in onSaleMap/allMap (groupByShop) — ranking-relevant loss
Only: skcId, parentId, name, selectStatus  
**extCode / marketplaceName / trusteeship dropped** before state/diff.

### Related but unused
- `getChildInfo.json` exists in sellfox-bridge client (`temu_cross_child_info`) — not wired in temu-monitor; could hold SKU-level 货号 (unverified).
- Shipping `queryShipChannel` is logistics channel, not product “黑猫”.

### On-sale filter (sellfox)
1. Pull parents with date windows (`dateType=updateDate`, ≤30d windows, lookbackDays).
2. **Client-side** on-sale = `selectStatus === "12"` (已加入站点).
3. Delist common: still in allMap but status ≠ 12 (often `"13"`).
4. No request-body selectStatus filter today.
5. Status distribution seen: 1,7,9,10,11,12,13,17.

## Temu Partner OpenAPI available fields

### Endpoints
- `bg.local.goods.list.query` (pageNo)
- `temu.local.goods.list.retrieve` (pageToken)

### normalizeGoods keeps
goodsId, name, active, lowTraffic, restrictedTraffic, status4VO, subStatus4VO, goodsShowSubStatus, goodsStatus, **outGoodsSn**, thumbUrl

### Traffic tags (severity-related but not sales rank)
- goodsSearchTags: 1=low traffic, 4=restricted
- lowTrafficTag / restrictedTrafficTag: 1=yes, 2=no

### On-sale filter (openapi)
**list.retrieve:** `goodsSearchType: 'ACTIVE'` → items assumed active.  
**list.query:** `goodsSearchType: 1` + `goodsStatusFilterType: 1`, then `isActiveGoods`:
- goodsStatus ACTIVE/ON_SALE → true; INACTIVE/OFF_SALE/DELETED → false
- status4VO === 1 → on sale; 2–6 → not
- forceAssumeActiveOnType1 config fallback
- empty-after-filter fallback marks all active (anti false delist)

### Snapshot maps only keep name + tag flags (outGoodsSn not persisted to state).

## Can ranking signals be obtained?

### 1) SKU 货号 (VIP*)
- **Sellfox parent list:** has `extCode` key; probe samples never printed values; monitor drops it in groupByShop. **Possibly parent-level only / often empty** (pageQuery shows product.extCode empty, SKU.extCode filled).
- **Sellfox child API:** candidate for SKU 货号; not implemented/probed here.
- **OpenAPI:** `outGoodsSn` is the only external-code-like field in code; **no proof** it equals VIP* 货号.
- **Reliable VIP* source in repo:** agentseller `pageQuery` → `productSkuSummaries[].extCode` (VIP2WCX, VIPR956, vip-*, JMCAT*).

### 2) 近7天销量
- **Sellfox: cannot.**
- **OpenAPI goods list as used: cannot** (no sales fields in module/docs).
- **pageQuery:** `last7DaysSalesVolume` exists; this capture all null (and totalSales 0) — field real, needs on-sale/high-sales pages to validate non-null.

### 3) channel 黑猫
- **Neither sellfox nor openapi expose “黑猫”.**
- Sellfox `marketplaceName` is marketplace/site-ish, not 黑猫 warehouse channel.
- SKU prefixes JMCAT* / VIP* may be internal channel/supplier encoding — business convention, not API channel field.

### 4) On-sale
- Sellfox and OpenAPI both support on-sale sets well (primary purpose of both monitors).
- Suitable as hard filter before ranking traffic severity.

## Implications for traffic severity ranking
If ranking needs **sales volume + VIP 货号 + 黑猫**:
- **Do not rely on current sellfox/openapi monitor payloads alone.**
- Sellfox: only weak extra signal is parent `extCode` (if values ever present) + on-sale; optional child probe.
- OpenAPI: on-sale + low/restricted traffic tags; `outGoodsSn` maybe 货号; **no 7-day sales, no 黑猫**.
- Best in-repo source for VIP 货号 + last7DaysSalesVolume: **agentseller pageQuery / plugin path**, not sellfox/openapi.

## Suggested next probes (if implementing later)
1. Log raw sellfox parent `extCode` values for on-sale SKCs.
2. Call sellfox `getChildInfo` for one parent; inspect SKU codes/sales.
3. OpenAPI `probe` with debug: dump full goods keys for `outGoodsSn` and any sales-like fields.
4. pageQuery filtered to 在售 + sort by sales to confirm non-null `last7DaysSalesVolume`.
5. Clarify business meaning of JMCAT* vs VIP* vs “黑猫” with ops (likely SKU convention, not API).
