/**
 * API client for the Sean Lead Agent backend.
 * In dev, Vite proxies /api to localhost:8000.
 * In production, set VITE_API_URL to the Railway backend URL.
 */

const BASE_URL = import.meta.env.VITE_API_URL || '';

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
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
