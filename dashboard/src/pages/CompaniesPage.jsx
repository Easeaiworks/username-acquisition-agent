import { useState, useEffect, useCallback } from 'react';
import DataTable from '../components/DataTable';
import { StatusBadge, PriorityBadge } from '../components/Badge';
import { getCompanies, getCompany } from '../lib/api';
import { X, ExternalLink, Globe, Users, Calendar } from 'lucide-react';

function CompanyDrawer({ companyId, onClose }) {
  const [company, setCompany] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    getCompany(companyId)
      .then(setCompany)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [companyId]);

  if (!companyId) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white shadow-xl overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-5 py-4 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Company Details</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        ) : company ? (
          <div className="p-5 space-y-5">
            <div>
              <h4 className="text-lg font-bold text-gray-900">{company.brand_name}</h4>
              {company.legal_name && company.legal_name !== company.brand_name && (
                <p className="text-sm text-gray-500">{company.legal_name}</p>
              )}
              <div className="flex gap-2 mt-2">
                <StatusBadge status={company.pipeline_stage} />
                {company.priority_bucket && <PriorityBadge priority={company.priority_bucket} />}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-start gap-2">
                <Globe size={14} className="text-gray-400 mt-0.5" />
                <div>
                  <p className="text-gray-500">Domain</p>
                  <p className="font-medium text-gray-900">{company.domain || '—'}</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <Users size={14} className="text-gray-400 mt-0.5" />
                <div>
                  <p className="text-gray-500">Size</p>
                  <p className="font-medium text-gray-900">{company.employee_range || '—'}</p>
                </div>
              </div>
              <div>
                <p className="text-gray-500">Industry</p>
                <p className="font-medium text-gray-900 capitalize">{company.industry || '—'}</p>
              </div>
              <div>
                <p className="text-gray-500">HQ</p>
                <p className="font-medium text-gray-900">{company.hq_country || '—'}</p>
              </div>
            </div>

            {company.composite_score != null && (
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-xs text-gray-500 font-medium mb-2">Scoring Breakdown</p>
                <div className="text-2xl font-bold text-gray-900 mb-3">
                  {company.composite_score.toFixed(3)}
                </div>
                <div className="space-y-2 text-sm">
                  {[
                    ['Brand Value', company.brand_value_score, 0.35],
                    ['Handle Pain', company.handle_pain_score, 0.30],
                    ['Urgency', company.urgency_score, 0.20],
                    ['Reachability', company.reachability_score, 0.15],
                  ].map(([label, val, weight]) => (
                    <div key={label} className="flex items-center justify-between">
                      <span className="text-gray-600">{label} ({(weight * 100).toFixed(0)}%)</span>
                      <div className="flex items-center gap-2">
                        <div className="w-20 bg-gray-200 rounded-full h-1.5">
                          <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: `${(val || 0) * 100}%` }} />
                        </div>
                        <span className="font-mono text-xs w-8 text-right">{val != null ? val.toFixed(2) : '—'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {company.platform_handles && company.platform_handles.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 font-medium mb-2">Platform Handles</p>
                <div className="space-y-2">
                  {company.platform_handles.map((h, i) => (
                    <div key={i} className="flex items-center justify-between text-sm bg-gray-50 rounded-lg px-3 py-2">
                      <span className="capitalize font-medium text-gray-700">{h.platform}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-600">{h.current_handle || 'None'}</span>
                        {h.is_available && <span className="text-xs text-green-600 font-medium">AVAILABLE</span>}
                        {h.is_dormant && <span className="text-xs text-amber-600 font-medium">DORMANT</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="p-5 text-sm text-gray-400">Company not found</p>
        )}
      </div>
    </div>
  );
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [filters, setFilters] = useState({ stage: '', search: '' });
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, limit: 50 };
      if (filters.stage) params.stage = filters.stage;
      if (filters.search) params.search = filters.search;
      const data = await getCompanies(params);
      setCompanies(Array.isArray(data) ? data : data.items || []);
    } catch (e) {
      console.error('Companies load error:', e);
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => { load(); }, [load]);

  const columns = [
    { key: 'brand_name', label: 'Company' },
    { key: 'domain', label: 'Domain', render: (v) => v || '—' },
    { key: 'industry', label: 'Industry', render: (v) => <span className="capitalize">{v || '—'}</span> },
    { key: 'employee_range', label: 'Size', render: (v) => v || '—' },
    {
      key: 'composite_score',
      label: 'Score',
      render: (v) => v != null ? <span className="font-mono">{v.toFixed(2)}</span> : '—',
    },
    { key: 'pipeline_stage', label: 'Stage', render: (v) => <StatusBadge status={v} /> },
    {
      key: 'created_at',
      label: 'Added',
      render: (v) => v ? new Date(v).toLocaleDateString() : '—',
    },
  ];

  const STAGES = ['new', 'scanned', 'scored', 'enriched', 'qualified', 'approval_queue', 'outreach_active', 'meeting_booked', 'rejected', 'parked'];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Companies</h2>
        <p className="text-sm text-gray-500 mt-1">All companies in the acquisition pipeline</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search companies..."
          value={filters.search}
          onChange={(e) => { setFilters(f => ({ ...f, search: e.target.value })); setPage(1); }}
          className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 w-64 bg-white"
        />
        <select
          value={filters.stage}
          onChange={(e) => { setFilters(f => ({ ...f, stage: e.target.value })); setPage(1); }}
          className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white text-gray-700"
        >
          <option value="">All Stages</option>
          {STAGES.map(s => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={companies}
            onRowClick={(row) => setSelectedId(row.id)}
            emptyMessage="No companies found matching your criteria"
          />
          <div className="flex items-center justify-between text-sm">
            <p className="text-gray-500">{companies.length} companies shown</p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1 rounded border border-gray-300 text-gray-600 disabled:opacity-40"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={companies.length < 50}
                className="px-3 py-1 rounded border border-gray-300 text-gray-600 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}

      <CompanyDrawer companyId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
