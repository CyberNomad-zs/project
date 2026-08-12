#!/usr/bin/env bash
set -euo pipefail
echo "=== tables ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT tablename FROM pg_tables WHERE schemaname='tk' AND (tablename LIKE '%experience%' OR tablename LIKE '%creator_health%' OR tablename LIKE '%creator_violation%') ORDER BY 1;"

echo "=== severity values ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT DISTINCT severity_default FROM tk.dim_tk_anomaly_type;"

echo "=== seed anomaly types (high not medium) ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -v ON_ERROR_STOP=1 -c "
INSERT INTO tk.dim_tk_anomaly_type
    (code, name_cn, object_type, severity_default, priority_default, description, sort_order, enabled)
VALUES
    ('shop_experience_drop', '店铺体验分下降', 'shop', 'high', 'P1',
     '店铺体验分总分较上次快照任意下降', 162, TRUE),
    ('shop_experience_metric_worse', '店铺体验分项变差', 'shop', 'high', 'P1',
     '体验分三模块或子指标较上次任意变差', 163, TRUE),
    ('creator_health_drop', '达人健康分下降', 'creator', 'high', 'P1',
     '达人账号健康评分较上次任意下降', 164, TRUE),
    ('creator_violation', '达人新增违规', 'creator', 'high', 'P0',
     '达人健康页首次入库的违规记录', 165, TRUE)
ON CONFLICT (code) DO UPDATE SET
    name_cn          = EXCLUDED.name_cn,
    object_type      = EXCLUDED.object_type,
    severity_default = EXCLUDED.severity_default,
    priority_default = EXCLUDED.priority_default,
    description      = EXCLUDED.description,
    sort_order       = EXCLUDED.sort_order,
    enabled          = TRUE;
"

echo "=== codes ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT code, severity_default, priority_default FROM tk.dim_tk_anomaly_type WHERE code IN ('shop_experience_drop','shop_experience_metric_worse','creator_health_drop','creator_violation') ORDER BY 1;"

echo "SEED_OK"
