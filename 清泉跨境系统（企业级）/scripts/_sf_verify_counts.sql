SELECT 'profit_shop' t, shop_name, sellfox_shop_id, period_start, period_end,
       gross_sales_amount, settlement_amount, gross_profit, ads_cost, currency
FROM tk.fact_sellfox_tk_profit_shop;

SELECT shop_name, sellfox_shop_id, grain, count(*) n,
       sum(gross_sales_amount) gmv, sum(settlement_amount) settle, sum(ads_cost) ads
FROM tk.fact_sellfox_tk_profit_sku
GROUP BY 1,2,3 ORDER BY 1,3;

SELECT shop_name, count(*) n, min(statement_date), max(statement_date),
       sum(settlement_amount) settle, sum(gross_sales_amount) gmv
FROM tk.fact_sellfox_tk_statement
GROUP BY 1 ORDER BY 1;

SELECT shop_name, count(*) FROM tk.fact_tiktok_finance_daily
WHERE raw_extra->>'source'='sellfox'
GROUP BY 1 ORDER BY 1;

SELECT shop_name, count(*) FROM tk.fact_tiktok_product
WHERE raw_extra->>'source'='sellfox'
GROUP BY 1 ORDER BY 1;

SELECT status, stats, error_message, started_at, finished_at
FROM tk.sellfox_sync_run ORDER BY started_at DESC LIMIT 1;

SELECT name, external_shop_id, meta->>'sellfox_shop_id' sf, meta->>'sellfox_shop_code' code
FROM shop WHERE platform='tiktok' ORDER BY name;
