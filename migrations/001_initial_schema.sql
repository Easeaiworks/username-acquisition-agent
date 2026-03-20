-- =============================================================================
-- Sean Lead Agent — Initial Database Schema
-- Run this in Supabase SQL Editor to create all tables
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- COMPANIES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_name TEXT NOT NULL,
    legal_name TEXT,
    aliases TEXT[] DEFAULT '{}',
    domain TEXT,
    industry TEXT,
    vertical TEXT,
    employee_range TEXT,
    country TEXT,
    city TEXT,
    founding_year INTEGER,
    is_public BOOLEAN DEFAULT FALSE,
    consumer_facing_score FLOAT DEFAULT 0,

    -- Scoring
    brand_value_score FLOAT DEFAULT 0,
    handle_pain_score FLOAT DEFAULT 0,
    urgency_score FLOAT DEFAULT 0,
    reachability_score FLOAT DEFAULT 0,
    total_opportunity_score FLOAT DEFAULT 0,
    priority_bucket TEXT,

    -- Signals
    urgency_signals JSONB DEFAULT '{}',
    enrichment_data JSONB DEFAULT '{}',

    -- Pipeline state
    pipeline_stage TEXT DEFAULT 'discovered',
    approved_for_outreach BOOLEAN DEFAULT FALSE,

    -- Metadata
    source TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    scanned_at TIMESTAMPTZ,
    scored_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_companies_score ON companies(total_opportunity_score DESC);
CREATE INDEX IF NOT EXISTS idx_companies_stage ON companies(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_brand ON companies(brand_name);

-- =============================================================================
-- PLATFORM HANDLES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS platform_handles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,

    -- What we found
    observed_handle TEXT,
    observed_display_name TEXT,

    -- Analysis
    normalized_candidates TEXT[] DEFAULT '{}',
    exact_match BOOLEAN DEFAULT FALSE,
    mismatch_type TEXT DEFAULT 'none',
    mismatch_severity FLOAT DEFAULT 0,
    handle_available BOOLEAN,
    current_holder_info JSONB,

    -- Account activity (dormant holder detection)
    account_exists BOOLEAN,
    last_post_date TIMESTAMPTZ,
    follower_count INTEGER,
    following_count INTEGER,
    post_count INTEGER,
    account_dormant BOOLEAN DEFAULT FALSE,
    dormancy_months INTEGER,
    account_created_at TIMESTAMPTZ,

    -- Confidence
    confidence FLOAT DEFAULT 0,
    data_source TEXT,

    -- Metadata
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    raw_response JSONB
);

CREATE INDEX IF NOT EXISTS idx_handles_company ON platform_handles(company_id);
CREATE INDEX IF NOT EXISTS idx_handles_platform ON platform_handles(platform);
CREATE INDEX IF NOT EXISTS idx_handles_mismatch ON platform_handles(mismatch_type);
CREATE INDEX IF NOT EXISTS idx_handles_dormant ON platform_handles(account_dormant) WHERE account_dormant = TRUE;

-- =============================================================================
-- CONTACTS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    -- Identity
    first_name TEXT,
    last_name TEXT,
    full_name TEXT,
    title TEXT,
    seniority_level TEXT,
    department TEXT,

    -- Contact info
    email TEXT,
    email_confidence FLOAT,
    email_source TEXT,
    email_type TEXT,
    linkedin_url TEXT,
    phone TEXT,

    -- Enrichment
    rocketreach_id TEXT,
    hunter_result JSONB,
    enrichment_data JSONB,

    -- Outreach state
    outreach_priority INTEGER DEFAULT 0,
    do_not_contact BOOLEAN DEFAULT FALSE,
    suppressed_reason TEXT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    verified_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_priority ON contacts(outreach_priority);

-- =============================================================================
-- OUTREACH SEQUENCES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS outreach_sequences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    -- Sequence config
    channel TEXT NOT NULL,
    sequence_step INTEGER DEFAULT 1,
    max_steps INTEGER DEFAULT 4,

    -- Message
    subject TEXT,
    message_body TEXT,
    message_variant TEXT,
    personalization_data JSONB,

    -- Timing
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    next_followup_at TIMESTAMPTZ,

    -- Response tracking
    status TEXT DEFAULT 'draft',
    response_text TEXT,
    response_sentiment TEXT,
    response_classified_at TIMESTAMPTZ,

    -- Outcome
    meeting_booked BOOLEAN DEFAULT FALSE,
    meeting_datetime TIMESTAMPTZ,
    meeting_link TEXT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outreach_contact ON outreach_sequences(contact_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_sequences(status);
CREATE INDEX IF NOT EXISTS idx_outreach_scheduled ON outreach_sequences(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_outreach_followup ON outreach_sequences(next_followup_at);

-- =============================================================================
-- DAILY REPORTS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS daily_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date DATE NOT NULL UNIQUE,

    -- Scanner metrics
    companies_scanned INTEGER DEFAULT 0,
    new_companies_discovered INTEGER DEFAULT 0,
    opportunities_found INTEGER DEFAULT 0,
    critical_opportunities INTEGER DEFAULT 0,

    -- Enrichment metrics
    contacts_enriched INTEGER DEFAULT 0,
    emails_verified INTEGER DEFAULT 0,

    -- Outreach metrics
    emails_sent INTEGER DEFAULT 0,
    linkedin_messages_sent INTEGER DEFAULT 0,
    calls_attempted INTEGER DEFAULT 0,

    -- Response metrics
    replies_received INTEGER DEFAULT 0,
    positive_replies INTEGER DEFAULT 0,
    meetings_booked INTEGER DEFAULT 0,

    -- Pipeline snapshot
    pipeline_snapshot JSONB,
    top_opportunities JSONB,

    -- Metadata
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- AUDIT LOG TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id UUID,
    details JSONB,
    api_calls_made INTEGER DEFAULT 0,
    api_cost_estimate FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

-- =============================================================================
-- SUPPRESSION LIST TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS suppression_list (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT,
    domain TEXT,
    company_name TEXT,
    reason TEXT NOT NULL,
    added_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suppression_email ON suppression_list(email);
CREATE INDEX IF NOT EXISTS idx_suppression_domain ON suppression_list(domain);

-- =============================================================================
-- ROW LEVEL SECURITY POLICIES
-- =============================================================================
-- Enable RLS on all tables
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_handles ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE outreach_sequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppression_list ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (backend pipelines)
CREATE POLICY "service_role_all" ON companies FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON platform_handles FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON contacts FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON outreach_sequences FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON daily_reports FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON audit_log FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON suppression_list FOR ALL USING (auth.role() = 'service_role');

-- Authenticated users can read all tables (dashboard access)
CREATE POLICY "authenticated_read" ON companies FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON platform_handles FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON contacts FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON outreach_sequences FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON daily_reports FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON audit_log FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON suppression_list FOR SELECT USING (auth.role() = 'authenticated');

-- Authenticated users can update company approval status (approve from dashboard)
CREATE POLICY "authenticated_approve" ON companies FOR UPDATE
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- =============================================================================
-- UPDATED_AT TRIGGER
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contacts_updated_at
    BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_outreach_updated_at
    BEFORE UPDATE ON outreach_sequences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
