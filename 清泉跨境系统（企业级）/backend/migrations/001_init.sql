-- 清泉跨境系统 · 初始表结构 Phase 0
-- PostgreSQL 16+
-- 执行: psql $DATABASE_URL -f 001_init.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- 组织与用户
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS org_user (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS org_dept (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    parent_id       UUID REFERENCES org_dept(id),
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 店铺
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shop (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform                TEXT NOT NULL CHECK (platform IN ('amazon', 'tiktok', 'temu', 'other')),
    external_shop_id        TEXT NOT NULL,
    name                    TEXT NOT NULL,
    alias_names             JSONB NOT NULL DEFAULT '[]'::jsonb,
    primary_owner_user_id   UUID REFERENCES org_user(id),
    timezone                TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    currency                TEXT NOT NULL DEFAULT 'GBP',
    status                  TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    meta                    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, external_shop_id)
);

CREATE INDEX IF NOT EXISTS idx_shop_platform ON shop(platform);
CREATE INDEX IF NOT EXISTS idx_shop_status ON shop(status);

-- ---------------------------------------------------------------------------
-- 采集原始与幂等
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_raw (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source              TEXT NOT NULL,
    platform            TEXT,
    shop_external_id    TEXT,
    shop_id             UUID REFERENCES shop(id),
    biz_date            DATE,
    idempotency_key     TEXT NOT NULL,
    payload             JSONB NOT NULL,
    evidence            JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at        TIMESTAMPTZ,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    process_status      TEXT NOT NULL DEFAULT 'accepted'
                        CHECK (process_status IN ('accepted', 'processed', 'failed')),
    error_message       TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ingest_idempotency
    ON ingest_raw (idempotency_key);

CREATE INDEX IF NOT EXISTS idx_ingest_source_date
    ON ingest_raw (source, biz_date DESC);

CREATE INDEX IF NOT EXISTS idx_ingest_received
    ON ingest_raw (received_at DESC);

-- ---------------------------------------------------------------------------
-- TK 广告事实（Phase0 优先接通）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_ads_campaign_daily (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id         UUID REFERENCES shop(id),
    shop_external_id TEXT NOT NULL,
    shop_name       TEXT,
    biz_date        DATE NOT NULL,
    campaign_name   TEXT NOT NULL,
    spend           NUMERIC(18, 4) NOT NULL DEFAULT 0,
    orders          NUMERIC(18, 4) NOT NULL DEFAULT 0,
    roi             NUMERIC(18, 6),
    revenue         NUMERIC(18, 4) NOT NULL DEFAULT 0,
    currency        TEXT DEFAULT 'GBP',
    row_status      TEXT DEFAULT 'success',
    source_url      TEXT,
    collected_at    TIMESTAMPTZ,
    ingest_id       UUID REFERENCES ingest_raw(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (shop_external_id, campaign_name, biz_date)
);

CREATE INDEX IF NOT EXISTS idx_ads_biz_date ON fact_ads_campaign_daily (biz_date DESC);
CREATE INDEX IF NOT EXISTS idx_ads_shop_date ON fact_ads_campaign_daily (shop_id, biz_date DESC);

-- ---------------------------------------------------------------------------
-- 异常与任务
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anomaly_event (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform        TEXT NOT NULL,
    shop_id         UUID REFERENCES shop(id),
    anomaly_type    TEXT NOT NULL,
    biz_id          TEXT NOT NULL,
    biz_id_type     TEXT NOT NULL DEFAULT 'unknown',
    dedupe_key      TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'warn'
                    CHECK (severity IN ('info', 'warn', 'high', 'critical')),
    title           TEXT NOT NULL,
    detail          TEXT,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    task_id         UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_dedupe ON anomaly_event (dedupe_key, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_detected ON anomaly_event (detected_at DESC);

CREATE TABLE IF NOT EXISTS task (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dedupe_key          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'resolved', 'cancelled')),
    platform            TEXT NOT NULL,
    shop_id             UUID REFERENCES shop(id),
    anomaly_type        TEXT NOT NULL,
    biz_id              TEXT NOT NULL,
    title               TEXT NOT NULL,
    owner_user_id       UUID REFERENCES org_user(id),
    due_at              TIMESTAMPTZ,
    progress_note       TEXT,
    source_event_id     UUID REFERENCES anomaly_event(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ
);

-- 会议规则：未闭环任务按 dedupe_key 唯一
CREATE UNIQUE INDEX IF NOT EXISTS uq_task_open_dedupe
    ON task (dedupe_key)
    WHERE status IN ('open', 'in_progress');

CREATE INDEX IF NOT EXISTS idx_task_status ON task (status);
CREATE INDEX IF NOT EXISTS idx_task_owner ON task (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_task_shop ON task (shop_id);
CREATE INDEX IF NOT EXISTS idx_task_due ON task (due_at);

CREATE TABLE IF NOT EXISTS task_progress (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    note            TEXT NOT NULL,
    from_status     TEXT,
    to_status       TEXT,
    operator_user_id UUID REFERENCES org_user(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_progress_task ON task_progress (task_id, created_at DESC);

-- 回填 anomaly.task_id FK（表创建顺序）
ALTER TABLE anomaly_event
    DROP CONSTRAINT IF EXISTS fk_anomaly_task;
ALTER TABLE anomaly_event
    ADD CONSTRAINT fk_anomaly_task
    FOREIGN KEY (task_id) REFERENCES task(id);

-- ---------------------------------------------------------------------------
-- 飞书同步
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_feishu_map (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_key       TEXT NOT NULL,
    local_table     TEXT NOT NULL,
    local_id        UUID NOT NULL,
    app_token       TEXT NOT NULL,
    table_id        TEXT NOT NULL,
    record_id       TEXT NOT NULL,
    content_hash    TEXT,
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (table_key, local_id),
    UNIQUE (app_token, table_id, record_id)
);

CREATE TABLE IF NOT EXISTS sync_feishu_job (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_key       TEXT NOT NULL,
    mode            TEXT NOT NULL DEFAULT 'incremental'
                    CHECK (mode IN ('incremental', 'rebuild')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'success', 'failed')),
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS outbox_event (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL,
    aggregate_type  TEXT NOT NULL,
    aggregate_id    UUID NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    attempts        INT NOT NULL DEFAULT 0,
    available_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON outbox_event (status, available_at)
    WHERE status IN ('pending', 'failed');

-- ---------------------------------------------------------------------------
-- 采集节点心跳
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS collector_node (
    node_id         TEXT PRIMARY KEY,
    version         TEXT,
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 审计
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id   UUID REFERENCES org_user(id),
    action          TEXT NOT NULL,
    resource_type   TEXT,
    resource_id     TEXT,
    detail          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at DESC);

-- ---------------------------------------------------------------------------
-- 种子数据（密码: admin123 — 首次登录后务必修改）
-- hash = bcrypt of "admin123" cost 12
-- 由应用启动 seed 写入更稳妥；此处仅结构占位注释
-- INSERT INTO org_user (username, password_hash, display_name, is_admin)
-- VALUES ('admin', '<bcrypt>', '管理员', TRUE);

COMMENT ON TABLE task IS '跟踪任务：未闭环唯一 dedupe_key = platform:biz_id:anomaly_type';
COMMENT ON TABLE ingest_raw IS '采集上报原始；idempotency_key 全局唯一';
COMMENT ON TABLE fact_ads_campaign_daily IS 'TK 广告系列日指标；Phase0 优先';
COMMENT ON TABLE sync_feishu_map IS '本地记录与飞书 record_id 映射，支持 update';
