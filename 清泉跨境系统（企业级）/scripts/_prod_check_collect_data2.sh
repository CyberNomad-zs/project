#!/usr/bin/env bash
set -euo pipefail
echo "=== experience all counts by shop ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_external_id, shop_name, count(*), max(updated_at) AS max_upd, max(experience_score) AS max_score
FROM tk.fact_tiktok_experience_daily
GROUP BY 1,2 ORDER BY max_upd DESC NULLS LAST;
"
echo "=== creator all counts ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT shop_external_id, shop_name, count(*), max(updated_at) AS max_upd
FROM tk.fact_tiktok_creator_health_daily
GROUP BY 1,2 ORDER BY max_upd DESC NULLS LAST;
"
echo "=== recent ingest_raw sources ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT source, status, count(*), max(created_at) AS max_created
FROM public.ingest_raw
WHERE created_at > now() - interval '6 hours'
GROUP BY 1,2 ORDER BY max_created DESC NULLS LAST
LIMIT 30;
"
echo "=== latest experience payloads in ingest if any ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT id, source, status, created_at, left(coalesce(payload::text, raw::text, ''), 200) AS snip
FROM public.ingest_raw
WHERE created_at > now() - interval '6 hours'
  AND (source ILIKE '%experience%' OR source ILIKE '%creator%')
ORDER BY created_at DESC LIMIT 10;
" 2>/dev/null || docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "\d public.ingest_raw"
