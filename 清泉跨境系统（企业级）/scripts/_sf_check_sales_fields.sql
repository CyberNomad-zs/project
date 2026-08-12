-- 销量相关：列名 + 有值样本
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema IN ('tk','public')
  AND (
    column_name ~* '(sale|sold|qty|quantity|unit|order|gmv|revenue|volume|件数|销量)'
    OR column_name ILIKE '%sales%'
  )
ORDER BY table_schema, table_name, ordinal_position;

-- product 表销量类字段
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='tk' AND table_name='fact_tiktok_product'
ORDER BY ordinal_position;

SELECT shop_name,
       count(*) n,
       count(units_sold) FILTER (WHERE units_sold IS NOT NULL) has_units,
       sum(COALESCE(units_sold,0)) units_sum,
       count(*) FILTER (WHERE raw_extra ? 'sales') has_sales_key,
       max(raw_extra->>'source') src_sample
FROM tk.fact_tiktok_product
GROUP BY 1 ORDER BY 1;

-- sellfox profit sku 是否有销量
SELECT column_name FROM information_schema.columns
WHERE table_schema='tk' AND table_name='fact_sellfox_tk_profit_sku'
ORDER BY ordinal_position;

SELECT shop_name, grain, count(*) n,
       sum(COALESCE(sales_qty,0)) sales_qty_sum,
       sum(COALESCE(order_qty,0)) order_qty_sum,
       sum(COALESCE(gross_sales_amount,0)) gmv
FROM tk.fact_sellfox_tk_profit_sku
GROUP BY 1,2;

-- statement
SELECT column_name FROM information_schema.columns
WHERE table_schema='tk' AND table_name='fact_sellfox_tk_statement'
  AND column_name ~* '(qty|sale|unit|order|amount|quantity)'
ORDER BY 1;

SELECT shop_name, count(*) n,
       sum(COALESCE(quantity,0)) qty_sum,
       sum(COALESCE(gross_sales_amount,0)) gmv
FROM tk.fact_sellfox_tk_statement
GROUP BY 1;

-- shop daily / order facts
SELECT table_name FROM information_schema.tables
WHERE table_schema='tk' AND table_name ~* '(order|shop_daily|product|sale)'
ORDER BY 1;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='tk' AND table_name IN (
  'fact_tiktok_shop_daily','fact_tiktok_order','fact_tiktok_order_item',
  'fact_tiktok_product_daily','fact_tiktok_finance_daily'
)
ORDER BY table_name, ordinal_position;
