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
      <div className="absolute inset-0" style={{ background: 'rgba(15, 26, 46, 0.5)', backdropFilter: 'blur(4px)' }} onClick={onClose} />
      <div className="relative w-full max-w-lg overflow-y-auto" style={{
        background: 'linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(238,241,248,0.98) 100%)',
        boxShadow: '-8px 0 40px rgba(15, 26, 46, 0.15)',
      }}>
        <div className="sticky top-0 px-5 py-4 flex items-center justify-between" style={{
          background: 'rgba(255,255,255,0.9)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid rgba(91,126,194,0.1)',
        }}>
          <h3 className="font-semibold" style={{ color: '#1b2a4a' }}>Company Details</h3>
          <button onClick={onClose} className="transition-colors" style={{ color: '#9aa5bd' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#374a6d'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = '#9aa5bd'; }}
          >
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
          </div>
        ) : company ? (
          <div className="p-5 space-y-5">
            <div>
              <h4 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>{company.brand_name}</h4>
              {company.legal_name && company.legal_name !== company.brand_name && (
                <p className="text-sm" style={{ color: '#6b7a99' }}>{company.legal_name}</p>
              )}
              <div className="flex gap-2 mt-2">
                <StatusBadge status={company.pipeline_stage} />
                {company.priority_bucket && <PriorityBadge priority={company.priority_bucket} />}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-start gap-2">
                <Globe size={14} className="mt-0.5" style={{ color: '#9aa5bd' }} />
                <div>
                  <p style={{ color: '#6b7a99' }}>Domain</p>
                  <p className="font-medium" style={{ color: '#1b2a4a' }}>{company.domain || '—'}</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <Users size={14} className="mt-0.5" style={{ color: '#9aa5bd' }} />
                <div>
                  <p style={{ color: '#6b7a99' }}>Size</p>
                  <p className="font-medium" style={{ color: '#1b2a4a' }}>{company.employee_range || '—'}</p>
                </div>
              </div>
              <div>
                <p style={{ color: '#6b7a99' }}>Industry</p>
                <p className="font-medium capitalize" style={{ color: '#1b2a4a' }}>{company.industry || '—'}</p>
              </div>
              <div>
                <p style={{ color: '#6b7a99' }}>HQ</p>
                <p className="font-medium" style={{ color: '#1b2a4a' }}>{company.hq_country || '—'}</p>
              </div>
            </div>

            {company.composite_score != null && (
              <div className="rounded-lg p-4" style={{
                background: 'linear-gradient(145deg, rgba(238,241,248,0.8), rgba(224,230,242,0.6))',
                border: '1px solid rgba(91,126,194,0.1)',
              }}>
                <p className="text-xs font-medium mb-2" style={{ color: '#6b7a99' }}>Scoring Breakdown</p>
                <div className="text-2xl font-bold mb-3" style={{ color: '#1b2a4a' }}>
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
                      <span style={{ color: '#6b7a99' }}>{label} ({(weight * 100).toFixed(0)}%)</span>
                      <div className="flex items-center gap-2">
                        <div className="w-20 rounded-full h-1.5" style={{ background: 'rgba(58,82,137,0.12)' }}>
                          <div className="h-1.5 rounded-full" style={{ width: `${(val || 0) * 100}%`, background: 'linear-gradient(90deg, #3a5289, #5b7ec2)' }} />
                        </div>
                        <span className="font-mono text-xs w-8 text-right" style={{ color: '#3a5289' }}>{val != null ? val.toFixed(2) : '—'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {company.platform_handles && company.platform_handles.length > 0 && (
              <div>
                <p className="text-xs font-medium mb-2" style={{ color: '#6b7a99' }}>Platform Handles</p>
                <div className="space-y-2">
                  {company.platform_handles.map((h, i) => (
                    <div key={i} className="flex items-center justify-between text-sm rounded-lg px-3 py-2" style={{
                      background: 'linear-gradient(145deg, rgba(238,241,248,0.6), rgba(224,230,242,0.4))',
                      border: '1px solid rgba(91,126,194,0.08)',
                    }}>
                      <span className="capitalize font-medium" style={{ color: '#374a6d' }}>{h.platform}</span>
                      <div className="flex items-center gap-2">
                        <span style={{ color: '#6b7a99' }}>{h.current_handle || 'None'}</span>
                        {h.is_available && <span className="text-xs font-medium" style={{ color: '#059669' }}>AVAILABLE</span>}
                        {h.is_dormant && <span className="text-xs font-medium" style={{ color: '#d97706' }}>DORMANT</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="p-5 text-sm" style={{ color: '#9aa5bd' }}>Company not found</p>
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
      render: (v) => v != null ? <span className="font-mono" style={{ color: '#3a5289' }}>{v.toFixed(2)}</span> : '—',
    },
    { key: 'pipeline_stage', label: 'Stage', render: (v) => <StatusBadge status={v} /> },
    {
      key: 'created_at',
      label: 'Added',
      render: (v) => v ? new Date(v).toLocaleDateString() : '—',
    },
  ];

  const STAGES = ['new', 'scanned', 'scored', 'enriched', 'qualified', 'approval_queue', 'outreach_active', 'meeting_booked', 'rejected', 'parked'];

  const inputStyle = {
    background: 'rgba(255,255,255,0.9)',
    border: '1px solid rgba(91,126,194,0.2)',
    color: '#374a6d',
    outline: 'none',
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Companies</h2>
        <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>All companies in the acquisition pipeline</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search companies..."
          value={filters.search}
          onChange={(e) => { setFilters(f => ({ ...f, search: e.target.value })); setPage(1); }}
          className="text-sm rounded-lg px-3 py-1.5 w-64"
          style={inputStyle}
        />
        <select
          value={filters.stage}
          onChange={(e) => { setFilters(f => ({ ...f, stage: e.target.value })); setPage(1); }}
          className="text-sm rounded-lg px-3 py-1.5"
          style={inputStyle}
        >
          <option value="">All Stages</option>
          {STAGES.map(s => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
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
            <p style={{ color: '#6b7a99' }}>{companies.length} companies shown</p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1 rounded-lg text-sm font-medium disabled:opacity-40 transition-all duration-200"
                style={{ border: '1px solid rgba(91,126,194,0.2)', color: '#374a6d', background: 'rgba(255,255,255,0.8)' }}
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={companies.length < 50}
                className="px-3 py-1 rounded-lg text-sm font-medium disabled:opacity-40 transition-all duration-200"
                style={{ border: '1px solid rgba(91,126,194,0.2)', color: '#374a6d', background: 'rgba(255,255,255,0.8)' }}
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
