# TikTok products/orders SKU coverage findings (read-only)

## Scope
TikTok collectors + backend ingest only. Checked:
- `E:\project\清泉跨境系统（企业级）\collectors\tiktok-ads\**`
- `E:\project\清泉跨境系统（企业级）\backend\app\api\ingest.py` (`tiktok_orders` / `tiktok_products`)
- migrations `005`, `006`
- sample debug JSON under `collectors\tiktok-ads\logs\`

No `order_line` migration/table exists.

---

## Verdict (direct answers)

| Question | Captured today? | Notes |
|---|---|---|
| `seller_sku` | **Partial (products only)** | Products scraper extracts when DOM shows `SKU:` / `商家SKU:`. Orders always emit empty `sellerSku`. |
| `sku_id` | **Schema only; always empty in practice** | Orders payload has `skuId` placeholder hard-coded `''`. No product `sku_id` column. |
| `sku_name` | **No** | Not in scraper, converter, ingest known fields, or DB columns. |
| `variation` | **No** | Not modeled anywhere in TK product/order path. |
| Order line items with multiple SKUs | **No** | One row per `order_id` (order header). Explicit future note for `fact_tiktok_order_line`. Multi-item only as total `quantity` like `N 件商品`. |
| Inventory per SKU | **No — product-level stock only** | `stock_qty` is list-row inventory for the **product**, not per SKU/variant. Scraper even skips expand rows labeled `SKU展开`. |

---

## Pipeline map

```
orders page DOM
  -> collectors/tiktok-ads/scripts/scrape-orders-page.js
  -> run-orders.ps1
  -> qingquan-client.ps1 ConvertTo-QingquanOrderIngestItems
  -> POST ingest source=tiktok_orders
  -> backend/app/api/ingest.py _process_tiktok_orders
  -> tk.fact_tiktok_order (005)

product manage DOM
  -> collectors/tiktok-ads/scripts/scrape-products-page.js
  -> run-products.ps1
  -> ConvertTo-QingquanProductIngestItems
  -> source=tiktok_products
  -> _process_tiktok_products
  -> tk.fact_tiktok_product (006)
```

---

## 1) Orders

### Schema — `E:\project\清泉跨境系统（企业级）\backend\migrations\005_tiktok_orders.sql`
- Granularity comment: shop x order_id (order header one row; multi-SKU detail deferred to future `fact_tiktok_order_line`)
- Columns present: `product_name`, `seller_sku`, `sku_id`, `quantity`, `pay_amount`, ...
- Unique key: `(shop_external_id, order_id)` — cannot store multi-SKU lines
- No `sku_name`, no `variation`, no `order_line` table anywhere in migrations

### Scraper raw fields — `...\collectors\tiktok-ads\scripts\scrape-orders-page.js`
Emitted row keys:
`orderId`, `orderStatus`, `payTime`, `createTime`, `createTimeRaw`, `productName`, `sellerSku`, `skuId`, `quantity`, `payAmount`, `shippingStatus`, `buyerRegion`, `buyer`, `currencyHint`, `rawCells`

Important implementation facts:
- `sellerSku: ''` and `skuId: ''` are hard-coded empty in both table parse and order-id-node fallback
- `productName` comes from product column; live UI often only shows `N 件商品`, not title/SKU
- `quantity` parsed from regex for `N 件商品` — order-level piece count, not per-SKU lines
- No expansion of multi-item orders; de-dupe by `orderId` keeps one row/order

### Sample raw payloads
Files:
- `...\logs\orders-debug-27501502216807-20260804-180002.json`
- `...\logs\orders-debug-27328767468273-20260804-180002.json`
- DOM probe: `...\logs\_orders-row-probe.json`, `...\logs\_orders-dom-probe.json`

Observed:
- keys include `sellerSku`, `skuId` but 0 nonempty across sampled rows
- `productName` almost always `"1 件商品"` (or N 件商品)
- `quantity` can be >1 (e.g. 2, 3) but still one header row
- table headers: order/customer/product/status/shipping/total — no SKU column on list page
- probe cells for product column text = `"1 件商品"` only

### Converter — `...\scripts\qingquan-client.ps1` `ConvertTo-QingquanOrderIngestItems`
Maps into ingest payload:
- `order_id`, `order_status`, `pay_time`, `create_time`, `product_name`, `seller_sku`, `sku_id`, `quantity`, `pay_amount`, `currency`, `shipping_status`, `buyer_region`, `source_url`, optional `create_time_raw`
- Does not pass `buyer`, `currencyHint`, `rawCells` as first-class fields
- Idempotency: `tiktok_orders:{storeId}:{orderId}`

### Ingest — `backend\app\api\ingest.py` `_process_tiktok_orders`
- Reads: `seller_sku`/`sellerSku`, `sku_id`/`skuId`, `product_name`/`productName`, `quantity`, etc.
- Writes first-class columns above
- Unknown keys -> `raw_extra` JSONB (converter already strips most extras)
- Does not explode line items; one envelope -> one order header row
- Empty strings become NULL via `or None` for sku fields

### Dropped / not captured (orders)
| Field | At collect | At converter | At ingest/DB |
|---|---|---|---|
| seller_sku | placeholder always empty | sent empty | NULL |
| sku_id | placeholder always empty | sent empty | NULL |
| sku_name | never | never | no column |
| variation | never | never | no column |
| multi-SKU line items | collapsed to qty + N 件商品 | 1 item/order | 1 row/order |
| real product title on list | usually missing in DOM text | n/a | product_name = N 件商品 |
| buyer | scraped | not mapped | lost |
| rawCells | scraped | not mapped | lost |

---

## 2) Products / inventory

### Schema — `...\backend\migrations\006_tiktok_products.sql`
- Granularity: shop x platform product_id (or seller_sku fallback)
- Columns: `product_id`, `product_name`, `seller_sku`, `status`, `stock_qty`, `price`, `currency`, `sales_qty`, `raw_extra`
- Unique: `(shop_external_id, product_id)`
- No `sku_id`, `sku_name`, `variation`, no per-SKU inventory table

### Scraper raw fields — `...\scripts\scrape-products-page.js`
Emitted row keys:
`productId`, `productName`, `sellerSku`, `status`, `stockQty`, `price`, `salesQty`, `currencyHint`, `rawCells`

Extraction:
- `productId` from `ID: <digits>` in product cell
- `sellerSku` from regex for `SKU:` / `商家SKU:`
- `stockQty` from stock column — one number per product row
- `salesQty` from sold count in performance column
- Explicitly skips expand/noise rows matching SKU expand labels
- Price ranges keep first number only
- No `sku_id` / `sku_name` / `variation` / SKU array

Page headers observed in samples:
product / performance / status / stock / retail price / tools / actions

### Sample raw payloads
- `...\logs\products-debug-27501502216807-20260804-182004.json` (Deal): samples often empty sellerSku; stockQty filled (304, 199, 246...)
- `...\logs\products-debug-27328767468273-20260804-182004.json` (Gardena): sellerSku often present e.g. `JMCATJQPJ`, `JMCATMSWJ`; stockQty filled
- `...\logs\products-debug-27501502216807-20260803-182001.json`: mixed sellerSku
- Multi-variant products still one row: price range in rawCells, single aggregated `stockQty`

### Converter — `ConvertTo-QingquanProductIngestItems`
Payload:
`product_id`, `product_name`, `seller_sku`, `status`, `stock_qty`, `price`, `sales_qty`, `currency`, `source_url`
- Fallback product_id: `sku:{sellerSku}` or `name:{productName[:80]}`
- Idempotency: `tiktok_products:{storeId}:{productId}`
- Drops `rawCells`, `currencyHint` (currencyHint only used if no currency)

### Ingest — `_process_tiktok_products`
- Accepts same fields (camelCase aliases)
- Maps `stock_qty`/`stockQty` -> column `stock_qty`
- Unknown -> `raw_extra`
- No SKU child rows

### Dropped / not captured (products)
| Field | Status |
|---|---|
| seller_sku | Captured when list cell contains SKU text; often empty on some shops/rows |
| stock_qty | Yes, product-level inventory |
| inventory per SKU/variant | No (not scraped; expand rows skipped) |
| sku_id / sku_name / variation | No |
| full price range / promo price | Only first money amount kept; remainder not first-class (rawCells dropped before ingest) |
| sales accel tool status | In rawCells only -> dropped at converter |

---

## 3) Related but out of multi-SKU scope
- `tiktok_product_traffic` / content: product_id level, not SKU
- `tiktok_anomaly_task`: has product_id + seller_sku fields for alerts, not line items
- `mock_ingest_tiktok.py`: ads only, no order/product SKU samples
- Roadmap `docs\TK-整站运营数据采集路线图.md`: P2a/P2b marked done at order header / product list grain — does not claim SKU lines

---

## Concrete field name cheat-sheet

### Orders scraper -> ingest -> DB
| Raw (scraper) | Ingest payload | DB column | Live value quality |
|---|---|---|---|
| orderId | order_id | order_id | OK |
| orderStatus | order_status | order_status | OK |
| createTime / createTimeRaw | create_time / create_time_raw | create_time + raw_extra | OK |
| payTime | pay_time | pay_time | usually empty |
| productName | product_name | product_name | usually N 件商品 |
| sellerSku | seller_sku | seller_sku | always empty today |
| skuId | sku_id | sku_id | always empty today |
| quantity | quantity | quantity | order piece count |
| payAmount | pay_amount | pay_amount | OK |
| shippingStatus | shipping_status | shipping_status | logistics blob |
| buyerRegion | buyer_region | buyer_region | empty |
| buyer | (not sent) | - | dropped |
| rawCells | (not sent) | - | dropped |

### Products scraper -> ingest -> DB
| Raw | Ingest | DB | Live value quality |
|---|---|---|---|
| productId | product_id | product_id | OK |
| productName | product_name | product_name | OK (title) |
| sellerSku | seller_sku | seller_sku | partial |
| status | status | status | OK |
| stockQty | stock_qty | stock_qty | product aggregate OK |
| price | price | price | first price only |
| salesQty | sales_qty | sales_qty | OK when sold count present |
| currencyHint | currency | currency | OK |
| rawCells | (not sent) | - | dropped |

Missing entirely: `sku_name`, `variation`, `line_items[]`, `order_line`, per-SKU stock.

---

## Bottom line
Current TikTok product/order collection is header/list grain, not SKU grain.
- DB is ready for order `seller_sku`/`sku_id` and product `seller_sku`/`stock_qty`.
- Collectors do not populate meaningful order SKUs; products get optional seller SKU + product-level stock only.
- Multi-SKU order lines and per-SKU inventory would need new scrape depth (order detail / SKU expand) plus likely `fact_tiktok_order_line` (already noted as future in 005) and/or a SKU inventory fact table.
