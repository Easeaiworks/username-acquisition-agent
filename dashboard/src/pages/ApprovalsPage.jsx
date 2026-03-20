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
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h4 className="font-medium text-gray-900 truncate">
                {item.brand_name || item.company_name || 'Unknown'}
              </h4>
              {item.priority_bucket && <PriorityBadge priority={item.priority_bucket} />}
            </div>
            <p className="text-sm text-gray-500 mt-0.5">
              {type === 'company'
                ? `Score: ${item.composite_score?.toFixed(2) || '—'} · ${item.industry || 'Unknown industry'}`
                : `To: ${item.contact_name || '—'} · Step ${item.sequence_step || 1}/4`}
            </p>
          </div>

          <div className="flex items-center gap-1.5 ml-3">
            <button
              onClick={() => handleAction('approve')}
              disabled={loading !== null}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
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
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
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
              className="p-1.5 text-gray-400 hover:text-gray-600 rounded"
            >
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3">
          {type === 'company' ? (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-gray-500 text-xs">Domain</p>
                <p className="text-gray-900">{item.domain || '—'}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Size</p>
                <p className="text-gray-900">{item.employee_range || '—'}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Brand Value</p>
                <p className="text-gray-900">{item.brand_value_score?.toFixed(2) || '—'}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Handle Pain</p>
                <p className="text-gray-900">{item.handle_pain_score?.toFixed(2) || '—'}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Urgency</p>
                <p className="text-gray-900">{item.urgency_score?.toFixed(2) || '—'}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Reachability</p>
                <p className="text-gray-900">{item.reachability_score?.toFixed(2) || '—'}</p>
              </div>
            </div>
          ) : (
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-gray-500 text-xs">Subject</p>
                <p className="text-gray-900">{item.subject || '—'}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Preview</p>
                <p className="text-gray-700 whitespace-pre-line text-xs leading-relaxed bg-gray-50 rounded p-3">
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
        <h2 className="text-xl font-bold text-gray-900">Approvals</h2>
        <p className="text-sm text-gray-500 mt-1">
          {totalPending > 0 ? `${totalPending} items need your review` : 'All caught up — no pending approvals'}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {[
          { id: 'companies', label: 'Companies', count: queue.companies.length },
          { id: 'outreach', label: 'Outreach', count: queue.outreach.length },
        ].map(({ id, label, count }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {label}
            {count > 0 && (
              <span className={`ml-1.5 inline-flex items-center justify-center w-5 h-5 rounded-full text-xs ${
                tab === id ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-600'
              }`}>
                {count}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <CheckCircle2 size={40} className="mx-auto text-green-400 mb-3" />
          <p className="text-gray-600 font-medium">No pending {tab} approvals</p>
          <p className="text-sm text-gray-400 mt-1">New items will appear here when the pipeline runs</p>
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
