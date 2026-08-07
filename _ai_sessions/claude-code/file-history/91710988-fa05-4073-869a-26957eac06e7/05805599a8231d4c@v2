-- 023 TK 达人表现异常域（P3.3）
-- 依赖：010_tk_anomaly_task.sql · 014_tk_content_anomaly.sql · 022_tk_affiliate_daily.sql
-- 1) object_type 增加 creator
-- 2) dim 写入 creator_* / affiliate_* 异常码
-- 可重复执行

-- ---------------------------------------------------------------------------
-- 1) 扩 object_type CHECK：+ creator
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
  CHECK (object_type IN (
    'product', 'campaign', 'shop', 'order', 'content', 'creator', 'other'
  ));

COMMENT ON COLUMN tk.fact_tk_anomaly_task.object_type IS
  'product|campaign|shop|order|content|creator|other；creator=③达人表现/联盟域';

-- ---------------------------------------------------------------------------
-- 2) 异常类型字典 · 达人表现
-- ---------------------------------------------------------------------------
INSERT INTO tk.dim_tk_anomaly_type
    (code, name_cn, object_type, severity_default, priority_default, description, sort_order, enabled)
VALUES
    ('creator_invest_no_sale',      '达人有投入无成交', 'creator', 'high', 'P1',
     '预计佣金（已采投入）达基线但归因 GMV/成交件均为 0；投流/寄样金额暂不采勿当 0', 310, TRUE),
    ('creator_gmv_drop',            '达人归因GMV骤降', 'creator', 'high', 'P1',
     '达人行 gmv 较上一窗口快照下降超阈（近7天窗语义，非日历日均摊）', 320, TRUE),
    ('affiliate_creators_sold_drop','动销达人数下降',   'creator', 'warn', 'P1',
     '店级 creators_sold 较上一窗口快照下降超阈', 330, TRUE),
    ('creator_refund_high',         '达人退款异常',     'creator', 'warn', 'P2',
     '达人行退款金额/归因 GMV 超阈（需有 GMV 基线）', 340, TRUE)
ON CONFLICT (code) DO UPDATE SET
    name_cn          = EXCLUDED.name_cn,
    object_type      = EXCLUDED.object_type,
    severity_default = EXCLUDED.severity_default,
    priority_default = EXCLUDED.priority_default,
    description      = EXCLUDED.description,
    sort_order       = EXCLUDED.sort_order,
    enabled          = EXCLUDED.enabled;

COMMENT ON TABLE tk.dim_tk_anomaly_type IS
    'TK 异常类型字典（含广告/商品/店/健康/财务/视频内容/达人表现）';
