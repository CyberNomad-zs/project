#!/usr/bin/env bash
set -euo pipefail

echo "=== ingest_raw experience/creator last 20 ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT id::text, source, shop_external_id, biz_date, process_status,
       left(coalesce(error_message,''),100) AS err, received_at
FROM public.ingest_raw
WHERE source IN ('tiktok_experience_daily','tiktok_creator_health_daily','tiktok_creator_violation')
ORDER BY received_at DESC NULLS LAST
LIMIT 20;
"

echo "=== pop-like shop ids in any recent ingest ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT source, shop_external_id, process_status, received_at
FROM public.ingest_raw
WHERE shop_external_id = '27758103898326'
ORDER BY received_at DESC NULLS LAST
LIMIT 10;
"

echo "=== notify flags ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python -c "from app.config import get_settings; s=get_settings(); print('im', s.tk_notify_im); print('wh', s.tk_notify_webhook); print('webhook', bool(s.feishu_bot_webhook_tk_health)); print('im_id', bool(getattr(s,'feishu_im_receive_id',None) or ''))"

echo "DONE3"
