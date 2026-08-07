COPY (
  SELECT shop_external_id, shop_name, order_id
    FROM tk.fact_tiktok_order
   WHERE order_id ~ '^\d{15,22}$'
     AND (seller_sku IS NULL OR btrim(seller_sku) = '')
     AND shop_external_id IN ('27328767468273', '27501502216807')
   ORDER BY shop_external_id, updated_at DESC NULLS LAST, order_id
) TO STDOUT WITH CSV HEADER;
