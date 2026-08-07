\dt tk.*
SELECT platform, external_shop_id, name, meta FROM shop WHERE platform = 'tiktok' ORDER BY name;
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'tk' AND table_name = 'fact_tiktok_finance_daily'
ORDER BY ordinal_position;
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'shop'
ORDER BY ordinal_position;
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name ILIKE '%sellfox%' OR table_name ILIKE '%finance%' OR table_name ILIKE '%profit%'
ORDER BY 1, 2;
