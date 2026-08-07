SELECT count(*) AS order_lines,
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '') AS with_sku
  FROM tk.fact_tiktok_order_line;
SELECT count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '') AS order_with_sku,
       count(*) FILTER (WHERE sku_id IS NOT NULL AND btrim(sku_id) <> '') AS order_with_skuid
  FROM tk.fact_tiktok_order;
