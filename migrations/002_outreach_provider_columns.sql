-- Migration 002: Add provider tracking columns to outreach_sequences
-- Supports Instantly.ai / Smartlead send integration.

ALTER TABLE outreach_sequences
    ADD COLUMN IF NOT EXISTS provider TEXT,
    ADD COLUMN IF NOT EXISTS provider_message_id TEXT,
    ADD COLUMN IF NOT EXISTS provider_campaign_id TEXT,
    ADD COLUMN IF NOT EXISTS error_message TEXT;

CREATE INDEX IF NOT EXISTS idx_outreach_provider_message
    ON outreach_sequences(provider_message_id)
    WHERE provider_message_id IS NOT NULL;
