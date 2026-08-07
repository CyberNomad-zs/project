-- product.sales_qty
SELECT shop_name,
       count(*) n,
       count(sales_qty) FILTER (WHERE sales_qty IS NOT NULL) has_sales,
       count(*) FILTER (WHERE COALESCE(sales_qty,0) > 0) gt0,
       sum(COALESCE(sales_qty,0)) sales_sum,
       max(raw_extra->>'source') src
FROM tk.fact_tiktok_product
GROUP BY 1 ORDER BY 1;

-- sellfox profit shop
SELECT shop_name, period_start, period_end, sales_qty, return_qty, gross_sales_amount
FROM tk.fact_sellfox_tk_profit_shop;

-- sellfox profit sku
SELECT shop_name, grain,
       count(*) n,
       count(*) FILTER (WHERE COALESCE(sales_qty,0)>0) gt0,
       sum(COALESCE(sales_qty,0)) sales_sum,
       sum(COALESCE(return_qty,0)) return_sum,
       sum(COALESCE(gross_sales_amount,0)) gmv
FROM tk.fact_sellfox_tk_profit_sku
GROUP BY 1,2 ORDER BY 1,2;

-- statement sales_qty
SELECT shop_name,
       count(*) n,
       count(*) FILTER (WHERE COALESCE(sales_qty,0)>0) gt0,
       sum(COALESCE(sales_qty,0)) sales_sum,
       sum(COALESCE(return_qty,0)) return_sum
FROM tk.fact_sellfox_tk_statement
GROUP BY 1 ORDER BY 1;

-- shop daily (采集)
SELECT shop_name,
       count(*) n,
       min(biz_date), max(biz_date),
       sum(COALESCE(orders_cnt,0)) orders,
       sum(COALESCE(gmv,0)) gmv
FROM tk.fact_tiktok_shop_daily
GROUP BY 1 ORDER BY 1;

-- orders
SELECT shop_name,
       count(*) n,
       sum(COALESCE(quantity,0)) qty,
       sum(COALESCE(pay_amount,0)) pay
FROM tk.fact_tiktok_order
GROUP BY 1 ORDER BY 1;

-- product traffic daily
SELECT shop_name,
       count(*) n,
       sum(COALESCE(orders_cnt,0)) orders,
       sum(COALESCE(gmv,0)) gmv
FROM tk.fact_tiktok_product_traffic_daily
GROUP BY 1 ORDER BY 1;

-- sample product with sales
SELECT shop_name, product_id, seller_sku, sales_qty, stock_qty, raw_extra->>'source' src
FROM tk.fact_tiktok_product
WHERE COALESCE(sales_qty,0) > 0
ORDER BY sales_qty DESC NULLS LAST
LIMIT 8;
