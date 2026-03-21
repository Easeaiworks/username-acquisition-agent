import { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, Eye, ChevronDown, ChevronUp } from 'lucide-react';
import { PriorityBadge } from '../components/Badge';
import { getApprovalQueue, approveCompany, rejectCompany, approveOutreach, rejectOutreach } from '../lib/api';

function ApprovalCard({ item, type, onAction }) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(null);

  const handleAction = async (action) => {
    setLoading(action);
    try {
      await onAction(item.id, action);
    } catch (e) {
      console.error(`${action} error:`, e);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="glass-card rounded-xl overflow-hidden">
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h4 className="font-medium truncate" style={{ color: '#1b2a4a' }}>
                {item.brand_name || item.company_name || 'Unknown'}
              </h4>
              {item.priority_bucket && <PriorityBadge priority={item.priority_bucket} />}
            </div>
            <p className="text-sm mt-0.5" style={{ color: '#6b7a99' }}>
              {type === 'company'
                ? `Score: ${item.composite_score?.toFixed(2) || '—'} · ${item.industry || 'Unknown industry'}`
                : `To: ${item.contact_name || '—'} · Step ${item.sequence_step || 1}/4`}
            </p>
          </div>

          <div className="flex items-center gap-1.5 ml-3">
            <button
              onClick={() => handleAction('approve')}
              disabled={loading !== null}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg text-white disabled:opacity-50 transition-all duration-200"
              style={{ background: 'linear-gradient(135deg, #059669, #047857)', boxShadow: '0 2px 6px rgba(5,150,105,0.25)' }}
            >
              {loading === 'approve' ? (
                <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white" />
              ) : (
                <CheckCircle2 size={13} />
              )}
              Approve
            </button>
            <button
              onClick={() => handleAction('reject')}
              disabled={loading !== null}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg disabled:opacity-50 transition-all duration-200"
              style={{ border: '1px solid rgba(239,68,68,0.2)', color: '#dc2626', background: 'rgba(254,226,226,0.4)' }}
            >
              {loading === 'reject' ? (
                <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-red-600" />
              ) : (
                <XCircle size={13} />
              )}
              Reject
            </button>
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1.5 rounded transition-colors"
              style={{ color: '#9aa5bd' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = '#374a6d'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = '#9aa5bd'; }}
            >
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 pt-3" style={{ borderTop: '1px solid rgba(91,126,194,0.08)' }}>
          {type === 'company' ? (
            <div className="grid grid-cols-2 gap-3 text-sm">
              {[
                ['Domain', item.domain],
                ['Size', item.employee_range],
                ['Brand Value', item.brand_value_score?.toFixed(2)],
                ['Handle Pain', item.handle_pain_score?.toFixed(2)],
                ['Urgency', item.urgency_score?.toFixed(2)],
                ['Reachability', item.reachability_score?.toFixed(2)],
              ].map(([label, val]) => (
                <div key={label}>
                  <p className="text-xs" style={{ color: '#6b7a99' }}>{label}</p>
                  <p style={{ color: '#1b2a4a' }}>{val || '—'}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-xs" style={{ color: '#6b7a99' }}>Subject</p>
                <p style={{ color: '#1b2a4a' }}>{item.subject || '—'}</p>
              </div>
              <div>
                <p className="text-xs" style={{ color: '#6b7a99' }}>Preview</p>
                <p className="whitespace-pre-line text-xs leading-relaxed rounded p-3" style={{
                  color: '#374a6d',
                  background: 'rgba(238,241,248,0.6)',
                  border: '1px solid rgba(91,126,194,0.06)',
                }}>
                  {item.body_preview || item.body || 'No preview available'}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ApprovalsPage() {
  const [queue, setQueue] = useState({ companies: [], outreach: [] });
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('companies');

  const load = async () => {
    setLoading(true);
    try {
      const data = await getApprovalQueue();
      setQueue({
        companies: data.companies || [],
        outreach: data.outreach || [],
      });
    } catch (e) {
      console.error('Approval queue load error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCompanyAction = async (id, action) => {
    if (action === 'approve') await approveCompany(id);
    else await rejectCompany(id);
    setQueue(q => ({ ...q, companies: q.companies.filter(c => c.id !== id) }));
  };

  const handleOutreachAction = async (id, action) => {
    if (action === 'approve') await approveOutreach(id);
    else await rejectOutreach(id);
    setQueue(q => ({ ...q, outreach: q.outreach.filter(o => o.id !== id) }));
  };

  const items = tab === 'companies' ? queue.companies : queue.outreach;
  const totalPending = queue.companies.length + queue.outreach.length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Approvals</h2>
        <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>
          {totalPending > 0 ? `${totalPending} items need your review` : 'All caught up — no pending approvals'}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg p-1 w-fit" style={{ background: 'rgba(238,241,248,0.8)', border: '1px solid rgba(91,126,194,0.08)' }}>
        {[
          { id: 'companies', label: 'Companies', count: queue.companies.length },
          { id: 'outreach', label: 'Outreach', count: queue.outreach.length },
        ].map(({ id, label, count }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className="px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200"
            style={tab === id
              ? { background: 'rgba(255,255,255,0.95)', color: '#1b2a4a', boxShadow: '0 2px 8px rgba(15,26,46,0.06)' }
              : { color: '#6b7a99' }
            }
          >
            {label}
            {count > 0 && (
              <span
                className="ml-1.5 inline-flex items-center justify-center w-5 h-5 rounded-full text-xs"
                style={tab === id
                  ? { background: 'rgba(58,82,137,0.1)', color: '#3a5289' }
                  : { background: 'rgba(154,165,189,0.2)', color: '#6b7a99' }
                }
              >
                {count}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
        </div>
      ) : items.length === 0 ? (
        <div className="glass-card rounded-xl p-12 text-center">
          <CheckCircle2 size={40} className="mx-auto mb-3" style={{ color: '#34d399' }} />
          <p className="font-medium" style={{ color: '#374a6d' }}>No pending {tab} approvals</p>
          <p className="text-sm mt-1" style={{ color: '#9aa5bd' }}>New items will appear here when the pipeline runs</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <ApprovalCard
              key={item.id}
              item={item}
              type={tab === 'companies' ? 'company' : 'outreach'}
              onAction={tab === 'companies' ? handleCompanyAction : handleOutreachAction}
            />
          ))}
        </div>
      )}
    </div>
  );
}
