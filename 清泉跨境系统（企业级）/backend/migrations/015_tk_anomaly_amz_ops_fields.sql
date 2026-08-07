-- 015 TK 异常任务：对齐 AMZ「异常任务」人维/指标明细字段
-- 飞书参考：ASIN健康度监控 · 异常任务 tblXnUm9VSmyQ2AC
-- TK 表：tblstt4IVNJihCd3
-- 依赖：010_tk_anomaly_task.sql

ALTER TABLE tk.fact_tk_anomaly_task
    ADD COLUMN IF NOT EXISTS level_code TEXT,
    ADD COLUMN IF NOT EXISTS current_value DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS current_value_label TEXT,
    ADD COLUMN IF NOT EXISTS compare_value DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS compare_value_label TEXT,
    ADD COLUMN IF NOT EXISTS change_magnitude DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS change_magnitude_label TEXT,
    ADD COLUMN IF NOT EXISTS streak_count INT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS needs_boss_decision BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS is_confirmed TEXT,
    ADD COLUMN IF NOT EXISTS judgment_basis TEXT,
    ADD COLUMN IF NOT EXISTS action_taken TEXT,
    ADD COLUMN IF NOT EXISTS executor_name TEXT,
    ADD COLUMN IF NOT EXISTS executed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS data_before TEXT,
    ADD COLUMN IF NOT EXISTS data_after TEXT,
    ADD COLUMN IF NOT EXISTS is_effective TEXT,
    ADD COLUMN IF NOT EXISTS review_items TEXT,
    ADD COLUMN IF NOT EXISTS review_date DATE,
    ADD COLUMN IF NOT EXISTS next_action TEXT,
    ADD COLUMN IF NOT EXISTS close_status TEXT,
    ADD COLUMN IF NOT EXISTS reviewer_name TEXT;

COMMENT ON COLUMN tk.fact_tk_anomaly_task.level_code IS 'AMZ 等级 red/orange/yellow；可由 priority 推导';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.current_value IS '当前指标值（可空）';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.compare_value IS '对比/阈值';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.streak_count IS '连续异常次数';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.needs_boss_decision IS '需要老板决策';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.description IS '说明（人读长文案）';
COMMENT ON COLUMN tk.fact_tk_anomaly_task.close_status IS '闭环状态补充（人维）';

-- 回填等级：P0→red P1→orange P2→yellow
UPDATE tk.fact_tk_anomaly_task
SET level_code = CASE priority
    WHEN 'P0' THEN 'red'
    WHEN 'P1' THEN 'orange'
    WHEN 'P2' THEN 'yellow'
    ELSE COALESCE(level_code, 'orange')
END
WHERE level_code IS NULL;

-- P0 默认需要老板决策（仅回填仍为 false 且未闭环）
UPDATE tk.fact_tk_anomaly_task
SET needs_boss_decision = TRUE
WHERE priority = 'P0'
  AND needs_boss_decision IS FALSE
  AND status IN ('open', 'in_progress');

-- description 缺省用 summary
UPDATE tk.fact_tk_anomaly_task
SET description = summary
WHERE (description IS NULL OR description = '')
  AND summary IS NOT NULL
  AND summary <> '';

CREATE INDEX IF NOT EXISTS idx_tk_anomaly_task_level
    ON tk.fact_tk_anomaly_task (level_code, status)
    WHERE level_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tk_anomaly_task_boss
    ON tk.fact_tk_anomaly_task (needs_boss_decision, status)
    WHERE needs_boss_decision = TRUE;
