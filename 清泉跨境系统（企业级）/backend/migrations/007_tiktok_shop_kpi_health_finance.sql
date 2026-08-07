-- 007 TikTok shop daily KPI / account health / finance daily (P2c + P3 skeleton)
-- 依赖：001_init.sql
-- 说明：店级日汇总，与广告/订单/商品明细表分离

CREATE TABLE IF NOT EXISTS fact_tiktok_shop_daily (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    biz_date            DATE NOT NULL,
    gmv                 NUMERIC(18, 4),
    orders_cnt          NUMERIC(18, 4),
    buyers_cnt          NUMERIC(18, 4),
    refund_amount       NUMERIC(18, 4),
    currency            TEXT DEFAULT 'GBP',
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES ingest_raw(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, biz_date)
);

CREATE INDEX IF NOT EXISTS idx_tk_shop_daily_date
    ON fact_tiktok_shop_daily (biz_date DESC);

COMMENT ON TABLE fact_tiktok_shop_daily IS 'TK 店级日 KPI（数据分析/首页）；P2c';

CREATE TABLE IF NOT EXISTS fact_tiktok_health_daily (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    biz_date            DATE NOT NULL,
    health_score        NUMERIC(18, 4),
    late_dispatch_rate  NUMERIC(18, 6),
    negative_feedback_rate NUMERIC(18, 6),
    status_label        TEXT,
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES ingest_raw(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, biz_date)
);

CREATE INDEX IF NOT EXISTS idx_tk_health_daily_date
    ON fact_tiktok_health_daily (biz_date DESC);

COMMENT ON TABLE fact_tiktok_health_daily IS 'TK 账号健康日快照；P3a';

CREATE TABLE IF NOT EXISTS fact_tiktok_finance_daily (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    biz_date            DATE NOT NULL,
    settlement_amount   NUMERIC(18, 4),
    pending_amount      NUMERIC(18, 4),
    refund_amount       NUMERIC(18, 4),
    currency            TEXT DEFAULT 'GBP',
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES ingest_raw(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, biz_date)
);

CREATE INDEX IF NOT EXISTS idx_tk_finance_daily_date
    ON fact_tiktok_finance_daily (biz_date DESC);

COMMENT ON TABLE fact_tiktok_finance_daily IS 'TK 财务/结算日摘要；P3b';
