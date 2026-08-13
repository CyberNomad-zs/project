#!/usr/bin/env bash
set -euo pipefail

echo "=== D: experience anomaly eval (smoke real notify) ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 \
  python -m app.jobs.tk_experience_anomaly_eval --shop-external-id smoke-shop-exp
echo "EVAL_EXIT:$?"

echo "=== C: real experience rows ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_name, shop_external_id, biz_date, experience_score,
       product_satisfaction, fulfillment_score, customer_service_score, updated_at
FROM tk.fact_tiktok_experience_daily
WHERE shop_external_id != 'smoke-shop-exp'
ORDER BY updated_at DESC;
"

echo "=== C: real creator_health rows ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_name, creator_key, biz_date, health_score, updated_at
FROM tk.fact_tiktok_creator_health_daily
WHERE shop_external_id != 'smoke-shop-exp'
ORDER BY updated_at DESC;
"

echo "=== D: recent experience/creator anomaly tasks ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT anomaly_code, shop_external_id, status, left(coalesce(title,''), 60) AS title, created_at
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
print("im_receive_set", bool(getattr(s, "feishu_im_receive_id", None)))
PY

echo "DOCX_GATE_FINISH_DONE"
