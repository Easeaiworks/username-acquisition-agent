/**
 * API client for the Sean Lead Agent backend.
 * In dev, Vite proxies /api to localhost:8000.
 * In production, set VITE_API_URL to the Railway backend URL.
 */

const BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Get the stored Dashboard API key from sessionStorage.
 * This is set by the LoginPage / AuthProvider on successful login.
 */
function getApiKey() {
  try { return sessionStorage.getItem('sean_dashboard_api_key') || ''; }
  catch { return ''; }
}

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const apiKey = getApiKey();

  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Include the Dashboard API key if available
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  const res = await fetch(url, { ...options, headers });

  // If we get a 401/403, the key is invalid or missing — signal auth failure
  if (res.status === 401 || res.status === 403) {
    const error = new Error('Authentication failed');
    error.status = res.status;
    error.isAuthError = true;
    throw error;
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

// Auth
export async function login(email, password) {
  const url = `${BASE_URL}/api/auth/login`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (res.status === 401 || res.status === 403) {
    const err = await res.json().catch(() => ({ detail: 'Invalid credentials' }));
    throw new Error(err.detail || 'Invalid email or password');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Server error: ${res.status}`);
  }

  return res.json();  // { api_key, user_id, email, name, role }
}

// Dashboard
export const getDashboardOverview = () => request('/api/dashboard/overview');
export const getApprovalQueue = (page = 1) => request(`/api/dashboard/approval-queue?page=${page}`);
export const getTopOpportunities = (limit = 10) => request(`/api/dashboard/top-opportunities?limit=${limit}`);
export const getRecentActivity = (limit = 20) => request(`/api/dashboard/recent-activity?limit=${limit}`);
export const getOutreachStats = (days = 30) => request(`/api/dashboard/outreach-stats?days=${days}`);

// Companies
export const getCompanies = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/api/companies/?${qs}`);
};
export const getCompany = (id) => request(`/api/companies/${id}`);
export const approveCompany = (id) => request(`/api/companies/${id}/approve`, { method: 'POST' });
export const rejectCompany = (id) => request(`/api/companies/${id}/reject`, { method: 'POST' });
export const getPipelineSummary = () => request('/api/companies/pipeline/summary');

// Scoring
export const triggerScoringRun = (limit = 500) => request(`/api/scoring/run?limit=${limit}`, { method: 'POST' });
export const getCompanyScore = (id) => request(`/api/scoring/${id}`);
export const getScoringDistribution = () => request('/api/scoring/summary/distribution');

// Enrichment
export const triggerEnrichmentRun = (minScore = 0.5) => request(`/api/enrichment/run?min_score=${minScore}`, { method: 'POST' });
export const getCompanyContacts = (id) => request(`/api/enrichment/${id}/contacts`);
export const getEnrichmentStats = () => request('/api/enrichment/stats/summary');

// Outreach
export const triggerAutoOutreach = () => request('/api/outreach/auto-run', { method: 'POST' });
export const triggerFollowups = () => request('/api/outreach/followups', { method: 'POST' });
export const getPendingOutreach = (page = 1) => request(`/api/outreach/queue/pending?page=${page}`);
export const approveOutreach = (id) => request(`/api/outreach/${id}/approve`, { method: 'POST' });
export const rejectOutreach = (id) => request(`/api/outreach/${id}/reject`, { method: 'POST' });
export const getCompanyOutreach = (id) => request(`/api/outreach/company/${id}`);

// Reports
export const generateReport = () => request('/api/reports/generate', { method: 'POST' });
export const getTodayReport = () => request('/api/reports/today');
export const getLatestReport = () => request('/api/reports/latest');
export const getReportHistory = (days = 30) => request(`/api/reports/history?days=${days}`);
export const getReportTrends = (days = 14) => request(`/api/reports/trends?days=${days}`);
export const getReportByDate = (date) => request(`/api/reports/${date}`);

// Settings
export const getSettings = () => request('/api/settings/');
export const getSystemStatus = () => request('/api/settings/system/status');
export const updateSetting = (key, value) => request(`/api/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) });
export const testInstantly = () => request('/api/settings/instantly/test', { method: 'POST' });
export const autoSetupInstantly = (apiKey, campaignName) => request('/api/settings/instantly/auto-setup', { method: 'POST', body: JSON.stringify({ api_key: apiKey, campaign_name: campaignName }) });

// Admin — Users
export const getAdminUsers = () => request('/api/admin/users');
export const createAdminUser = (data) => request('/api/admin/users', { method: 'POST', body: JSON.stringify(data) });
export const updateAdminUser = (id, data) => request(`/api/admin/users/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteAdminUser = (id) => request(`/api/admin/users/${id}`, { method: 'DELETE' });
export const regenerateUserKey = (id) => request(`/api/admin/users/${id}/regenerate-key`, { method: 'POST' });

// Admin — Integrations
export const getIntegrations = () => request('/api/admin/integrations');
export const updateIntegration = (id, data) => request(`/api/admin/integrations/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const testIntegration = (id) => request(`/api/admin/integrations/${id}/test`, { method: 'POST' });
export const disconnectIntegration = (id) => request(`/api/admin/integrations/${id}/disconnect`, { method: 'DELETE' });
export const createIntegration = (data) => request('/api/admin/integrations', { method: 'POST', body: JSON.stringify(data) });

// Admin — Uploads
export const getUploads = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/api/admin/uploads?${qs}`);
};
export const deleteUpload = (id) => request(`/api/admin/uploads/${id}`, { method: 'DELETE' });
export const getUploadPreview = (id) => request(`/api/admin/uploads/${id}/preview`);

// For file upload — special handling (no Content-Type header, let browser set multipart boundary)
export async function uploadFile(file, category, description = '') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('category', category);
  if (description) formData.append('description', description);

  const apiKey = getApiKey();
  const res = await fetch(`${BASE_URL}/api/admin/uploads`, {
    method: 'POST',
    headers: { 'X-API-Key': apiKey },
    body: formData,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

// Admin — Templates
export const getTemplates = () => request('/api/admin/templates');
export const createTemplate = (data) => request('/api/admin/templates', { method: 'POST', body: JSON.stringify(data) });
export const updateTemplate = (id, data) => request(`/api/admin/templates/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteTemplate = (id) => request(`/api/admin/templates/${id}`, { method: 'DELETE' });
export const duplicateTemplate = (id) => request(`/api/admin/templates/${id}/duplicate`, { method: 'POST' });
export const previewTemplate = (data) => request('/api/admin/templates/preview', { method: 'POST', body: JSON.stringify(data) });

// Email — Contacts
export const getEmailContacts = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/api/email/contacts?${qs}`);
};
export const getEmailContact = (id) => request(`/api/email/contacts/${id}`);
export const createEmailContact = (data) => request('/api/email/contacts', { method: 'POST', body: JSON.stringify(data) });
export const updateEmailContact = (id, data) => request(`/api/email/contacts/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteEmailContact = (id) => request(`/api/email/contacts/${id}`, { method: 'DELETE' });
export const importEmailContacts = (contacts) => request('/api/email/contacts/import', { method: 'POST', body: JSON.stringify({ contacts }) });
export const addContactTags = (id, tags) => request(`/api/email/contacts/${id}/tags`, { method: 'POST', body: JSON.stringify({ tags }) });
export const removeContactTags = (id, tags) => request(`/api/email/contacts/${id}/tags`, { method: 'DELETE', body: JSON.stringify({ tags }) });
export const unsubscribeContact = (id) => request(`/api/email/contacts/${id}/unsubscribe`, { method: 'POST' });

// Email — Lists
export const getEmailLists = () => request('/api/email/lists');
export const getEmailList = (id) => request(`/api/email/lists/${id}`);
export const createEmailList = (data) => request('/api/email/lists', { method: 'POST', body: JSON.stringify(data) });
export const updateEmailList = (id, data) => request(`/api/email/lists/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteEmailList = (id) => request(`/api/email/lists/${id}`, { method: 'DELETE' });
export const getListMembers = (id, params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/api/email/lists/${id}/members?${qs}`);
};
export const addListMembers = (id, contactIds) => request(`/api/email/lists/${id}/members`, { method: 'POST', body: JSON.stringify({ contact_ids: contactIds }) });
export const removeListMember = (listId, contactId) => request(`/api/email/lists/${listId}/members/${contactId}`, { method: 'DELETE' });

// Email — Campaigns
export const getEmailCampaigns = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/api/email/campaigns?${qs}`);
};
export const getEmailCampaign = (id) => request(`/api/email/campaigns/${id}`);
export const createEmailCampaign = (data) => request('/api/email/campaigns', { method: 'POST', body: JSON.stringify(data) });
export const updateEmailCampaign = (id, data) => request(`/api/email/campaigns/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteEmailCampaign = (id) => request(`/api/email/campaigns/${id}`, { method: 'DELETE' });
export const scheduleCampaign = (id, data) => request(`/api/email/campaigns/${id}/schedule`, { method: 'POST', body: JSON.stringify(data) });
export const sendCampaign = (id) => request(`/api/email/campaigns/${id}/send`, { method: 'POST' });
export const pauseCampaign = (id) => request(`/api/email/campaigns/${id}/pause`, { method: 'POST' });
export const duplicateCampaign = (id) => request(`/api/email/campaigns/${id}/duplicate`, { method: 'POST' });
export const getCampaignStats = (id) => request(`/api/email/campaigns/${id}/stats`);
export const previewCampaign = (data) => request('/api/email/campaigns/preview', { method: 'POST', body: JSON.stringify(data) });

// Email — Sequences
export const getEmailSequences = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/api/email/sequences?${qs}`);
};
export const getEmailSequence = (id) => request(`/api/email/sequences/${id}`);
export const createEmailSequence = (data) => request('/api/email/sequences', { method: 'POST', body: JSON.stringify(data) });
export const updateEmailSequence = (id, data) => request(`/api/email/sequences/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteEmailSequence = (id) => request(`/api/email/sequences/${id}`, { method: 'DELETE' });
export const activateSequence = (id) => request(`/api/email/sequences/${id}/activate`, { method: 'POST' });
export const pauseSequence = (id) => request(`/api/email/sequences/${id}/pause`, { method: 'POST' });
export const getSequenceSteps = (id) => request(`/api/email/sequences/${id}/steps`);
export const createSequenceStep = (id, data) => request(`/api/email/sequences/${id}/steps`, { method: 'POST', body: JSON.stringify(data) });
export const updateSequenceStep = (seqId, stepId, data) => request(`/api/email/sequences/${seqId}/steps/${stepId}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteSequenceStep = (seqId, stepId) => request(`/api/email/sequences/${seqId}/steps/${stepId}`, { method: 'DELETE' });
export const enrollContacts = (id, contactIds) => request(`/api/email/sequences/${id}/enroll`, { method: 'POST', body: JSON.stringify({ contact_ids: contactIds }) });
export const unenrollContact = (seqId, contactId) => request(`/api/email/sequences/${seqId}/enroll/${contactId}`, { method: 'DELETE' });
export const getSequenceEnrollments = (id) => request(`/api/email/sequences/${id}/enrollments`);

// Email — Senders
export const getEmailSenders = () => request('/api/email/senders');
export const getEmailSender = (id) => request(`/api/email/senders/${id}`);
export const createEmailSender = (data) => request('/api/email/senders', { method: 'POST', body: JSON.stringify(data) });
export const updateEmailSender = (id, data) => request(`/api/email/senders/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteEmailSender = (id) => request(`/api/email/senders/${id}`, { method: 'DELETE' });
export const verifyEmailSender = (id) => request(`/api/email/senders/${id}/verify`, { method: 'POST' });
export const setDefaultSender = (id) => request(`/api/email/senders/${id}/set-default`, { method: 'POST' });

// Automations
export const getWorkflows = () => request('/api/automations/workflows');
export const getWorkflow = (id) => request(`/api/automations/workflows/${id}`);
export const createWorkflow = (data) => request('/api/automations/workflows', { method: 'POST', body: JSON.stringify(data) });
export const updateWorkflow = (id, data) => request(`/api/automations/workflows/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteWorkflow = (id) => request(`/api/automations/workflows/${id}`, { method: 'DELETE' });
export const toggleWorkflow = (id) => request(`/api/automations/workflows/${id}/toggle`, { method: 'POST' });
export const runWorkflow = (id) => request(`/api/automations/workflows/${id}/run`, { method: 'POST' });
export const getWorkflowRuns = (id, params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/api/automations/workflows/${id}/runs?${qs}`);
};
export const getWorkflowRun = (id) => request(`/api/automations/runs/${id}`);
export const getTriggerTypes = () => request('/api/automations/trigger-types');
export const getActionTypes = () => request('/api/automations/action-types');

// Webhooks
export const getWebhooks = () => request('/api/webhooks');
export const getWebhook = (id) => request(`/api/webhooks/${id}`);
export const createWebhook = (data) => request('/api/webhooks', { method: 'POST', body: JSON.stringify(data) });
export const updateWebhook = (id, data) => request(`/api/webhooks/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteWebhook = (id) => request(`/api/webhooks/${id}`, { method: 'DELETE' });
export const toggleWebhook = (id) => request(`/api/webhooks/${id}/toggle`, { method: 'POST' });
export const testWebhook = (id) => request(`/api/webhooks/${id}/test`, { method: 'POST' });
export const getWebhookDeliveries = (id, params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/api/webhooks/${id}/deliveries?${qs}`);
};
export const getWebhookEvents = () => request('/api/webhooks/events');
