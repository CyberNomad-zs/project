-- 清理首轮赛狐同步写入的颜色/规格文案 seller_sku（无正规编码时置空，等 scrape/下次 API 补）
UPDATE tk.fact_tiktok_product p
SET seller_sku = NULL,
    updated_at = now()
WHERE p.seller_sku IS NOT NULL
  AND btrim(p.seller_sku) <> ''
  AND (
    -- 整串每个 | 分段都是颜色/纯英文无数字
    (
      SELECT bool_and(
        seg ~* '^(black|white|pink|gray|grey|green|purple|red|blue|yellow|orange|brown|beige|gold|silver|clear)([ \-/].*)?$'
        OR (seg ~* '^[A-Za-z][A-Za-z \-/]{1,30}$' AND seg !~ '\d')
      )
      FROM unnest(string_to_array(p.seller_sku, '|')) AS seg
      WHERE btrim(seg) <> ''
    )
  );

-- 去掉串里的颜色分段，保留编码分段（如 black and red|JMCATX → JMCATX）
UPDATE tk.fact_tiktok_product p
SET seller_sku = cleaned.sku,
    updated_at = now()
FROM (
  SELECT id,
         nullif(
           array_to_string(
             ARRAY(
               SELECT btrim(seg)
               FROM unnest(string_to_array(seller_sku, '|')) AS seg
               WHERE btrim(seg) <> ''
                 AND NOT (
                   btrim(seg) ~* '^(black|white|pink|gray|grey|green|purple|red|blue|yellow|orange|brown|beige|gold|silver|clear)([ \-/].*)?$'
                   OR (btrim(seg) ~* '^[A-Za-z][A-Za-z \-/]{1,30}$' AND btrim(seg) !~ '\d')
                 )
             ),
             '|'
           ),
           ''
         ) AS sku
  FROM tk.fact_tiktok_product
  WHERE seller_sku IS NOT NULL AND seller_sku LIKE '%|%'
) cleaned
WHERE p.id = cleaned.id
  AND cleaned.sku IS DISTINCT FROM p.seller_sku
  AND cleaned.sku IS NOT NULL;
