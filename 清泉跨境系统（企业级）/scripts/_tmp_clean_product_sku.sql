-- snapshot dirty
SELECT count(*) AS dirty_before
  FROM tk.fact_tiktok_product
 WHERE seller_sku ~ '(浏览|销售|分析|在售|--)'
    OR seller_sku LIKE '%|%--%';

-- clean: take first token before | or -- and keep alnum_- only head
WITH cleaned AS (
  SELECT id,
         seller_sku AS old_sku,
         NULLIF(
           substring(
             regexp_replace(
               split_part(split_part(seller_sku, '|', 1), '--', 1),
               '[^A-Za-z0-9_*-].*$', ''
             ) from '^[A-Za-z0-9][A-Za-z0-9_*-]{0,47}'
           ),
           ''
         ) AS new_sku
    FROM tk.fact_tiktok_product
   WHERE seller_sku IS NOT NULL
     AND btrim(seller_sku) <> ''
     AND (
       seller_sku ~ '(浏览|销售|分析|在售|--)'
       OR seller_sku LIKE '%|%--%'
       OR length(seller_sku) > 48
     )
)
UPDATE tk.fact_tiktok_product p
   SET seller_sku = c.new_sku,
       updated_at = now()
  FROM cleaned c
 WHERE p.id = c.id
   AND c.new_sku IS NOT NULL
   AND c.new_sku IS DISTINCT FROM c.old_sku;

SELECT count(*) AS dirty_after
  FROM tk.fact_tiktok_product
 WHERE seller_sku ~ '(浏览|销售|分析|在售|--)'
    OR seller_sku LIKE '%|%--%';

SELECT count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku)<>'') AS with_sku,
       count(*) AS total
  FROM tk.fact_tiktok_product;

SELECT shop_name, product_id, seller_sku
  FROM tk.fact_tiktok_product
 WHERE seller_sku IS NOT NULL AND btrim(seller_sku)<>''
 ORDER BY updated_at DESC NULLS LAST
 LIMIT 10;
