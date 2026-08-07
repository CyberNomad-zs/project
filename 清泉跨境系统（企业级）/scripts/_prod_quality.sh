#!/usr/bin/env bash
set -euo pipefail
echo "=== shop_daily by date ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT biz_date, count(*), string_agg(DISTINCT shop_name, ',' ORDER BY shop_name) shops, round(sum(coalesce(gmv,0))::numeric,2) gmv FROM tk.fact_tiktok_shop_daily GROUP BY 1 ORDER BY 1 DESC LIMIT 10;"
echo "=== content by date ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT biz_date, count(*), count(DISTINCT shop_external_id) shops, round(sum(coalesce(attributed_gmv,0))::numeric,2) gmv, round(avg(coalesce(impressions,0))::numeric,1) avg_imp FROM tk.fact_tiktok_content_daily GROUP BY 1 ORDER BY 1 DESC;"
echo "=== traffic by date null metrics ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT biz_date, count(*) n, count(*) FILTER (WHERE impressions IS NULL) null_imp, count(*) FILTER (WHERE gmv IS NULL) null_gmv, count(*) FILTER (WHERE cvr IS NULL) null_cvr, count(*) FILTER (WHERE clicks IS NULL) null_clk, round(sum(coalesce(gmv,0))::numeric,2) gmv_sum FROM tk.fact_tiktok_product_traffic_daily GROUP BY 1 ORDER BY 1 DESC;"
echo "=== traffic sample raw_extra keys ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT shop_name, product_id, impressions, clicks, ctr, gmv, cvr, orders_cnt, left(raw_extra::text,200) raw FROM tk.fact_tiktok_product_traffic_daily WHERE biz_date=(SELECT max(biz_date) FROM tk.fact_tiktok_product_traffic_daily) ORDER BY gmv DESC NULLS LAST LIMIT 5;"
echo "=== ads latest ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT biz_date, count(*), round(sum(coalesce(spend, ad_spend, 0))::numeric,2) spend FROM tk.fact_ads_campaign_daily GROUP BY 1 ORDER BY 1 DESC LIMIT 5;" 2>/dev/null || docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT column_name FROM information_schema.columns WHERE table_schema='tk' AND table_name='fact_ads_campaign_daily' ORDER BY 1;"
echo "=== open anomaly by code ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT anomaly_code, count(*) FROM tk.fact_tk_anomaly_task WHERE status IN ('open','in_progress') GROUP BY 1 ORDER BY 2 DESC;"
