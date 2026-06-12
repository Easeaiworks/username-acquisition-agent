-- ============================================================
-- Migration 005: Admin Panel — RBAC, file uploads, integrations, templates
-- ============================================================

-- 1. User roles & accounts
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('super_admin', 'admin', 'viewer')),
    api_key TEXT UNIQUE,              -- each user gets their own API key
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed the default super admin (uses the existing DASHBOARD_API_KEY)
-- The app will auto-link the existing key on first login

-- 2. API integrations — encrypted key storage
CREATE TABLE IF NOT EXISTS api_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name TEXT NOT NULL,                            -- e.g. 'instantly', 'twitter', 'sendgrid'
    service_category TEXT NOT NULL DEFAULT 'custom',       -- 'email', 'social', 'enrichment', 'custom'
    display_name TEXT NOT NULL,                            -- Human-friendly name
    api_key_encrypted TEXT,                                -- encrypted value (base64)
    extra_config JSONB DEFAULT '{}'::jsonb,               -- additional fields (client_id, client_secret, webhook_url, etc.)
    is_connected BOOLEAN NOT NULL DEFAULT FALSE,
    last_tested_at TIMESTAMPTZ,
    test_result TEXT,                                      -- 'ok' or error message
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(service_name)
);

-- 3. File uploads — track all uploaded assets
CREATE TABLE IF NOT EXISTS file_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,                               -- original filename
    storage_path TEXT NOT NULL,                            -- Supabase storage path
    file_type TEXT NOT NULL,                               -- 'email_list', 'social_list', 'template', 'image', 'document', 'other'
    mime_type TEXT,                                        -- e.g. 'text/csv', 'image/png'
    file_size_bytes BIGINT,
    category TEXT NOT NULL DEFAULT 'general',              -- 'email_lists', 'social_data', 'templates', 'images', 'documents'
    description TEXT DEFAULT '',
    row_count INTEGER,                                    -- for CSV/Excel: number of data rows
    column_headers JSONB,                                 -- for CSV/Excel: list of column names
    processing_status TEXT DEFAULT 'uploaded',             -- 'uploaded', 'processing', 'ready', 'error'
    processing_error TEXT,
    uploaded_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Email templates
CREATE TABLE IF NOT EXISTS email_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    subject_template TEXT NOT NULL DEFAULT '',
    body_template TEXT NOT NULL DEFAULT '',
    template_type TEXT NOT NULL DEFAULT 'outreach',        -- 'outreach', 'follow_up', 'meeting_request', 'custom'
    sequence_step INTEGER DEFAULT 1,                       -- which step in the sequence (1-4)
    merge_tags JSONB DEFAULT '[]'::jsonb,                  -- available merge tags: ["{{first_name}}", "{{company}}"]
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);
CREATE INDEX IF NOT EXISTS idx_admin_users_api_key ON admin_users(api_key);
CREATE INDEX IF NOT EXISTS idx_api_integrations_category ON api_integrations(service_category);
CREATE INDEX IF NOT EXISTS idx_file_uploads_category ON file_uploads(category);
CREATE INDEX IF NOT EXISTS idx_file_uploads_type ON file_uploads(file_type);
CREATE INDEX IF NOT EXISTS idx_email_templates_type ON email_templates(template_type);
CREATE INDEX IF NOT EXISTS idx_email_templates_step ON email_templates(sequence_step);

-- 6. Seed default integrations (all major services the system supports)
INSERT INTO api_integrations (service_name, service_category, display_name, extra_config)
VALUES
    ('instantly', 'email', 'Instantly.ai', '{"fields": ["api_key", "campaign_id"]}'),
    ('sendgrid', 'email', 'SendGrid', '{"fields": ["api_key"]}'),
    ('mailgun', 'email', 'Mailgun', '{"fields": ["api_key", "domain"]}'),
    ('smtp_custom', 'email', 'Custom SMTP', '{"fields": ["host", "port", "username", "password", "use_tls"]}'),
    ('twitter', 'social', 'Twitter / X', '{"fields": ["api_key", "api_secret", "access_token", "access_token_secret"]}'),
    ('instagram', 'social', 'Instagram', '{"fields": ["access_token"]}'),
    ('tiktok', 'social', 'TikTok', '{"fields": ["api_key"]}'),
    ('linkedin', 'social', 'LinkedIn', '{"fields": ["client_id", "client_secret", "access_token"]}'),
    ('youtube', 'enrichment', 'YouTube Data API', '{"fields": ["api_key"]}'),
    ('twitch', 'enrichment', 'Twitch Helix', '{"fields": ["client_id", "client_secret"]}'),
    ('apify', 'enrichment', 'Apify', '{"fields": ["api_token"]}'),
    ('rocketreach', 'enrichment', 'RocketReach', '{"fields": ["api_key"]}'),
    ('hunter', 'enrichment', 'Hunter.io', '{"fields": ["api_key"]}'),
    ('anthropic', 'ai', 'Claude / Anthropic', '{"fields": ["api_key"]}'),
    ('calendly', 'scheduling', 'Calendly', '{"fields": ["api_key", "event_url"]}')
ON CONFLICT (service_name) DO NOTHING;

-- 7. Seed default email templates
INSERT INTO email_templates (name, subject_template, body_template, template_type, sequence_step, merge_tags, is_default)
VALUES
    (
        'Initial Outreach',
        'Quick question about @{{target_handle}}',
        E'Hi {{first_name}},\n\nI noticed that {{company}} has built an incredible brand, but the social handle @{{target_handle}} on {{platform}} doesn''t quite match your brand presence.\n\nWe specialize in helping companies like yours secure the perfect username across platforms. Would you be open to a quick 10-minute call to explore this?\n\nBest,\n{{sender_name}}',
        'outreach', 1,
        '["{{first_name}}", "{{company}}", "{{target_handle}}", "{{platform}}", "{{sender_name}}"]',
        TRUE
    ),
    (
        'Follow-up 1',
        'Re: @{{target_handle}} — quick follow-up',
        E'Hi {{first_name}},\n\nJust following up on my previous note about securing @{{target_handle}} for {{company}}.\n\nBrands that lock down their handle early see significantly better engagement. Happy to share some quick data on a call.\n\nBest,\n{{sender_name}}',
        'follow_up', 2,
        '["{{first_name}}", "{{company}}", "{{target_handle}}", "{{sender_name}}"]',
        TRUE
    ),
    (
        'Follow-up 2 — Value Add',
        '{{company}} + social handle strategy',
        E'Hi {{first_name}},\n\nI wanted to share a quick insight: companies in {{industry}} that secure consistent handles across platforms see up to 23% higher brand recall.\n\nI''d love to walk you through our approach. Would {{meeting_day}} work for a brief chat?\n\n{{sender_name}}',
        'follow_up', 3,
        '["{{first_name}}", "{{company}}", "{{industry}}", "{{meeting_day}}", "{{sender_name}}"]',
        TRUE
    ),
    (
        'Final Touch — Breakup',
        'Last note on @{{target_handle}}',
        E'Hi {{first_name}},\n\nI don''t want to be a pest — this will be my last note on this.\n\nIf securing @{{target_handle}} is ever something {{company}} wants to explore, I''m always here. Just reply to this email anytime.\n\nWishing you the best,\n{{sender_name}}',
        'follow_up', 4,
        '["{{first_name}}", "{{company}}", "{{target_handle}}", "{{sender_name}}"]',
        TRUE
    )
ON CONFLICT DO NOTHING;

-- 8. Create storage bucket for file uploads (run manually in Supabase dashboard if needed)
-- INSERT INTO storage.buckets (id, name, public) VALUES ('uploads', 'uploads', false) ON CONFLICT DO NOTHING;
