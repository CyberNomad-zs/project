-- 005 TikTok 订单事实（P2a 整站采集 · 订单域）
-- 依赖：001_init.sql
-- 粒度：店铺 × 订单号（订单头一行；多 SKU 明细可后续拆 fact_tiktok_order_line）

CREATE TABLE IF NOT EXISTS fact_tiktok_order (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    order_id            TEXT NOT NULL,
    order_status        TEXT,
    pay_time            TIMESTAMPTZ,
    create_time         TIMESTAMPTZ,
    biz_date            DATE,
    product_name        TEXT,
    seller_sku          TEXT,
    sku_id              TEXT,
    quantity            NUMERIC(18, 4) NOT NULL DEFAULT 0,
    pay_amount          NUMERIC(18, 4) NOT NULL DEFAULT 0,
    currency            TEXT DEFAULT 'USD',
    shipping_status     TEXT,
    buyer_region        TEXT,
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES ingest_raw(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, order_id)
);

CREATE INDEX IF NOT EXISTS idx_tk_order_biz_date
    ON fact_tiktok_order (biz_date DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_tk_order_shop_date
    ON fact_tiktok_order (shop_external_id, biz_date DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_tk_order_status
    ON fact_tiktok_order (order_status);

COMMENT ON TABLE fact_tiktok_order IS 'TK 订单头事实；P2a 整站采集；幂等键 shop_external_id+order_id';
COMMENT ON COLUMN fact_tiktok_order.biz_date IS '业务日：优先支付日，否则下单日（UTC+店铺时区由采集侧决定）';
COMMENT ON COLUMN fact_tiktok_order.raw_extra IS '页面多余列 JSON，避免频繁加列';
