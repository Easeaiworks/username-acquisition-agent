-- Migration 004: Add 'reviewed' column to outreach_sequences.
-- Used by collect_attention_items() to find unreviewed objections.

ALTER TABLE outreach_sequences
    ADD COLUMN IF NOT EXISTS reviewed BOOLEAN DEFAULT FALSE;
