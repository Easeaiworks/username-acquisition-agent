-- ============================================================
-- Migration 007: Automation Engine — workflows, webhook endpoints, execution logs
-- ============================================================

-- 1. Automation workflows
CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    trigger_type TEXT NOT NULL,  -- 'lead_scored', 'company_approved', 'outreach_sent', 'stage_changed', 'score_threshold', 'manual', 'schedule'
    trigger_config JSONB DEFAULT '{}',  -- e.g. {"min_score": 0.8, "stage_from": "new", "stage_to": "contacted"}
    conditions JSONB DEFAULT '[]',  -- array of condition objects [{"field": "score", "op": "gte", "value": 0.8}]
    actions JSONB DEFAULT '[]',  -- array of action objects [{"type": "mailchimp_add", "config": {"list_id": "...", "tags": ["hot"]}}]
    is_enabled BOOLEAN DEFAULT true,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_triggered_at TIMESTAMPTZ,
    trigger_count INTEGER DEFAULT 0
);

-- 2. Workflow execution log
CREATE TABLE IF NOT EXISTS workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    trigger_event TEXT NOT NULL,
    trigger_data JSONB DEFAULT '{}',
    status TEXT DEFAULT 'running',  -- 'running', 'completed', 'failed', 'skipped'
    actions_executed JSONB DEFAULT '[]',  -- log of each action result
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER
);

-- 3. Webhook endpoints
CREATE TABLE IF NOT EXISTS webhook_endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    secret TEXT,  -- for HMAC signing
    events TEXT[] DEFAULT '{}',  -- array of event types to subscribe to
    is_active BOOLEAN DEFAULT true,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_triggered_at TIMESTAMPTZ,
    failure_count INTEGER DEFAULT 0
);

-- 4. Webhook delivery log
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID REFERENCES webhook_endpoints(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    success BOOLEAN DEFAULT false,
    attempt INTEGER DEFAULT 1,
    delivered_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_workflows_trigger ON workflows (trigger_type) WHERE is_enabled = true;
CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow ON workflow_runs (workflow_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook ON webhook_deliveries (webhook_id, delivered_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_events ON webhook_endpoints USING GIN (events);
