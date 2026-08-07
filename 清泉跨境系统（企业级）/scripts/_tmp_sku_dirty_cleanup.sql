-- cleanup SKU-expand dirty rows on fact_tiktok_product
\pset pager off
BEGIN;

CREATE TEMP TABLE _dirty_sku_expand AS
SELECT id, shop_external_id, product_id, product_name, shop_name
FROM tk.fact_tiktok_product
WHERE coalesce(product_name, '') ~* '(SKU\s*展开|展开全部|\d+\s*个\s*SKU)'
   OR coalesce(product_id, '') ~* '(SKU\s*展开|展开全部|\d+\s*个\s*SKU)'
   OR product_id LIKE 'name:%SKU%'
   OR product_id LIKE 'name:%展开%';

SELECT count(*) AS will_delete FROM _dirty_sku_expand;
SELECT shop_name, product_id, left(coalesce(product_name,''),40) AS name
FROM _dirty_sku_expand
ORDER BY shop_name, product_id;

DELETE FROM tk.fact_tiktok_product p
USING _dirty_sku_expand d
WHERE p.id = d.id;

SELECT count(*) AS remaining_dirty
FROM tk.fact_tiktok_product
WHERE coalesce(product_name, '') ~* '(SKU\s*展开|展开全部|\d+\s*个\s*SKU)'
   OR coalesce(product_id, '') ~* '(SKU\s*展开|展开全部|\d+\s*个\s*SKU)'
   OR product_id LIKE 'name:%SKU%'
   OR product_id LIKE 'name:%展开%';

SELECT count(*) AS prod_total_after FROM tk.fact_tiktok_product;

COMMIT;
