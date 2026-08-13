#!/usr/bin/env bash
set -euo pipefail
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_external_id, process_status,
       left(payload::text, 800) AS payload_head
FROM public.ingest_raw
WHERE id = '77ad3c0a-3bb7-4b36-979f-e9b273dd0dba';
"
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT id, name, external_id, platform
FROM public.shops
WHERE external_id = '27758103898326' OR name ILIKE '%gardena%' OR name ILIKE '%pop%'
LIMIT 20;
" 2>/dev/null || docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT table_name FROM information_schema.tables
WHERE table_schema IN ('public','tk') AND table_name ILIKE '%shop%'
ORDER BY 1;
"
