#!/usr/bin/env bash
# 切新 Base 后：分店表 JSON 进容器 + 清旧映射 + 强制重推体验分
# 前提：api/worker 已用新 .env rebuild + up -d
set -euo pipefail

echo "=== store-tables json into containers (容器内 _REPO_ROOT=/，须放 /config) ==="
docker exec qingquan-api-1 mkdir -p /config
docker cp /opt/qingquan/config/feishu-tk-store-tables.json qingquan-api-1:/config/feishu-tk-store-tables.json
docker exec qingquan-worker-1 mkdir -p /config
docker cp /opt/qingquan/config/feishu-tk-store-tables.json qingquan-worker-1:/config/feishu-tk-store-tables.json

echo "=== map before ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT table_key, table_id, count(*) AS n
FROM public.sync_feishu_map
WHERE table_key LIKE '%experience%' OR table_id LIKE '%SyTlj%' OR table_id LIKE '%9CYd8%'
GROUP BY 1,2 ORDER BY 1,2;
"

echo "=== delete experience maps (force recreate on new base) ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
DELETE FROM public.sync_feishu_map
WHERE table_key = 'tk_experience_daily'
   OR table_id IN ('tblSyTljO6C6tRaY','tbl9CYd8vb4DJaGN');
"

docker cp /tmp/_prod_run_exp_sync.py qingquan-api-1:/tmp/run_exp_sync.py

echo "=== runtime env check ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python - <<'PY'
from app.config import get_settings
s = get_settings()
print("app_id", s.feishu_app_id)
print("tk_token", s.feishu_bitable_app_token_tk)
print("exp_table", s.feishu_bitable_table_tk_experience_daily)
PY

echo "=== force sync experience ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/run_exp_sync.py

echo "=== map after ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT table_key, table_id, count(*) AS n
FROM public.sync_feishu_map
WHERE table_key = 'tk_experience_daily'
GROUP BY 1,2;
"

echo "EXP_RESYNC_NEW_BASE_DONE"
