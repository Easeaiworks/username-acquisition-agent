-- Migration 003: Add columns to daily_reports that persist_report() and history/trends queries expect.
-- Table has 0 rows so this is safe.

ALTER TABLE daily_reports
    ADD COLUMN IF NOT EXISTS pipeline_total INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS new_companies INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS stage_movements INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS scored_today INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS avg_score DOUBLE PRECISION DEFAULT 0,
    ADD COLUMN IF NOT EXISTS high_value_today INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reply_rate DOUBLE PRECISION DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bounces INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS active_sequences INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pending_approvals INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS attention_items INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS full_report_json JSONB;
