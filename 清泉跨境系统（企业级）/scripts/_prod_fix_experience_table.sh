#!/usr/bin/env bash
# Point prod experience sync at the UI table tblSyTljO6C6tRaY and re-sync.
set -euo pipefail
ENV=/opt/qingquan/.env
TARGET=tblSyTljO6C6tRaY
OLD=$(grep '^FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=' "$ENV" | head -1 | cut -d= -f2- || true)
echo "OLD=$OLD"
if grep -q '^FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=' "$ENV"; then
  sudo sed -i "s|^FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=.*|FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=${TARGET}|" "$ENV"
else
  echo "FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=${TARGET}" | sudo tee -a "$ENV" >/dev/null
fi
grep '^FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=' "$ENV"

# restart api so Settings reloads
cd /opt/qingquan/deploy
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env up -d api 2>/dev/null || docker restart qingquan-api-1
sleep 10
curl -sS -m 8 http://127.0.0.1:8000/health; echo

docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python - <<'PY'
from app.config import get_settings
s = get_settings()
print("experience_table", s.feishu_bitable_table_tk_experience_daily)
PY

docker cp /tmp/_prod_run_exp_sync.py qingquan-api-1:/tmp/run_exp_sync.py 2>/dev/null || true
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/run_exp_sync.py
echo "FIX_EXP_TABLE_DONE"
