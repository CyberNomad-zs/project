#!/usr/bin/env bash
# Hot-deploy Python modules into running api/worker containers (no full rebuild).
set -euo pipefail
ROOT=/opt/qingquan
API=qingquan-api-1
WRK=qingquan-worker-1

copy_into() {
  local ctn="$1"
  docker cp "$ROOT/backend/app/domain/notify_dual.py" "$ctn:/app/app/domain/notify_dual.py"
  docker cp "$ROOT/backend/app/domain/tk_experience_rules.py" "$ctn:/app/app/domain/tk_experience_rules.py"
  docker cp "$ROOT/backend/app/domain/tk_creator_health_rules.py" "$ctn:/app/app/domain/tk_creator_health_rules.py"
  docker cp "$ROOT/backend/app/domain/tk_health_rules.py" "$ctn:/app/app/domain/tk_health_rules.py"
  docker cp "$ROOT/backend/app/domain/tk_review_rules.py" "$ctn:/app/app/domain/tk_review_rules.py"
  docker cp "$ROOT/backend/app/domain/tk_violation_rules.py" "$ctn:/app/app/domain/tk_violation_rules.py"
  docker cp "$ROOT/backend/app/adapters/feishu/im.py" "$ctn:/app/app/adapters/feishu/im.py"
  docker cp "$ROOT/backend/app/adapters/feishu/bitable.py" "$ctn:/app/app/adapters/feishu/bitable.py"
  docker cp "$ROOT/backend/app/config.py" "$ctn:/app/app/config.py"
  docker cp "$ROOT/backend/app/api/ingest.py" "$ctn:/app/app/api/ingest.py"
  docker cp "$ROOT/backend/app/jobs/tk_feishu_sync.py" "$ctn:/app/app/jobs/tk_feishu_sync.py"
  docker cp "$ROOT/backend/app/jobs/tk_experience_anomaly_eval.py" "$ctn:/app/app/jobs/tk_experience_anomaly_eval.py"
  docker cp "$ROOT/backend/app/jobs/tk_creator_health_anomaly_eval.py" "$ctn:/app/app/jobs/tk_creator_health_anomaly_eval.py"
}

echo "=== copy into api ==="
copy_into "$API"
echo "=== copy into worker ==="
copy_into "$WRK"

echo "=== restart api/worker ==="
cd "$ROOT/deploy"
set -a; . "$ROOT/.env"; set +a
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env restart api worker

sleep 3
echo "=== health ==="
curl -sS -m 10 http://127.0.0.1:8000/health; echo

echo "=== import smoke inside api ==="
docker exec -e PYTHONPATH=/app -w /app "$API" python -c "
from app.domain import notify_dual, tk_experience_rules, tk_creator_health_rules
from app.adapters.feishu import im
from app.config import get_settings
s=get_settings()
print('notify_dual', bool(notify_dual))
print('im_receive_set', bool(getattr(s,'feishu_im_receive_id','') or getattr(s,'feishu_im_user_id_songmin','')))
print('webhook_set', bool(getattr(s,'feishu_bot_webhook_tk_health','')))
print('experience_table', bool(getattr(s,'feishu_bitable_table_tk_experience_daily','')))
print('IMPORT_OK')
"

echo "=== dry-run experience eval ==="
docker exec -e PYTHONPATH=/app -w /app "$API" python -m app.jobs.tk_experience_anomaly_eval --dry-run || true
echo "=== dry-run creator health eval ==="
docker exec -e PYTHONPATH=/app -w /app "$API" python -m app.jobs.tk_creator_health_anomaly_eval --dry-run || true

echo "HOTDEPLOY_OK"
