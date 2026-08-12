#!/usr/bin/env bash
# 切新 Base 后：清 TK 旧映射 + 全量重推 T1/T2/异常/T6/T7 到新 Base（含分店表）
# 前提：api/worker 已用新 .env rebuild；/app/config/feishu-tk-store-tables.json 已 docker cp
set -euo pipefail

echo "=== delete stale TK maps (old base table ids) ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
DELETE FROM public.sync_feishu_map
WHERE table_key IN ('tk_shop_daily','tk_ads_campaign','tk_anomaly_task','tk_content_daily','tk_affiliate_creator_daily');
"

docker cp /opt/qingquan/scripts/feishu_tk_daily_sync.py qingquan-api-1:/tmp/feishu_tk_daily_sync.py

echo "=== full sync lookback 30d ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python /tmp/feishu_tk_daily_sync.py --lookback-days 30

echo "=== map after ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT table_key, table_id, count(*) AS n
FROM public.sync_feishu_map
WHERE table_key LIKE 'tk_%'
GROUP BY 1,2 ORDER BY 1,2;
"

echo "TK_FULL_RESYNC_NEW_BASE_DONE"
