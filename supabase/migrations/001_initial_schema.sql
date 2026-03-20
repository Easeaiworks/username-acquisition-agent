-- =============================================================================
-- Sean Lead Agent — Initial Database Schema
-- Run this in Supabase SQL Editor to create all required tables.
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Companies — core entity representing acquisition targets
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand_name TEXT NOT NULL,
    legal_name TEXT,
    domain TEXT,
    industry TEXT,
    employee_range TEXT,
    hq_country TEXT,
    hq_state TEXT,
    founded_year INTEGER,
    is_public BOOLEAN DEFAULT FALSE,
    annual_revenue_range TEXT,
    funding_stage TEXT,

    -- Pipeline tracking
    pipeline_stage TEXT NOT NULL DEFAULT 'new'
        CHECK (pipeline_stage IN (
            'new', 'scanned', 'scored', 'enriched', 'qualified',
            'approval_queue', 'outreach_active', 'meeting_booked',
            'rejected', 'parked'
        )),

    -- Scoring
    composite_score DOUBLE PRECISION,
    total_opportunity_score DOUBLE PRECISION,
    brand_value_score DOUBLE PRECISION,
    handle_pain_score DOUBLE PRECISION,
    urgency_score DOUBLE PRECISION,
    reachability_score DOUBLE PRECISION,
    priority_bucket TEXT
        CHECK (priority_bucket IN ('critical', 'very_high', 'high', 'medium', 'low')),
    scored_at TIMESTAMPTZ,

    -- Outreach
    approved_for_outreach BOOLEAN DEFAULT FALSE,
    enrichment_status TEXT DEFAULT 'pending',

    -- Metadata
    source TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_companies_pipeline_stage ON companies(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_companies_priority_bucket ON companies(priority_bucket);
CREATE INDEX IF NOT EXISTS idx_companies_composite_score ON companies(composite_score DESC);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_brand_name ON companies(brand_name);
CREATE INDEX IF NOT EXISTS idx_companies_created_at ON companies(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_companies_scored_at ON companies(scored_at DESC);

-- ---------------------------------------------------------------------------
-- Platform Handles — social media handle data per company per platform
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_handles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    platform TEXT NOT NULL
        CHECK (platform IN ('instagram', 'tiktok', 'twitch', 'youtube')),

    -- Handle status
    current_handle TEXT,
    ideal_handle TEXT,
    is_available BOOLEAN DEFAULT FALSE,
    is_dormant BOOLEAN DEFAULT FALSE,
    mismatch_type TEXT,
    mismatch_severity DOUBLE PRECISION,

    -- Platform-specific data
    follower_count INTEGER,
    last_post_date TIMESTAMPTZ,
    account_verified BOOLEAN DEFAULT FALSE,

    -- Scan metadata
    scanned_at TIMESTAMPTZ DEFAULT NOW(),
    scan_source TEXT,
    raw_data JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One record per company per platform
    UNIQUE(company_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_platform_handles_company ON platform_handles(company_id);
CREATE INDEX IF NOT EXISTS idx_platform_handles_platform ON platform_handles(platform);
CREATE INDEX IF NOT EXISTS idx_platform_handles_available ON platform_handles(is_available) WHERE is_available = TRUE;
CREATE INDEX IF NOT EXISTS idx_platform_handles_dormant ON platform_handles(is_dormant) WHERE is_dormant = TRUE;

-- ---------------------------------------------------------------------------
-- Contacts — enriched decision-maker contacts per company
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- Identity
    first_name TEXT,
    last_name TEXT,
    full_name TEXT,
    email TEXT,
    email_confidence DOUBLE PRECISION,
    phone TEXT,
    linkedin_url TEXT,

    -- Role
    title TEXT,
    seniority TEXT CHECK (seniority IN ('c_suite', 'vp', 'director', 'manager', 'other')),
    department TEXT CHECK (department IN ('marketing', 'executive', 'communications', 'sales', 'other')),

    -- Enrichment source
    source TEXT,
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,

    -- Ranking
    contact_rank INTEGER,

    -- Suppression
    suppressed BOOLEAN DEFAULT FALSE,
    suppressed_at TIMESTAMPTZ,
    suppression_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_seniority ON contacts(seniority);
CREATE INDEX IF NOT EXISTS idx_contacts_suppressed ON contacts(suppressed) WHERE suppressed = FALSE;

-- ---------------------------------------------------------------------------
-- Outreach Sequences — email sequence tracking
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outreach_sequences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,

    -- Sequence state
    sequence_step INTEGER NOT NULL DEFAULT 1 CHECK (sequence_step BETWEEN 1 AND 4),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft', 'queued', 'sent', 'delivered', 'opened',
            'clicked', 'replied', 'bounced', 'failed'
        )),

    -- Content
    subject TEXT,
    body TEXT,
    body_preview TEXT,

    -- Timestamps
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ,
    replied_at TIMESTAMPTZ,
    next_followup_at TIMESTAMPTZ,

    -- Response handling
    response_text TEXT,
    response_sentiment TEXT
        CHECK (response_sentiment IN ('positive', 'neutral', 'negative', 'objection', 'ooo', 'unsubscribe')),
    response_confidence DOUBLE PRECISION,
    response_classified_at TIMESTAMPTZ,
    reviewed BOOLEAN DEFAULT FALSE,

    -- Meeting tracking
    meeting_booked BOOLEAN DEFAULT FALSE,
    meeting_booked_at TIMESTAMPTZ,

    -- Email provider tracking
    provider TEXT,
    provider_message_id TEXT,

    -- Compliance
    approved BOOLEAN DEFAULT FALSE,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outreach_company ON outreach_sequences(company_id);
CREATE INDEX IF NOT EXISTS idx_outreach_contact ON outreach_sequences(contact_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_sequences(status);
CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach_sequences(sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_outreach_next_followup ON outreach_sequences(next_followup_at)
    WHERE status IN ('sent', 'delivered', 'opened');
CREATE INDEX IF NOT EXISTS idx_outreach_meeting ON outreach_sequences(meeting_booked)
    WHERE meeting_booked = TRUE;
CREATE INDEX IF NOT EXISTS idx_outreach_sentiment ON outreach_sequences(response_sentiment);

-- ---------------------------------------------------------------------------
-- Audit Log — tracks all significant system actions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type TEXT NOT NULL,
    entity_id UUID,
    action TEXT NOT NULL,
    description TEXT,
    type TEXT,
    metadata JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);

-- ---------------------------------------------------------------------------
-- Daily Reports — persisted daily analytics
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_date DATE NOT NULL UNIQUE,
    generated_at TIMESTAMPTZ NOT NULL,

    -- Pipeline metrics
    pipeline_total INTEGER DEFAULT 0,
    new_companies INTEGER DEFAULT 0,
    stage_movements INTEGER DEFAULT 0,

    -- Scoring metrics
    scored_today INTEGER DEFAULT 0,
    avg_score DOUBLE PRECISION DEFAULT 0,
    high_value_today INTEGER DEFAULT 0,

    -- Outreach metrics
    emails_sent INTEGER DEFAULT 0,
    replies_received INTEGER DEFAULT 0,
    reply_rate DOUBLE PRECISION DEFAULT 0,
    meetings_booked INTEGER DEFAULT 0,
    bounces INTEGER DEFAULT 0,
    active_sequences INTEGER DEFAULT 0,

    -- Attention metrics
    pending_approvals INTEGER DEFAULT 0,
    attention_items INTEGER DEFAULT 0,

    -- Full report payload for detailed analysis
    full_report_json JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON daily_reports(report_date DESC);

-- ---------------------------------------------------------------------------
-- Suppression List — global email suppression
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppression_list (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT NOT NULL UNIQUE,
    reason TEXT NOT NULL DEFAULT 'unsubscribe'
        CHECK (reason IN ('unsubscribe', 'bounce', 'complaint', 'manual')),
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suppression_email ON suppression_list(email);

-- ---------------------------------------------------------------------------
-- Auto-update updated_at timestamps
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER platform_handles_updated_at
    BEFORE UPDATE ON platform_handles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER contacts_updated_at
    BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER outreach_sequences_updated_at
    BEFORE UPDATE ON outreach_sequences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security (RLS) — enabled but permissive for service_role
-- ---------------------------------------------------------------------------
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_handles ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE outreach_sequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppression_list ENABLE ROW LEVEL SECURITY;

-- Service role policies (full access for backend)
CREATE POLICY "service_role_all" ON companies FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON platform_handles FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON contacts FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON outreach_sequences FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON audit_log FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON daily_reports FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON suppression_list FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- Anon role: read-only on companies (for dashboard if needed)
CREATE POLICY "anon_read_companies" ON companies FOR SELECT TO anon USING (TRUE);
CREATE POLICY "anon_read_reports" ON daily_reports FOR SELECT TO anon USING (TRUE);
