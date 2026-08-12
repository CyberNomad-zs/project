-- inspect + cleanup SKU-expand dirty rows on fact_tiktok_product
\pset pager off

SELECT count(*) AS prod_total FROM tk.fact_tiktok_product;

SELECT count(*) AS dirty
FROM tk.fact_tiktok_product
WHERE coalesce(product_name, '') ~* '(SKU\s*展开|展开全部|\d+\s*个\s*SKU)'
   OR coalesce(product_id, '') ~* '(SKU\s*展开|展开全部|\d+\s*个\s*SKU)'
   OR product_id LIKE 'name:%SKU%'
   OR product_id LIKE 'name:%展开%';

SELECT product_id,
       left(coalesce(product_name, ''), 60) AS name,
       seller_sku,
       status,
       shop_name,
       updated_at
FROM tk.fact_tiktok_product
WHERE coalesce(product_name, '') ~* '(SKU\s*展开|展开全部|\d+\s*个\s*SKU)'
   OR coalesce(product_id, '') ~* '(SKU\s*展开|展开全部|\d+\s*个\s*SKU)'
   OR product_id LIKE 'name:%SKU%'
   OR product_id LIKE 'name:%展开%'
ORDER BY updated_at DESC
LIMIT 50;

SELECT count(*) FILTER (
         WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> ''
       ) AS with_sku,
       count(*) AS total,
       count(*) FILTER (WHERE product_id LIKE 'name:%') AS name_fb,
       count(*) FILTER (WHERE product_id ~ '^\d{15,}$') AS real_pid
FROM tk.fact_tiktok_product;

SELECT count(*) FILTER (
         WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> ''
       ) AS o_sku,
       count(*) FILTER (
         WHERE sku_id IS NOT NULL AND btrim(sku_id) <> ''
       ) AS o_skuid,
       count(*) AS o_total
FROM tk.fact_tiktok_order;
