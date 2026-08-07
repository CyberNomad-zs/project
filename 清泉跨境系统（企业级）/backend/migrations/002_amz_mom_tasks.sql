-- 002 Amazon 环比样板：事实 / 规则 / 跑批 / task 扩展
-- 文档：docs/AMZ环比异常-人维任务草案.md（v0.2）
-- 依赖：001_init.sql
-- 业务已确认（2026-07-28）：
--   自然周/月 · 下列种子阈值 · 多单并行 · listing_owner · 首期指标仅 units+sales_amount

-- 链接日事实
CREATE TABLE IF NOT EXISTS fact_amz_link_daily (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES shop(id),
    shop_external_id    TEXT NOT NULL,
    biz_date            DATE NOT NULL,
    asin                TEXT,
    seller_sku          TEXT,
    parent_asin         TEXT,
    title               TEXT,
    units               NUMERIC(18, 4) NOT NULL DEFAULT 0,
    sales_amount        NUMERIC(18, 4) NOT NULL DEFAULT 0,
    currency            TEXT DEFAULT 'GBP',
    sessions            NUMERIC(18, 4),
    conversion_rate     NUMERIC(18, 6),
    fba_fulfillable     NUMERIC(18, 4),
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingest_id           UUID REFERENCES ingest_raw(id),
    collected_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    biz_key             TEXT GENERATED ALWAYS AS (
                            CASE
                                WHEN asin IS NOT NULL AND btrim(asin) <> '' THEN 'asin:' || btrim(asin)
                                ELSE 'sku:' || coalesce(btrim(seller_sku), '')
                            END
                        ) STORED,
    CONSTRAINT chk_amz_link_identity CHECK (
        (asin IS NOT NULL AND btrim(asin) <> '')
        OR (seller_sku IS NOT NULL AND btrim(seller_sku) <> '')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_amz_link_daily
    ON fact_amz_link_daily (shop_external_id, biz_date, biz_key);

CREATE INDEX IF NOT EXISTS idx_fact_amz_link_shop_date
    ON fact_amz_link_daily (shop_id, biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_fact_amz_link_asin_date
    ON fact_amz_link_daily (asin, biz_date DESC);

-- 环比规则
CREATE TABLE IF NOT EXISTS amz_mom_rule (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    metric              TEXT NOT NULL CHECK (metric IN ('units', 'sales_amount', 'sessions')),
    period              TEXT NOT NULL CHECK (period IN ('day', 'week', 'month')),
    compare             TEXT NOT NULL DEFAULT 'mom',
    drop_ratio_gte      NUMERIC(8, 4) NOT NULL,
    drop_abs_gte        NUMERIC(18, 4),
    min_base_value      NUMERIC(18, 4) NOT NULL DEFAULT 0,
    severity            TEXT NOT NULL DEFAULT 'warn'
                        CHECK (severity IN ('info', 'warn', 'high', 'critical')),
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    platform            TEXT NOT NULL DEFAULT 'amazon',
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 跑批
CREATE TABLE IF NOT EXISTS amz_mom_eval_run (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    biz_date            DATE NOT NULL,
    period              TEXT,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'success', 'failed')),
    rules_snapshot      JSONB NOT NULL DEFAULT '[]'::jsonb,
    stats               JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message       TEXT,
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_amz_mom_run_date ON amz_mom_eval_run (biz_date DESC);

-- task 轻量扩展
ALTER TABLE task ADD COLUMN IF NOT EXISTS domain TEXT NOT NULL DEFAULT 'ops';
ALTER TABLE task ADD COLUMN IF NOT EXISTS metric_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE task ADD COLUMN IF NOT EXISTS owner_source TEXT;

CREATE INDEX IF NOT EXISTS idx_task_domain_platform ON task (domain, platform, status);

-- ASIN 负责人（可选）
CREATE TABLE IF NOT EXISTS listing_owner (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform            TEXT NOT NULL,
    shop_id             UUID REFERENCES shop(id),
    biz_id              TEXT NOT NULL,
    biz_id_type         TEXT NOT NULL DEFAULT 'asin',
    owner_user_id       UUID NOT NULL REFERENCES org_user(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, shop_id, biz_id_type, biz_id)
);

-- 种子规则（业务已确认采用；仅 units + sales_amount）
INSERT INTO amz_mom_rule (code, name, metric, period, drop_ratio_gte, min_base_value, severity)
VALUES
    ('link_dod_units_drop', '链接日销量环比下降', 'units', 'day', 0.40, 5, 'warn'),
    ('link_wow_units_drop', '链接周销量环比下降', 'units', 'week', 0.30, 10, 'high'),
    ('link_mom_units_drop', '链接月销量环比下降', 'units', 'month', 0.30, 20, 'high'),
    ('link_wow_sales_drop', '链接周销售额环比下降', 'sales_amount', 'week', 0.30, 100, 'warn')
ON CONFLICT (code) DO NOTHING;

COMMENT ON TABLE fact_amz_link_daily IS 'Amazon 链接日指标；环比样板事实源';
COMMENT ON TABLE amz_mom_rule IS 'Amazon 环比异常规则；code=anomaly_type';
COMMENT ON TABLE amz_mom_eval_run IS '环比扫描跑批记录';
COMMENT ON TABLE listing_owner IS '链接级第一负责人；优先于 shop.primary_owner_user_id';
