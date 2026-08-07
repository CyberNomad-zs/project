#!/usr/bin/env bash
# Hot-deploy freshness + anomaly UI bits (api code only; web built separately).
set -euo pipefail
cd /opt/qingquan
set -a
# shellcheck disable=SC1091
. ./.env
set +a
cd deploy
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env build api worker
docker compose -p qingquan -f docker-compose.prod.yml --env-file ../.env up -d api worker
echo "--- wait health ---"
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf http://127.0.0.1:8000/health >/dev/null; then
    curl -sS http://127.0.0.1:8000/health
    echo
    exit 0
  fi
  sleep 3
done
echo "health not ready" >&2
exit 1
