#!/usr/bin/env bash
set -euo pipefail

echo "=== map before ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT table_key, table_id, count(*) AS n
FROM public.sync_feishu_map
WHERE table_key LIKE '%experience%' OR table_id LIKE '%SyTlj%' OR table_id LIKE '%9CYd8%'
GROUP BY 1,2
ORDER BY 1,2;
"

echo "=== delete experience maps (force recreate) ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
DELETE FROM public.sync_feishu_map
WHERE table_key = 'tk_experience_daily'
   OR table_id IN ('tblSyTljO6C6tRaY','tbl9CYd8vb4DJaGN');
"

# ensure hot files
docker cp /tmp/bitable.py qingquan-api-1:/app/app/adapters/feishu/bitable.py
docker cp /tmp/tk_feishu_sync.py qingquan-api-1:/app/app/jobs/tk_feishu_sync.py
docker cp /tmp/config.py qingquan-api-1:/app/app/config.py
docker cp /tmp/_prod_run_exp_sync.py qingquan-api-1:/tmp/run_exp_sync.py

echo "env:"
grep '^FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=' /opt/qingquan/.env

docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python - <<'PY'
from app.config import get_settings
print("runtime table", get_settings().feishu_bitable_table_tk_experience_daily)
PY

echo "=== force sync ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/run_exp_sync.py

echo "=== map after ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT table_key, table_id, count(*) AS n
FROM public.sync_feishu_map
WHERE table_key = 'tk_experience_daily'
GROUP BY 1,2;
"

echo "FORCE_RESYNC_DONE"
