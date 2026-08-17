#!/bin/bash
# TK 21:00 规则 + 飞书驾驶舱同步（清泉服务器 cron，等价于 Windows 侧 tk-p0-post-collect.ps1）
# 规则顺序：ads -> product -> shop -> content -> affiliate -> feishu
# 幂等：规则 upsert open tasks；飞书同步按 content_hash 增量，可重复跑
#
# 为什么先 docker cp：api/worker 镜像不挂载 backend/app，容器内代码可能旧于宿主机源码
# （尤其重建镜像后 affiliate 相关文件会丢失）。每次运行前从宿主机注入最新代码，保证 cron 自愈。

set -u

C=qingquan-api-1
H=/opt/qingquan/backend/app
S=/opt/qingquan/scripts
PYEXEC="docker exec -e PYTHONPATH=/app -w /app $C"

log() { echo "[$(date '+%F %T')] $*"; }

log "===== TK post-collect START ====="

# 1) 注入最新代码（docker cp 幂等，容器重建后自动补齐）
docker cp "$H/domain/tk_anomaly.py"              "$C:/app/app/domain/tk_anomaly.py"
docker cp "$H/domain/tk_content_rules.py"        "$C:/app/app/domain/tk_content_rules.py"
docker cp "$H/domain/tk_product_rules.py"        "$C:/app/app/domain/tk_product_rules.py"
docker cp "$H/domain/tk_affiliate_rules.py"      "$C:/app/app/domain/tk_affiliate_rules.py"
docker cp "$H/jobs/tk_feishu_sync.py"            "$C:/app/app/jobs/tk_feishu_sync.py"
docker cp "$H/jobs/tk_affiliate_anomaly_eval.py" "$C:/app/app/jobs/tk_affiliate_anomaly_eval.py"
docker cp "$H/adapters/feishu/bitable.py"        "$C:/app/app/adapters/feishu/bitable.py"
docker cp "$S/feishu_tk_daily_sync.py"           "$C:/tmp/feishu_tk_daily_sync.py"
# 分店表映射（重建镜像会丢，容器内路径必须是 /config/，见 SERVER.md）
docker exec "$C" mkdir -p /config
docker cp "/opt/qingquan/config/feishu-tk-store-tables.json" "$C:/config/feishu-tk-store-tables.json"
log "code injected (7 py + feishu_tk_daily_sync + store-tables)"

# 2) 5 个异常规则
rc=0
for j in tk_ads_anomaly_eval tk_product_anomaly_eval tk_shop_anomaly_eval tk_content_anomaly_eval tk_affiliate_anomaly_eval; do
  log "run $j"
  $PYEXEC python -m "app.jobs.$j"
  code=$?
  log "$j exit=$code"
  [ "$code" -ne 0 ] && rc=1
done

# 3) 飞书同步 T1/T2/T6/T7/异常
log "run feishu_tk_daily_sync --lookback-days 14"
$PYEXEC python /tmp/feishu_tk_daily_sync.py --lookback-days 14
code=$?
log "feishu_tk_daily_sync exit=$code"
[ "$code" -ne 0 ] && rc=1

# 4) 补跑：达人规则 + 异常任务补同步
# affiliate 采集 20:55 → 入库约 21:03，主跑(21:10)通常已覆盖；若采集慢，这里兜底再跑一次并补推飞书
log "补跑 tk_affiliate_anomaly_eval"
$PYEXEC python -m app.jobs.tk_affiliate_anomaly_eval
code=$?
log "tk_affiliate_anomaly_eval re-run exit=$code"
[ "$code" -ne 0 ] && rc=1

log "补跑 feishu anomaly-only sync"
$PYEXEC python /tmp/feishu_tk_daily_sync.py --anomaly-only --lookback-days 14
code=$?
log "feishu anomaly-only sync exit=$code"
[ "$code" -ne 0 ] && rc=1

log "===== TK post-collect END rc=$rc ====="
exit "$rc"
