-- 013 TK 视频内容行级窗口快照（P2.1b · content_id 门禁已过）
-- 依赖：008_tk_schema.sql（schema tk 已存在）
-- 粒度：shop × biz_date(窗口锚点) × channel × content_id
-- 语义：页面「近 N 天」等为窗口快照；禁止把 7 日窗口均摊成 7 行日事实
-- 门禁：docs/TK-P2-内容分析POC结论.md · Verdict 🟢 采集双侧通过（2026-08-05）
-- content_id 稳定键 = video-detail-item?id=…；勿用标题内商品长数字冒充

CREATE SCHEMA IF NOT EXISTS tk;

CREATE TABLE IF NOT EXISTS tk.fact_tiktok_content_daily (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id                 UUID REFERENCES public.shop(id),
    shop_external_id        TEXT NOT NULL,
    shop_name               TEXT,
    biz_date                DATE NOT NULL,
    channel                 TEXT NOT NULL DEFAULT 'short_video',
    content_id              TEXT NOT NULL,
    content_title           TEXT,
    product_id              TEXT,
    attributed_gmv          NUMERIC(18, 4),
    attributed_sku_orders   NUMERIC(18, 4),
    attributed_units        NUMERIC(18, 4),
    play_count              NUMERIC(18, 4),
    impressions             NUMERIC(18, 4),
    clicks                  NUMERIC(18, 4),
    ctr                     NUMERIC(18, 6),
    cvr                     NUMERIC(18, 6),
    customers               NUMERIC(18, 4),
    currency                TEXT DEFAULT 'GBP',
    source_url              TEXT,
    raw_extra               JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at            TIMESTAMPTZ,
    ingest_id               UUID REFERENCES public.ingest_raw(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, biz_date, channel, content_id)
);

CREATE INDEX IF NOT EXISTS idx_tk_content_daily_date
    ON tk.fact_tiktok_content_daily (biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_content_daily_shop
    ON tk.fact_tiktok_content_daily (shop_external_id, biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_content_daily_content
    ON tk.fact_tiktok_content_daily (content_id);

CREATE INDEX IF NOT EXISTS idx_tk_content_daily_product
    ON tk.fact_tiktok_content_daily (product_id)
    WHERE product_id IS NOT NULL;

COMMENT ON TABLE tk.fact_tiktok_content_daily IS
  'TK 视频内容行级窗口快照；P2.1b；幂等 shop+biz_date+channel+content_id；window/published_at 进 raw_extra；禁 7 日均摊';

COMMENT ON COLUMN tk.fact_tiktok_content_daily.biz_date IS
  '窗口锚点日（采集约定的业务日/窗口结束日），非「近7天拆成7行」';

COMMENT ON COLUMN tk.fact_tiktok_content_daily.content_id IS
  '稳定视频 ID，优先 video-detail-item?id=；禁止标题商品数字冒充';

COMMENT ON COLUMN tk.fact_tiktok_content_daily.channel IS
  'short_video | live | photo | other；默认 short_video';

DROP VIEW IF EXISTS public.fact_tiktok_content_daily CASCADE;
CREATE OR REPLACE VIEW public.fact_tiktok_content_daily AS
  SELECT * FROM tk.fact_tiktok_content_daily;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qingquan') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON tk.fact_tiktok_content_daily TO qingquan;
    GRANT SELECT ON public.fact_tiktok_content_daily TO qingquan;
  END IF;
END $$;
