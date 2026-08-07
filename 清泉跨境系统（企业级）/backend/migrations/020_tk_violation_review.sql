-- 020 TK 违规记录 + 商品评分（差评）
-- 依赖：008_tk_schema.sql · 011_tk_anomaly_types_specialize.sql
-- 可重复执行

CREATE SCHEMA IF NOT EXISTS tk;

-- ---------------------------------------------------------------------------
-- 违规记录（账号健康 · 违规记录页）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tk.fact_tiktok_violation (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    -- 稳定业务键：平台罚单/记录 ID，或 penalty|reason|date 哈希
    violation_key       TEXT NOT NULL,
    penalty_text        TEXT,
    penalty_score       NUMERIC(18, 4),
    reason              TEXT,
    status              TEXT,
    violation_at        TIMESTAMPTZ,
    biz_date            DATE,
    product_id          TEXT,
    order_id            TEXT,
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES public.ingest_raw(id),
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, violation_key)
);

CREATE INDEX IF NOT EXISTS idx_tk_violation_date
    ON tk.fact_tiktok_violation (biz_date DESC NULLS LAST, shop_external_id);
CREATE INDEX IF NOT EXISTS idx_tk_violation_shop_seen
    ON tk.fact_tiktok_violation (shop_external_id, first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_tk_violation_product
    ON tk.fact_tiktok_violation (product_id)
    WHERE product_id IS NOT NULL;

COMMENT ON TABLE tk.fact_tiktok_violation IS 'TK 店铺违规/扣分记录；来源账号健康·违规记录页';
COMMENT ON COLUMN tk.fact_tiktok_violation.violation_key IS '幂等键：罚单ID 或内容指纹';
COMMENT ON COLUMN tk.fact_tiktok_violation.penalty_score IS 'AHR 违规分等扣分值';
COMMENT ON COLUMN tk.fact_tiktok_violation.first_seen_at IS '首次入库时间；用于「新违规」提醒';

-- ---------------------------------------------------------------------------
-- 商品评分 / 评价
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tk.fact_tiktok_review (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES public.shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    review_key          TEXT NOT NULL,
    order_id            TEXT,
    product_id          TEXT,
    product_name        TEXT,
    rating              NUMERIC(4, 2),
    review_text         TEXT,
    review_at           TIMESTAMPTZ,
    biz_date            DATE,
    buyer_name          TEXT,
    reply_text          TEXT,
    reply_at            TIMESTAMPTZ,
    has_reply           BOOLEAN NOT NULL DEFAULT FALSE,
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES public.ingest_raw(id),
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, review_key)
);

CREATE INDEX IF NOT EXISTS idx_tk_review_date
    ON tk.fact_tiktok_review (biz_date DESC NULLS LAST, shop_external_id);
CREATE INDEX IF NOT EXISTS idx_tk_review_rating
    ON tk.fact_tiktok_review (shop_external_id, rating)
    WHERE rating IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tk_review_product
    ON tk.fact_tiktok_review (product_id)
    WHERE product_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tk_review_first_seen
    ON tk.fact_tiktok_review (shop_external_id, first_seen_at DESC);

COMMENT ON TABLE tk.fact_tiktok_review IS 'TK 商品评分/评价；来源商品·商品评分页';
COMMENT ON COLUMN tk.fact_tiktok_review.review_key IS '幂等键：order+product 或内容指纹';
COMMENT ON COLUMN tk.fact_tiktok_review.rating IS '星级 1-5';
COMMENT ON COLUMN tk.fact_tiktok_review.first_seen_at IS '首次入库时间；用于「新差评」提醒';

-- 兼容视图
DROP VIEW IF EXISTS public.fact_tiktok_violation CASCADE;
CREATE OR REPLACE VIEW public.fact_tiktok_violation AS SELECT * FROM tk.fact_tiktok_violation;
DROP VIEW IF EXISTS public.fact_tiktok_review CASCADE;
CREATE OR REPLACE VIEW public.fact_tiktok_review AS SELECT * FROM tk.fact_tiktok_review;

-- 异常类型
INSERT INTO tk.dim_tk_anomaly_type
    (code, name_cn, object_type, severity_default, priority_default, description, sort_order, enabled)
VALUES
    ('shop_violation',   '店铺违规扣分', 'shop',    'critical', 'P0',
     '账号健康·违规记录新出现扣分/处罚，即提醒负责人', 152, TRUE),
    ('shop_bad_review',  '商品差评待处理', 'product', 'high',     'P1',
     '商品评分页新出现差评（默认≤2星），即提醒负责人处理', 185, TRUE)
ON CONFLICT (code) DO UPDATE SET
    name_cn          = EXCLUDED.name_cn,
    object_type      = EXCLUDED.object_type,
    severity_default = EXCLUDED.severity_default,
    priority_default = EXCLUDED.priority_default,
    description      = EXCLUDED.description,
    sort_order       = EXCLUDED.sort_order,
    enabled          = TRUE;
