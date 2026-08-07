-- 022 TK 达人表现（联盟中心·表现）窗口快照（P3.1 · 门禁 G1–G4 已过）
-- 依赖：008_tk_schema.sql（schema tk 已存在）
-- 粒度：
--   店级：shop × biz_date(窗口锚点) × window_label
--   达人：shop × biz_date × window_label × creator_id
-- 语义：页面「近 7 天」等为窗口快照；禁止把 7 日窗口均摊成 7 行日事实
-- 门禁：docs/TK-P3-达人表现POC结论.md · Verdict 🟢（2026-08-06）
-- creator_id = TikTok handle（表现表首格）；非平台 numeric uid
-- 投入：仅 est_commission；投流/寄样金额暂不采，禁止填 0

CREATE SCHEMA IF NOT EXISTS tk;

-- ── 店级 ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tk.fact_tiktok_affiliate_daily (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id                 UUID REFERENCES public.shop(id),
    shop_external_id        TEXT NOT NULL,
    shop_name               TEXT,
    biz_date                DATE NOT NULL,
    window_label            TEXT NOT NULL DEFAULT '近7天',
    gmv_affiliate           NUMERIC(18, 4),
    order_units             NUMERIC(18, 4),
    refund_amount           NUMERIC(18, 4),
    video_cnt               NUMERIC(18, 4),
    live_cnt                NUMERIC(18, 4),
    creators_published      NUMERIC(18, 4),
    creators_sold           NUMERIC(18, 4),
    est_commission          NUMERIC(18, 4),
    currency                TEXT DEFAULT 'GBP',
    source_url              TEXT,
    raw_extra               JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at            TIMESTAMPTZ,
    ingest_id               UUID REFERENCES public.ingest_raw(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, biz_date, window_label)
);

CREATE INDEX IF NOT EXISTS idx_tk_affiliate_daily_date
    ON tk.fact_tiktok_affiliate_daily (biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_affiliate_daily_shop
    ON tk.fact_tiktok_affiliate_daily (shop_external_id, biz_date DESC);

COMMENT ON TABLE tk.fact_tiktok_affiliate_daily IS
  'TK 联盟达人表现·店级窗口快照；P3.1；幂等 shop+biz_date+window_label；禁 7 日均摊；投入仅预计佣金';

COMMENT ON COLUMN tk.fact_tiktok_affiliate_daily.biz_date IS
  '窗口锚点日（采集约定的业务日/窗口结束日），非「近7天拆成7行」';

COMMENT ON COLUMN tk.fact_tiktok_affiliate_daily.window_label IS
  '页面窗口文案归一，如 近7天 / 近28天；与 biz_date 共同唯一';

COMMENT ON COLUMN tk.fact_tiktok_affiliate_daily.est_commission IS
  '预计佣金（页面）；达人投流/寄样金额暂不采，禁止用 0 假填';

-- ── 达人级 ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tk.fact_tiktok_affiliate_creator_daily (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id                 UUID REFERENCES public.shop(id),
    shop_external_id        TEXT NOT NULL,
    shop_name               TEXT,
    biz_date                DATE NOT NULL,
    window_label            TEXT NOT NULL DEFAULT '近7天',
    creator_id              TEXT NOT NULL,
    creator_name            TEXT,
    creator_handle          TEXT,
    gmv                     NUMERIC(18, 4),
    order_units             NUMERIC(18, 4),
    orders_cnt              NUMERIC(18, 4),
    refund_amount           NUMERIC(18, 4),
    refund_units            NUMERIC(18, 4),
    est_commission          NUMERIC(18, 4),
    video_cnt               NUMERIC(18, 4),
    live_cnt                NUMERIC(18, 4),
    product_sold            NUMERIC(18, 4),
    samples_shipped         NUMERIC(18, 4),
    video_views             NUMERIC(18, 4),
    cvr                     NUMERIC(18, 6),
    sold_flag               BOOLEAN,
    currency                TEXT DEFAULT 'GBP',
    source_url              TEXT,
    raw_extra               JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at            TIMESTAMPTZ,
    ingest_id               UUID REFERENCES public.ingest_raw(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, biz_date, window_label, creator_id)
);

CREATE INDEX IF NOT EXISTS idx_tk_affiliate_creator_date
    ON tk.fact_tiktok_affiliate_creator_daily (biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_affiliate_creator_shop
    ON tk.fact_tiktok_affiliate_creator_daily (shop_external_id, biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_tk_affiliate_creator_id
    ON tk.fact_tiktok_affiliate_creator_daily (creator_id);

CREATE INDEX IF NOT EXISTS idx_tk_affiliate_creator_sold
    ON tk.fact_tiktok_affiliate_creator_daily (shop_external_id, biz_date DESC)
    WHERE sold_flag IS TRUE;

COMMENT ON TABLE tk.fact_tiktok_affiliate_creator_daily IS
  'TK 联盟达人表现·达人行窗口快照；P3.1；creator_id=handle；sold_flag=gmv>0 OR order_units>0';

COMMENT ON COLUMN tk.fact_tiktok_affiliate_creator_daily.creator_id IS
  '稳定业务主键：TikTok handle（表现表首格）；非 oec numeric uid';

COMMENT ON COLUMN tk.fact_tiktok_affiliate_creator_daily.sold_flag IS
  '是否出单：gmv>0 OR order_units>0（与动销达人口径对齐）';

COMMENT ON COLUMN tk.fact_tiktok_affiliate_creator_daily.samples_shipped IS
  '已发货样品数（件数）；寄样金额暂不采';

-- public 视图（兼容直查）
DROP VIEW IF EXISTS public.fact_tiktok_affiliate_daily CASCADE;
CREATE OR REPLACE VIEW public.fact_tiktok_affiliate_daily AS
  SELECT * FROM tk.fact_tiktok_affiliate_daily;

DROP VIEW IF EXISTS public.fact_tiktok_affiliate_creator_daily CASCADE;
CREATE OR REPLACE VIEW public.fact_tiktok_affiliate_creator_daily AS
  SELECT * FROM tk.fact_tiktok_affiliate_creator_daily;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qingquan') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON tk.fact_tiktok_affiliate_daily TO qingquan;
    GRANT SELECT, INSERT, UPDATE, DELETE ON tk.fact_tiktok_affiliate_creator_daily TO qingquan;
    GRANT SELECT ON public.fact_tiktok_affiliate_daily TO qingquan;
    GRANT SELECT ON public.fact_tiktok_affiliate_creator_daily TO qingquan;
  END IF;
END $$;
