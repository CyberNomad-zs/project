-- 024 TK 店铺体验分 + 达人健康多账号 + 异常类型
-- 依赖：008_tk_schema.sql · 010/011 anomaly · 019 health types
-- 可重复执行

CREATE SCHEMA IF NOT EXISTS tk;

-- ---------------------------------------------------------------------------
-- 店铺体验分日快照（总分 + 三模块 + 子指标 JSON）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tk.fact_tiktok_experience_daily (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id                 UUID REFERENCES public.shop(id),
    shop_external_id        TEXT NOT NULL,
    shop_name               TEXT,
    biz_date                DATE NOT NULL,
    experience_score        NUMERIC(18, 4),
    product_satisfaction    NUMERIC(18, 4),
    fulfillment_score       NUMERIC(18, 4),
    customer_service_score  NUMERIC(18, 4),
    status_label            TEXT,
    metrics_json            JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_url              TEXT,
    raw_extra               JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at            TIMESTAMPTZ,
    ingest_id               UUID REFERENCES public.ingest_raw(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, biz_date)
);

CREATE INDEX IF NOT EXISTS idx_tk_experience_daily_date
    ON tk.fact_tiktok_experience_daily (biz_date DESC);

COMMENT ON TABLE tk.fact_tiktok_experience_daily IS 'TK 店铺体验分日快照；三模块+子指标';

-- ---------------------------------------------------------------------------
-- 达人健康评分日快照（店 × 达人账号 × 日）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tk.fact_tiktok_creator_health_daily (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    creator_key         TEXT NOT NULL,
    creator_name        TEXT,
    creator_role        TEXT,
    biz_date            DATE NOT NULL,
    health_score        NUMERIC(18, 4),
    status_label        TEXT,
    violation_count     INTEGER,
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES public.ingest_raw(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, creator_key, biz_date)
);

CREATE INDEX IF NOT EXISTS idx_tk_creator_health_daily_date
    ON tk.fact_tiktok_creator_health_daily (biz_date DESC, shop_external_id);

COMMENT ON TABLE tk.fact_tiktok_creator_health_daily IS 'TK 达人健康评分日快照；Seller 切换账号粒度';

-- ---------------------------------------------------------------------------
-- 达人违规明细（与店级 fact_tiktok_violation 分离）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tk.fact_tiktok_creator_violation (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    creator_key         TEXT NOT NULL,
    creator_name        TEXT,
    violation_key       TEXT NOT NULL,
    violation_type      TEXT,
    reason              TEXT,
    result_text         TEXT,
    status              TEXT,
    violation_at        TIMESTAMPTZ,
    biz_date            DATE,
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES public.ingest_raw(id),
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, creator_key, violation_key)
);

CREATE INDEX IF NOT EXISTS idx_tk_creator_violation_seen
    ON tk.fact_tiktok_creator_violation (shop_external_id, first_seen_at DESC);

COMMENT ON TABLE tk.fact_tiktok_creator_violation IS 'TK 达人健康页违规明细';

-- ---------------------------------------------------------------------------
-- 异常类型种子
-- ---------------------------------------------------------------------------
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
