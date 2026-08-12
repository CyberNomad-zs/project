#!/usr/bin/env bash
set -euo pipefail
echo "== shop_daily gaps =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT d::date AS day, coalesce(s.n,0) n, coalesce(s.shops,0) shops FROM generate_series(current_date-10, current_date, '1 day') d LEFT JOIN (SELECT biz_date, count(*) n, count(DISTINCT shop_external_id) shops FROM tk.fact_tiktok_shop_daily GROUP BY 1) s ON s.biz_date=d::date ORDER BY 1;"
echo "== ads freshness =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT max(biz_date), count(*), round(sum(spend)::numeric,2) FROM tk.fact_ads_campaign_daily;"
echo "== content/traffic anchors =="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "SELECT 'content' t, biz_date, count(*) FROM tk.fact_tiktok_content_daily GROUP BY 2 UNION ALL SELECT 'traffic', biz_date, count(*) FROM tk.fact_tiktok_product_traffic_daily GROUP BY 2 ORDER BY 1,2;"
echo "== feishu env tables =="
grep -E 'FEISHU_BITABLE_TABLE_TK' /opt/qingquan/.env | sed 's/=.*/=***/'
echo "== scheduled tasks note local N/A =="
echo "== openapi content routes ok =="
curl -sS http://127.0.0.1:8000/openapi.json -o /tmp/o.json
python3 -c "import json;p=json.load(open('/tmp/o.json'))['paths'];print([k for k in p if 'content' in k or 'traffic' in k or 'shop-daily' in k])"