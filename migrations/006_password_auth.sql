-- Migration 006: Add password_hash column to admin_users for password-based login
-- This enables email + password authentication instead of raw API key entry.

ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Add an index on email for fast login lookups
CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users (email);
