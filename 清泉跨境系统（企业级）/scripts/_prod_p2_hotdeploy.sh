#!/usr/bin/env bash
# Hot-fix P2 closeout on prod (run on server after scp)
set -euo pipefail
cd /opt/qingquan

echo "==> fix dirty CONTENT env line if any"
if grep -q '^nFEISHU_BITABLE_TABLE_TK_CONTENT_DAILY=' .env 2>/dev/null; then
  # drop accidental leading-n duplicate; keep clean FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY
  sed -i '/^nFEISHU_BITABLE_TABLE_TK_CONTENT_DAILY=/d' .env
  echo "removed nFEISHU_BITABLE_TABLE_TK_CONTENT_DAILY"
fi
if ! grep -q '^FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY=' .env 2>/dev/null; then
  echo "WARN: FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY missing in .env"
else
  grep '^FEISHU_BITABLE_TABLE_TK_CONTENT_DAILY=' .env | sed 's/=.*/=***/'
fi

echo "==> apply migration 015_tk_anomaly_amz_ops_fields.sql"
if [[ -f backend/migrations/015_tk_anomaly_amz_ops_fields.sql ]]; then
  docker cp backend/migrations/015_tk_anomaly_amz_ops_fields.sql qingquan-db-1:/tmp/015_tk_anomaly_amz_ops_fields.sql
  docker exec qingquan-db-1 psql -U qingquan -d qingquan -v ON_ERROR_STOP=1 -f /tmp/015_tk_anomaly_amz_ops_fields.sql
  docker exec qingquan-db-1 psql -U qingquan -d qingquan -Atc \
    "SELECT column_name FROM information_schema.columns WHERE table_schema='tk' AND table_name='fact_tk_anomaly_task' AND column_name IN ('level_code','description','current_value','needs_boss_decision') ORDER BY 1;"
else
  echo "FATAL missing 015_tk_anomaly_amz_ops_fields.sql"
  exit 1
fi

echo "==> rebuild api worker"
set -a; . ./.env; set +a
cd deploy
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env build api worker
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env up -d api worker
cd /opt/qingquan

echo "==> wait health"
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    echo "API healthy"
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/health
echo

echo "==> openapi content routes"
curl -sS http://127.0.0.1:8000/openapi.json -o /tmp/openapi.json
python3 - <<'PY'
import json
p=json.load(open('/tmp/openapi.json')).get('paths',{})
need=['/api/v1/tk/content','/api/v1/tk/content/anomaly-eval','/api/v1/tk/product-traffic','/api/v1/tk/shop-daily']
for k in need:
    print(('OK ' if k in p else 'MISS'), k)
PY

echo "==> build web"
if ! command -v npm >/dev/null 2>&1; then
  echo "npm missing — skip web build"
else
  cd /opt/qingquan/web
  npm ci || npm install
  npm run build
  cd /opt/qingquan
  ls -la web/dist/index.html
  if ls web/dist/assets/*.js >/dev/null 2>&1; then
    grep -l 'tk-content\|内容分析' web/dist/assets/*.js | head -3 || echo 'WARN dist still no content tab string'
  fi
fi

echo "==> nginx reload"
if [[ -f /opt/qingquan/deploy/nginx-qingquan.jmzlai.com.conf ]]; then
  sudo cp /opt/qingquan/deploy/nginx-qingquan.jmzlai.com.conf /etc/nginx/sites-available/qingquan.jmzlai.com || true
fi
sudo nginx -t && sudo systemctl reload nginx || true

echo "==> smoke anomaly list (no auth expect 401)"
code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/v1/tk/anomaly-tasks || true)
echo "anomaly-tasks http=$code"
code2=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/v1/tk/content/anomaly-eval || true)
echo "content/anomaly-eval http=$code2"

echo "DEPLOY_DONE"
