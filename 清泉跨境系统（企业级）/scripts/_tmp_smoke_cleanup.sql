DELETE FROM tk.fact_tiktok_order_line WHERE seller_sku = 'SMOKE-SKU-1';
DELETE FROM public.ingest_record
 WHERE idempotency_key LIKE 'smoke-oline-%'
    OR idempotency_key LIKE 'smoke-noise-%';
SELECT count(*) AS order_lines FROM tk.fact_tiktok_order_line;
SELECT count(*) AS dirty
  FROM tk.fact_tiktok_product
 WHERE product_id LIKE 'name:%SKU%'
    OR coalesce(product_name, '') LIKE '%SKU展开%';
