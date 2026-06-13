-- ============================================================================
-- Migration 008: Email Marketing Platform
-- ============================================================================
--
-- Built-in email marketing system — a full-featured platform to compete with
-- Mailchimp. Provides contacts, lists, campaigns, drip sequences, event
-- tracking, reusable templates, sender configuration, and secure one-click
-- unsubscribe support.
--
-- Tables created:
--   1.  email_contacts            – Central contact store
--   2.  email_lists               – Audiences / mailing lists
--   3.  email_list_members        – Many-to-many (contacts <-> lists)
--   4.  email_campaigns           – One-off and A/B campaign sends
--   5.  email_events              – Open / click / bounce / unsubscribe tracking
--   6.  email_templates           – Reusable email templates with builder state
--   7.  email_sequences           – Drip / automation sequences
--   8.  email_sequence_steps      – Individual steps within a sequence
--   9.  email_sequence_enrollments – Contact enrollment in sequences
--   10. email_sender_config       – SMTP / SendGrid / SES configuration
--   11. email_unsubscribe_tokens  – Secure one-click unsubscribe tokens
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. email_contacts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    company TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    tags TEXT[] DEFAULT '{}',
    custom_fields JSONB DEFAULT '{}',
    status TEXT DEFAULT 'subscribed' CHECK (status IN ('subscribed','unsubscribed','bounced','complained','cleaned')),
    source TEXT DEFAULT 'manual',  -- 'manual', 'import', 'api', 'pipeline', 'form'
    ip_address TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT now(),
    unsubscribed_at TIMESTAMPTZ,
    bounce_count INTEGER DEFAULT 0,
    last_emailed_at TIMESTAMPTZ,
    last_opened_at TIMESTAMPTZ,
    last_clicked_at TIMESTAMPTZ,
    email_count INTEGER DEFAULT 0,
    open_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_contacts_email ON email_contacts (email);
CREATE INDEX IF NOT EXISTS idx_email_contacts_status ON email_contacts (status);
CREATE INDEX IF NOT EXISTS idx_email_contacts_tags ON email_contacts USING GIN (tags);


-- ---------------------------------------------------------------------------
-- 2. email_lists
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    default_from_name TEXT DEFAULT '',
    default_from_email TEXT DEFAULT '',
    default_reply_to TEXT DEFAULT '',
    contact_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- 3. email_list_members (many-to-many)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_list_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id UUID REFERENCES email_lists(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES email_contacts(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'active' CHECK (status IN ('active','unsubscribed','cleaned')),
    added_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(list_id, contact_id)
);
CREATE INDEX IF NOT EXISTS idx_email_list_members_list ON email_list_members (list_id);
CREATE INDEX IF NOT EXISTS idx_email_list_members_contact ON email_list_members (contact_id);


-- ---------------------------------------------------------------------------
-- 4. email_campaigns
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    preview_text TEXT DEFAULT '',
    from_name TEXT DEFAULT '',
    from_email TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    html_content TEXT DEFAULT '',
    text_content TEXT DEFAULT '',
    template_id UUID,  -- optional reference to email_templates
    list_id UUID REFERENCES email_lists(id),
    segment_conditions JSONB DEFAULT '{}',  -- for targeted sends
    campaign_type TEXT DEFAULT 'regular' CHECK (campaign_type IN ('regular','automated','ab_test')),
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft','scheduled','sending','sent','paused','cancelled')),
    scheduled_at TIMESTAMPTZ,
    started_sending_at TIMESTAMPTZ,
    finished_sending_at TIMESTAMPTZ,
    -- Stats (denormalized for fast reads)
    recipients_count INTEGER DEFAULT 0,
    sent_count INTEGER DEFAULT 0,
    delivered_count INTEGER DEFAULT 0,
    open_count INTEGER DEFAULT 0,
    unique_open_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    unique_click_count INTEGER DEFAULT 0,
    bounce_count INTEGER DEFAULT 0,
    unsubscribe_count INTEGER DEFAULT 0,
    complaint_count INTEGER DEFAULT 0,
    -- Metadata
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_email_campaigns_status ON email_campaigns (status);
CREATE INDEX IF NOT EXISTS idx_email_campaigns_list ON email_campaigns (list_id);


-- ---------------------------------------------------------------------------
-- 5. email_events (open / click / bounce tracking)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES email_campaigns(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES email_contacts(id) ON DELETE SET NULL,
    sequence_id UUID,  -- nullable, for drip sequence emails
    event_type TEXT NOT NULL CHECK (event_type IN ('sent','delivered','opened','clicked','bounced','unsubscribed','complained','dropped')),
    link_url TEXT,  -- for click events
    ip_address TEXT,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_email_events_campaign ON email_events (campaign_id, event_type);
CREATE INDEX IF NOT EXISTS idx_email_events_contact ON email_events (contact_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_events_type ON email_events (event_type, created_at DESC);


-- ---------------------------------------------------------------------------
-- 6. email_templates
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'general',  -- 'general', 'welcome', 'nurture', 'announcement', 'transactional'
    subject TEXT DEFAULT '',
    html_content TEXT DEFAULT '',
    text_content TEXT DEFAULT '',
    thumbnail_url TEXT,
    builder_json JSONB DEFAULT '{}',  -- stores the drag-and-drop builder state
    is_system BOOLEAN DEFAULT false,  -- system templates can't be deleted
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- 7. email_sequences (drip campaigns)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_sequences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    trigger_type TEXT DEFAULT 'manual' CHECK (trigger_type IN ('manual','list_join','tag_added','pipeline_stage','score_threshold','api')),
    trigger_config JSONB DEFAULT '{}',
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft','active','paused','archived')),
    list_id UUID REFERENCES email_lists(id),
    from_name TEXT DEFAULT '',
    from_email TEXT DEFAULT '',
    total_enrolled INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- 8. email_sequence_steps
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_sequence_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_id UUID REFERENCES email_sequences(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    step_type TEXT DEFAULT 'email' CHECK (step_type IN ('email','delay','condition','action')),
    -- For email steps
    subject TEXT DEFAULT '',
    html_content TEXT DEFAULT '',
    text_content TEXT DEFAULT '',
    template_id UUID REFERENCES email_templates(id),
    -- For delay steps
    delay_days INTEGER DEFAULT 0,
    delay_hours INTEGER DEFAULT 0,
    delay_minutes INTEGER DEFAULT 0,
    -- For condition steps
    condition_config JSONB DEFAULT '{}',  -- {"field":"opened_previous","op":"eq","value":true}
    -- For action steps
    action_type TEXT,  -- 'add_tag', 'remove_tag', 'move_to_list', 'update_field', 'webhook'
    action_config JSONB DEFAULT '{}',
    -- Stats
    sent_count INTEGER DEFAULT 0,
    open_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(sequence_id, step_number)
);


-- ---------------------------------------------------------------------------
-- 9. email_sequence_enrollments
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_sequence_enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_id UUID REFERENCES email_sequences(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES email_contacts(id) ON DELETE CASCADE,
    current_step INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active','completed','paused','unsubscribed','failed')),
    enrolled_at TIMESTAMPTZ DEFAULT now(),
    last_step_at TIMESTAMPTZ,
    next_step_due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE(sequence_id, contact_id)
);
CREATE INDEX IF NOT EXISTS idx_seq_enrollments_due ON email_sequence_enrollments (next_step_due_at) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_seq_enrollments_sequence ON email_sequence_enrollments (sequence_id, status);


-- ---------------------------------------------------------------------------
-- 10. email_sender_config (SMTP / SendGrid / SES)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_sender_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    sender_type TEXT NOT NULL CHECK (sender_type IN ('smtp','sendgrid','ses')),
    config JSONB NOT NULL DEFAULT '{}',
    -- SMTP: {"host","port","username","password","use_tls"}
    -- SendGrid: {"api_key"}
    -- SES: {"access_key_id","secret_access_key","region"}
    from_email TEXT NOT NULL DEFAULT '',
    from_name TEXT DEFAULT '',
    is_default BOOLEAN DEFAULT false,
    is_verified BOOLEAN DEFAULT false,
    daily_limit INTEGER DEFAULT 500,
    sent_today INTEGER DEFAULT 0,
    last_reset_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- 11. email_unsubscribe_tokens (secure one-click unsubscribe)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_unsubscribe_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID REFERENCES email_contacts(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES email_campaigns(id) ON DELETE SET NULL,
    token TEXT UNIQUE NOT NULL,
    used BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    used_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unsub_token ON email_unsubscribe_tokens (token);
