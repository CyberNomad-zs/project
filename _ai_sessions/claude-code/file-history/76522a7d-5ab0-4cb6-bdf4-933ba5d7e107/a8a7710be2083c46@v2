-- 012 TK 商品卡流量日/窗口快照（P2.1a · 内容分析门禁部分通过）
-- 依赖：008_tk_schema.sql（schema tk 已存在）
-- 粒度：shop × biz_date(窗口锚点) × product_id × channel
-- 语义：页面「近 N 天」等为窗口快照；禁止把 7 日窗口均摊成 7 行日事实
-- 门禁：docs/TK-P2-内容分析POC结论.md · Verdict 🟡 部分通过
-- 本迁移不建 fact_tiktok_content_daily（行级 content_id 未过门）

CREATE SCHEMA IF NOT EXISTS tk;

CREATE TABLE IF NOT EXISTS tk.fact_tiktok_product_traffic_daily (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    biz_date            DATE NOT NULL,
    product_id          TEXT NOT NULL,
    product_name        TEXT,
    channel             TEXT NOT NULL DEFAULT 'product_card',
    impressions         NUMERIC(18, 4),
    clicks              NUMERIC(18, 4),
    ctr                 NUMERIC(18, 6),
    orders_cnt          NUMERIC(18, 4),
    gmv                 NUMERIC(18, 4),
    cvr                 NUMERIC(18, 6),
    customers           NUMERIC(18, 4),
    currency            TEXT DEFAULT 'GBP',
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES public.ingest_raw(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, biz_date, product_id, channel)
);

CREATE INDEX IF NOT EXISTS idx_tk_product_traffic_date
    ON tk.fact_tiktok_product_traffic_daily (biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_product_traffic_shop
    ON tk.fact_tiktok_product_traffic_daily (shop_external_id, biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_product_traffic_product
    ON tk.fact_tiktok_product_traffic_daily (product_id);

COMMENT ON TABLE tk.fact_tiktok_product_traffic_daily IS
  'TK 商品卡流量窗口快照；P2.1a；幂等 shop+biz_date+product+channel；window 等进 raw_extra；禁 7 日均摊';

COMMENT ON COLUMN tk.fact_tiktok_product_traffic_daily.biz_date IS
  '窗口锚点日（采集约定的业务日/窗口结束日），非「近7天拆成7行」';

COMMENT ON COLUMN tk.fact_tiktok_product_traffic_daily.cvr IS
  '曝光到成交转化率；页面可能为 0.12 表示 0.12%';

DROP VIEW IF EXISTS public.fact_tiktok_product_traffic_daily CASCADE;
CREATE OR REPLACE VIEW public.fact_tiktok_product_traffic_daily AS
  SELECT * FROM tk.fact_tiktok_product_traffic_daily;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qingquan') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON tk.fact_tiktok_product_traffic_daily TO qingquan;
    GRANT SELECT ON public.fact_tiktok_product_traffic_daily TO qingquan;
  END IF;
END $$;
