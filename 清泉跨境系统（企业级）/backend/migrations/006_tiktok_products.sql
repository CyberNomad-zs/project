-- 006 TikTok 商品事实（P2b 整站采集 · 商品域）
-- 依赖：001_init.sql
-- 粒度：店铺 × 平台商品ID（或 seller_sku 兜底）

CREATE TABLE IF NOT EXISTS fact_tiktok_product (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES shop(id),
    shop_external_id    TEXT NOT NULL,
    shop_name           TEXT,
    product_id          TEXT NOT NULL,
    product_name        TEXT,
    seller_sku          TEXT,
    status              TEXT,
    stock_qty           NUMERIC(18, 4),
    price               NUMERIC(18, 4),
    currency            TEXT DEFAULT 'GBP',
    sales_qty           NUMERIC(18, 4),
    source_url          TEXT,
    raw_extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    ingest_id           UUID REFERENCES ingest_raw(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_tk_product_shop
    ON fact_tiktok_product (shop_external_id);

CREATE INDEX IF NOT EXISTS idx_tk_product_status
    ON fact_tiktok_product (status);

COMMENT ON TABLE fact_tiktok_product IS 'TK 商品列表事实；P2b；幂等 shop_external_id+product_id';
COMMENT ON COLUMN fact_tiktok_product.product_id IS '平台商品 ID；若仅有 SKU 可用 seller_sku 填充并加前缀 sku:';
COMMENT ON COLUMN fact_tiktok_product.raw_extra IS '页面多余列 JSON';
