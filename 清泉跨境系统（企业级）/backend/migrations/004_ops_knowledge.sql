-- 004 运营知识库骨架：动作/效果字典 + 结构化进度 + 剧本 + 指标效果
-- 文档：docs/specs/GOAL-ops-knowledge-ab.txt
-- 依赖：001_init.sql（task / task_progress）；002 可选（metric 回填用 fact_amz_link_daily）

-- 动作码字典
CREATE TABLE IF NOT EXISTS ops_action_dict (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    platform    TEXT,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 效果标签字典
CREATE TABLE IF NOT EXISTS ops_effect_dict (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 进度结构化字段（兼容旧 free-text note）
ALTER TABLE task_progress ADD COLUMN IF NOT EXISTS action_code TEXT;
ALTER TABLE task_progress ADD COLUMN IF NOT EXISTS effect_code TEXT;

-- 任务冗余最近动作/效果 + 指标效果 JSON
ALTER TABLE task ADD COLUMN IF NOT EXISTS last_action_code TEXT;
ALTER TABLE task ADD COLUMN IF NOT EXISTS last_effect_code TEXT;
ALTER TABLE task ADD COLUMN IF NOT EXISTS metric_effect JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_task_progress_action
    ON task_progress (action_code)
    WHERE action_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_last_action
    ON task (platform, anomaly_type, last_action_code)
    WHERE last_action_code IS NOT NULL;

-- 知识剧本
CREATE TABLE IF NOT EXISTS kb_playbook (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform        TEXT NOT NULL,
    anomaly_type    TEXT NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL DEFAULT '',
    action_codes    TEXT[] NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'published', 'rejected')),
    evidence        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_playbook_lookup
    ON kb_playbook (platform, anomaly_type, status);

-- 种子：每平台 ≥1 action
INSERT INTO ops_action_dict (code, name, platform) VALUES
    ('amz_adjust_ads', '调整站内广告预算/竞价', 'amazon'),
    ('amz_check_stock', '核查 FBA 库存与断货', 'amazon'),
    ('tk_pause_low_roi', '暂停低 ROI 广告系列', 'tiktok'),
    ('tk_revise_creative', '替换/优化素材创意', 'tiktok'),
    ('temu_relist', '重新上架/恢复在售', 'temu'),
    ('temu_fix_listing', '核对商品信息与类目', 'temu'),
    ('generic_observe', '观察等待（记录原因）', NULL)
ON CONFLICT (code) DO NOTHING;

-- 种子：≥4 effect
INSERT INTO ops_effect_dict (code, name) VALUES
    ('recovered', '已恢复/明显好转'),
    ('partial', '部分改善'),
    ('no_effect', '无效'),
    ('false_positive', '误报'),
    ('escalated', '已升级')
ON CONFLICT (code) DO NOTHING;

-- 三骨架各 1 条 published 剧本
INSERT INTO kb_playbook (id, platform, anomaly_type, title, body, action_codes, status, evidence)
SELECT
    gen_random_uuid(),
    v.platform,
    v.anomaly_type,
    v.title,
    v.body,
    v.action_codes,
    'published',
    '{"source":"seed"}'::jsonb
FROM (
    VALUES
        (
            'amazon',
            'link_wow_units_drop',
            '周销量环比下跌标准处置',
            '1) 查库存与可售天数 2) 查广告花费与曝光 3) 必要时调广告或记观察。闭环时填写效果标签。',
            ARRAY['amz_check_stock', 'amz_adjust_ads']::TEXT[]
        ),
        (
            'tiktok',
            'low_roi',
            '低 ROI 广告标准处置',
            '1) 确认花费与 ROI 窗口 2) 暂停低效系列或换素材 3) 记录是否恢复。',
            ARRAY['tk_pause_low_roi', 'tk_revise_creative']::TEXT[]
        ),
        (
            'temu',
            'listing_off',
            '下架点名标准处置',
            '1) 核对下架原因 2) 修正信息后重新上架 3) 确认恢复在售并闭环。',
            ARRAY['temu_fix_listing', 'temu_relist']::TEXT[]
        )
) AS v(platform, anomaly_type, title, body, action_codes)
WHERE NOT EXISTS (
    SELECT 1 FROM kb_playbook p
    WHERE p.platform = v.platform
      AND p.anomaly_type = v.anomaly_type
      AND p.status = 'published'
      AND p.evidence->>'source' = 'seed'
);

COMMENT ON TABLE ops_action_dict IS '运营动作码字典';
COMMENT ON TABLE ops_effect_dict IS '闭环效果标签字典';
COMMENT ON TABLE kb_playbook IS '知识剧本 draft|published|rejected；guidance 仅返回 published';
