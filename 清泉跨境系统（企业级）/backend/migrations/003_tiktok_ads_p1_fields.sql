-- 003 TikTok 广告 P1 字段（预算/目标ROI/状态/CPA/净成本/开关）
-- 依赖：001_init.sql

ALTER TABLE fact_ads_campaign_daily
    ADD COLUMN IF NOT EXISTS plan_status TEXT,
    ADD COLUMN IF NOT EXISTS delivery_status TEXT,
    ADD COLUMN IF NOT EXISTS daily_budget NUMERIC(18, 4),
    ADD COLUMN IF NOT EXISTS target_roi NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS net_cost NUMERIC(18, 4),
    ADD COLUMN IF NOT EXISTS avg_order_cost NUMERIC(18, 4);

COMMENT ON COLUMN fact_ads_campaign_daily.plan_status IS '投放开关 on|off|unknown';
COMMENT ON COLUMN fact_ads_campaign_daily.delivery_status IS '计划状态文案，如已生效';
COMMENT ON COLUMN fact_ads_campaign_daily.daily_budget IS '日预算/当前预算';
COMMENT ON COLUMN fact_ads_campaign_daily.target_roi IS '目标 ROI';
COMMENT ON COLUMN fact_ads_campaign_daily.net_cost IS '净成本';
COMMENT ON COLUMN fact_ads_campaign_daily.avg_order_cost IS '平均下单成本 CPA';
