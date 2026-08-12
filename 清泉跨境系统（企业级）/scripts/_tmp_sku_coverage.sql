-- SKU coverage snapshot
SELECT 'product' AS kind,
       count(*) AS total,
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '') AS with_seller_sku,
       count(*) FILTER (WHERE product_id IS NOT NULL AND product_id !~ '^name:') AS with_pid
FROM tk.fact_tiktok_product
UNION ALL
SELECT 'order',
       count(*),
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> ''),
       count(*) FILTER (WHERE sku_id IS NOT NULL AND btrim(sku_id) <> '')
FROM tk.fact_tiktok_order
UNION ALL
SELECT 'order_line',
       count(*),
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> ''),
       count(*) FILTER (WHERE sku_id IS NOT NULL AND btrim(sku_id) <> '')
FROM tk.fact_tiktok_order_line;

SELECT shop_name, count(*) AS n,
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '') AS with_sku
FROM tk.fact_tiktok_product
GROUP BY 1 ORDER BY n DESC;

SELECT shop_name, count(*) AS n,
       count(*) FILTER (WHERE seller_sku IS NOT NULL AND btrim(seller_sku) <> '') AS with_sku,
       count(*) FILTER (WHERE product_name ~ '件商品') AS placeholder_name
FROM tk.fact_tiktok_order
GROUP BY 1 ORDER BY n DESC
LIMIT 20;

-- sample empty product rows
SELECT shop_name, product_id, left(product_name,40) AS name, seller_sku
FROM tk.fact_tiktok_product
WHERE seller_sku IS NULL OR btrim(seller_sku)=''
ORDER BY updated_at DESC NULLS LAST
LIMIT 15;

-- sample empty order rows
SELECT shop_name, order_id, left(coalesce(product_name,''),40) AS name, seller_sku, sku_id
FROM tk.fact_tiktok_order
WHERE seller_sku IS NULL OR btrim(seller_sku)=''
ORDER BY updated_at DESC NULLS LAST
LIMIT 15;
