-- 014 TK 视频内容异常域（P2.3）
-- 依赖：010_tk_anomaly_task.sql · 011_tk_anomaly_types_specialize.sql · 013_tk_content_daily.sql
-- 1) object_type 增加 content
-- 2) dim 写入 content_* 异常码
-- 可重复执行

-- ---------------------------------------------------------------------------
-- 1) 扩 object_type CHECK：+ content
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  cname text;
BEGIN
  SELECT conname INTO cname
  FROM pg_constraint
  WHERE conrelid = 'tk.fact_tk_anomaly_task'::regclass
    AND contype = 'c'
    AND pg_get_constraintdef(oid) ILIKE '%object_type%';
  IF cname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE tk.fact_tk_anomaly_task DROP CONSTRAINT %I', cname);
  END IF;
END $$;

ALTER TABLE tk.fact_tk_anomaly_task
  ADD CONSTRAINT fact_tk_anomaly_task_object_type_check
  CHECK (object_type IN ('product', 'campaign', 'shop', 'order', 'content', 'other'));

COMMENT ON COLUMN tk.fact_tk_anomaly_task.object_type IS
  'product|campaign|shop|order|content|other；content=②视频内容分析域';

-- ---------------------------------------------------------------------------
-- 2) 异常类型字典 · 视频内容
-- ---------------------------------------------------------------------------
INSERT INTO tk.dim_tk_anomaly_type
    (code, name_cn, object_type, severity_default, priority_default, description, sort_order, enabled)
VALUES
    ('content_gmv_drop',       '视频归因GMV骤降', 'content', 'high', 'P1',
     '视频行 attributed_gmv 较上一窗口快照下降超阈（窗口语义，非日历日均摊）', 210, TRUE),
    ('content_play_drop',      '视频播放/曝光崩', 'content', 'high', 'P1',
     'play_count 或 impressions 较上一窗口快照下降超阈', 220, TRUE),
    ('content_imp_no_order',   '视频有曝无单',   'content', 'warn', 'P1',
     '曝光/播放达基线但归因 GMV 与 SKU 订单均为 0', 230, TRUE)
ON CONFLICT (code) DO UPDATE SET
    name_cn          = EXCLUDED.name_cn,
    object_type      = EXCLUDED.object_type,
    severity_default = EXCLUDED.severity_default,
    priority_default = EXCLUDED.priority_default,
    description      = EXCLUDED.description,
    sort_order       = EXCLUDED.sort_order,
    enabled          = EXCLUDED.enabled;

COMMENT ON TABLE tk.dim_tk_anomaly_type IS
    'TK 异常类型字典（011+014：广告/商品/店/健康/财务/视频内容）';
