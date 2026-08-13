#!/usr/bin/env bash
set -euo pipefail

echo "=== all experience rows ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_name, shop_external_id, biz_date, experience_score,
       product_satisfaction, fulfillment_score, customer_service_score, updated_at
FROM tk.fact_tiktok_experience_daily
ORDER BY updated_at DESC NULLS LAST;
"

echo "=== pop id lookup ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT * FROM tk.fact_tiktok_experience_daily
WHERE shop_external_id IN ('27758103898326','27501502216807','27328767468273')
   OR shop_name ILIKE '%gardena%' OR shop_name ILIKE '%pop%'
ORDER BY updated_at DESC;
"

echo "=== recent ingest_raw experience ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT id, source, status, left(coalesce(error_message,''),80) AS err, created_at
FROM public.ingest_raw
WHERE source ILIKE '%experience%' OR source ILIKE '%creator_health%'
ORDER BY created_at DESC NULLS LAST
LIMIT 15;
" 2>/dev/null || docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT column_name FROM information_schema.columns
WHERE table_schema='public' AND table_name='ingest_raw'
ORDER BY ordinal_position;
"

echo "=== anomaly columns sample ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT column_name FROM information_schema.columns
WHERE table_schema='tk' AND table_name='fact_tk_anomaly_task'
ORDER BY ordinal_position;
"

echo "=== recent experience anomalies ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT anomaly_code, shop_external_id, status, created_at, updated_at
FROM tk.fact_tk_anomaly_task
WHERE anomaly_code IN (
  'shop_experience_drop','shop_experience_metric_worse',
  'creator_health_drop','creator_violation'
)
ORDER BY created_at DESC NULLS LAST
LIMIT 12;
"

echo "=== notify flags ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python - <<'PY'
from app.config import get_settings
s = get_settings()
print("tk_notify_im", s.tk_notify_im)
print("tk_notify_webhook", s.tk_notify_webhook)
print("webhook_set", bool(s.feishu_bot_webhook_tk_health))
print("im_receive_set", bool(getattr(s, "feishu_im_receive_id", None) or ""))
PY

echo "DONE2"
