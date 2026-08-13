#!/usr/bin/env bash
set -euo pipefail
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_name, shop_external_id, biz_date, experience_score,
       product_satisfaction, fulfillment_score, customer_service_score, updated_at
FROM tk.fact_tiktok_experience_daily
ORDER BY updated_at DESC NULLS LAST
LIMIT 10;
"
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_name, creator_key, biz_date, health_score, updated_at
FROM tk.fact_tiktok_creator_health_daily
ORDER BY updated_at DESC NULLS LAST
LIMIT 15;
"
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT count(*) FILTER (WHERE shop_external_id <> 'smoke-shop-exp') AS real_exp,
       count(*) FILTER (WHERE shop_external_id = 'smoke-shop-exp') AS smoke_exp
FROM tk.fact_tiktok_experience_daily;
"
