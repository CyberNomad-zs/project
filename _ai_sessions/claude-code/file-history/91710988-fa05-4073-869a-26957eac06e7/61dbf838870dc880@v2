-- 019 TK 健康分异常类型补全（下降提醒）
-- 依赖：011_tk_anomaly_types_specialize.sql
-- 可重复执行

INSERT INTO tk.dim_tk_anomaly_type
    (code, name_cn, object_type, severity_default, priority_default, description, sort_order, enabled)
VALUES
    ('shop_health_drop', '店铺健康分下降', 'shop', 'high', 'P1',
     '账号健康分较上次快照任意下降即提醒（群机器人+异常任务）', 155, TRUE),
    ('shop_health_low',  '店铺健康分低',   'shop', 'critical', 'P0',
     '健康分 ≤ 内部红线（默认 150）', 160, TRUE)
ON CONFLICT (code) DO UPDATE SET
    name_cn          = EXCLUDED.name_cn,
    object_type      = EXCLUDED.object_type,
    severity_default = EXCLUDED.severity_default,
    priority_default = EXCLUDED.priority_default,
    description      = EXCLUDED.description,
    sort_order       = EXCLUDED.sort_order,
    enabled          = TRUE;
