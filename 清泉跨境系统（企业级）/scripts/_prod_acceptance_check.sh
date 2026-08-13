#!/usr/bin/env bash
set -euo pipefail
echo "=== 1 health ==="
curl -sS -m 8 http://127.0.0.1:8000/health; echo

echo "=== 2 notify env (presence) ==="
ENV=/opt/qingquan/.env
for k in TK_NOTIFY_IM TK_NOTIFY_WEBHOOK FEISHU_BOT_WEBHOOK_TK_HEALTH FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY FEISHU_IM_RECEIVE_ID; do
  if grep -qE "^${k}=" "$ENV" 2>/dev/null; then
    v=$(grep "^${k}=" "$ENV" | head -1 | cut -d= -f2-)
    if [ -z "$v" ]; then echo "$k=EMPTY"
    elif [ "$k" = "FEISHU_BOT_WEBHOOK_TK_HEALTH" ] || [ "$k" = "FEISHU_IM_RECEIVE_ID" ]; then echo "$k=SET"
    else echo "$k=$v"
    fi
  else
    echo "$k=MISSING"
  fi
done

echo "=== 3 runtime settings ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python - <<'PY'
from app.config import get_settings
s = get_settings()
print("tk_notify_im", s.tk_notify_im)
print("tk_notify_webhook", s.tk_notify_webhook)
print("webhook_configured", bool(s.feishu_bot_webhook_tk_health))
print("experience_table", (s.feishu_bitable_table_tk_experience_daily or "")[:20], "len", len(s.feishu_bitable_table_tk_experience_daily or ""))
print("im_receive", bool(s.feishu_im_receive_id))
PY

echo "=== 4 table counts ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT 'experience_daily' AS t, count(*) FROM tk.fact_tiktok_experience_daily
UNION ALL SELECT 'creator_health_daily', count(*) FROM tk.fact_tiktok_creator_health_daily
UNION ALL SELECT 'creator_violation', count(*) FROM tk.fact_tiktok_creator_violation
UNION ALL SELECT 'health_daily', count(*) FROM tk.fact_tiktok_health_daily
UNION ALL SELECT 'review', count(*) FROM tk.fact_tiktok_review
UNION ALL SELECT 'violation', count(*) FROM tk.fact_tiktok_violation;
"

echo "=== 5 recent experience (top 5) ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_name, shop_external_id, biz_date, experience_score, product_satisfaction, fulfillment_score, customer_service_score, updated_at
FROM tk.fact_tiktok_experience_daily
ORDER BY updated_at DESC NULLS LAST LIMIT 5;
"

echo "=== 6 recent creator health (top 8) ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_name, creator_key, biz_date, health_score, updated_at
FROM tk.fact_tiktok_creator_health_daily
ORDER BY updated_at DESC NULLS LAST LIMIT 8;
"

echo "=== 7 code files present ==="
for f in \
  /opt/qingquan/backend/app/domain/notify_dual.py \
  /opt/qingquan/backend/app/domain/tk_experience_rules.py \
  /opt/qingquan/backend/app/domain/tk_creator_health_rules.py \
  /opt/qingquan/backend/migrations/024_tk_experience_creator_health.sql
do
  if [ -f "$f" ]; then echo "OK $f"; else echo "MISS $f"; fi
done

echo "=== 8 dry-run rules ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python -m app.jobs.tk_experience_anomaly_eval --dry-run 2>/dev/null | tail -25
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python -m app.jobs.tk_creator_health_anomaly_eval --dry-run 2>/dev/null | tail -25

echo "ACCEPTANCE_CHECK_DONE"
