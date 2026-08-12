SELECT count(DISTINCT order_id) AS orders_with_lines,
       count(*) AS lines
  FROM tk.fact_tiktok_order_line
 WHERE shop_external_id = '27328767468273';
SELECT count(*) AS header_with_sku
  FROM tk.fact_tiktok_order
 WHERE shop_external_id = '27328767468273'
   AND seller_sku IS NOT NULL AND btrim(seller_sku) <> '';
