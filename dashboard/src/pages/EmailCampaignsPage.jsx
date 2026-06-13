import { useState, useEffect, useCallback } from 'react';
import { Send, Plus, ArrowLeft, Eye, Clock, Play, Pause, Copy, Trash2, X, CheckCircle, XCircle, Loader2, BarChart3, Mail, MousePointer, UserMinus, AlertTriangle } from 'lucide-react';
import {
  getEmailCampaigns, getEmailCampaign, createEmailCampaign, updateEmailCampaign,
  deleteEmailCampaign, sendCampaign, pauseCampaign, duplicateCampaign, getCampaignStats,
  getEmailLists,
} from '../lib/api';

function Toast({ message, type, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [onClose]);
  return (
    <div className="fixed top-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg text-sm font-medium"
      style={{
        background: type === 'success' ? 'linear-gradient(135deg, #d1fae5, #a7f3d0)' : 'linear-gradient(135deg, #fee2e2, #fecaca)',
        color: type === 'success' ? '#065f46' : '#991b1b',
        border: type === 'success' ? '1px solid rgba(6, 95, 70, 0.15)' : '1px solid rgba(153, 27, 27, 0.15)',
      }}>
      {type === 'success' ? <CheckCircle size={16} /> : <XCircle size={16} />}
      {message}
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100"><X size={14} /></button>
    </div>
  );
}

const STATUS_STYLES = {
  draft: { bg: '#e5e7eb', color: '#374151' },
  scheduled: { bg: '#dbeafe', color: '#1e40af' },
  sending: { bg: '#fef3c7', color: '#92400e' },
  sent: { bg: '#d1fae5', color: '#065f46' },
  paused: { bg: '#fee2e2', color: '#991b1b' },
};

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.draft;
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize"
      style={{ background: s.bg, color: s.color }}>
      {status}
    </span>
  );
}

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="rounded-xl p-4"
      style={{
        background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
        border: '1px solid rgba(255, 255, 255, 0.6)',
        boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
      }}>
      <div className="flex items-center gap-2 mb-1">
        {Icon && <Icon size={14} style={{ color: color || '#6b7a99' }} />}
        <p className="text-xs font-medium" style={{ color: '#6b7a99' }}>{label}</p>
      </div>
      <p className="text-2xl font-bold" style={{ color: color || '#1b2a4a' }}>{value}</p>
    </div>
  );
}

function CampaignEditor({ campaign, onSave, onCancel, lists }) {
  const [form, setForm] = useState({
    name: '', subject: '', preview_text: '',
    from_name: '', from_email: '', reply_to: '',
    list_id: '', html_content: '',
    ...campaign,
  });
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [error, setError] = useState(null);

  function update(field, value) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  async function handleSave(action = 'draft') {
    setSaving(true);
    setError(null);
    try {
      await onSave(form, action);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button onClick={onCancel} className="flex items-center gap-2 text-sm font-medium" style={{ color: '#2b5797' }}>
          <ArrowLeft size={16} /> Back to Campaigns
        </button>
        <div className="flex items-center gap-2">
          <button onClick={() => handleSave('draft')} disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:shadow-md"
            style={{ border: '1px solid rgba(91, 126, 194, 0.2)', color: '#2b5797' }}>
            Save as Draft
          </button>
          <button onClick={() => handleSave('send')} disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-md disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #059669, #10b981)' }}>
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Send Now
          </button>
        </div>
      </div>

      {error && <p className="text-xs text-red-600 bg-red-50 px-4 py-2 rounded-lg">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left column */}
        <div className="space-y-4">
          <div className="rounded-xl p-5" style={{
            background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
            border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
          }}>
            <h3 className="text-sm font-bold mb-4" style={{ color: '#1b2a4a' }}>Campaign Details</h3>
            {[
              { field: 'name', label: 'Campaign Name', placeholder: 'Summer Sale 2024' },
              { field: 'subject', label: 'Subject Line', placeholder: 'Check out our summer deals' },
              { field: 'preview_text', label: 'Preview Text', placeholder: 'You won\'t want to miss these...' },
            ].map(({ field, label, placeholder }) => (
              <div key={field} className="mb-3">
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>{label}</label>
                <input value={form[field] || ''} onChange={e => update(field, e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                  placeholder={placeholder} />
              </div>
            ))}
          </div>

          <div className="rounded-xl p-5" style={{
            background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
            border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
          }}>
            <h3 className="text-sm font-bold mb-4" style={{ color: '#1b2a4a' }}>Sender Info</h3>
            {[
              { field: 'from_name', label: 'From Name', placeholder: 'Your Company' },
              { field: 'from_email', label: 'From Email', placeholder: 'hello@company.com' },
              { field: 'reply_to', label: 'Reply-to', placeholder: 'reply@company.com' },
            ].map(({ field, label, placeholder }) => (
              <div key={field} className="mb-3">
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>{label}</label>
                <input value={form[field] || ''} onChange={e => update(field, e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                  placeholder={placeholder} />
              </div>
            ))}
            <div className="mb-3">
              <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Email List</label>
              <select value={form.list_id || ''} onChange={e => update('list_id', e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}>
                <option value="">Select a list...</option>
                {(lists || []).map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
          </div>
        </div>

        {/* Right column — Content */}
        <div className="rounded-xl p-5" style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
        }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold" style={{ color: '#1b2a4a' }}>HTML Content</h3>
            <button onClick={() => setShowPreview(!showPreview)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
              style={{ background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af' }}>
              <Eye size={14} /> {showPreview ? 'Editor' : 'Preview'}
            </button>
          </div>
          {showPreview ? (
            <div className="rounded-lg p-4 min-h-[400px] overflow-auto"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: '#fff' }}
              dangerouslySetInnerHTML={{ __html: form.html_content || '<p style="color:#999;">No content yet</p>' }}
            />
          ) : (
            <textarea value={form.html_content || ''} onChange={e => update('html_content', e.target.value)}
              rows={20}
              className="w-full px-4 py-3 rounded-lg text-sm outline-none font-mono"
              style={{
                border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)',
                color: '#1b2a4a', resize: 'vertical', minHeight: '400px',
              }}
              placeholder="<html>&#10;  <body>&#10;    <h1>Your email content</h1>&#10;  </body>&#10;</html>"
            />
          )}
        </div>
      </div>
    </div>
  );
}

function CampaignDetail({ campaign, stats, onBack }) {
  const openRate = stats?.delivered > 0 ? ((stats.unique_opens || stats.opens || 0) / stats.delivered * 100).toFixed(1) : '0.0';
  const clickRate = stats?.delivered > 0 ? ((stats.unique_clicks || stats.clicks || 0) / stats.delivered * 100).toFixed(1) : '0.0';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 text-sm font-medium" style={{ color: '#2b5797' }}>
          <ArrowLeft size={16} /> Back to Campaigns
        </button>
        <StatusBadge status={campaign.status} />
      </div>

      <div>
        <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>{campaign.name}</h2>
        <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Subject: {campaign.subject}</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
        <StatCard label="Delivered" value={stats?.delivered ?? 0} icon={Send} color="#1e3a5f" />
        <StatCard label="Opens" value={stats?.opens ?? 0} icon={Mail} color="#2b5797" />
        <StatCard label="Open Rate" value={`${openRate}%`} icon={Eye} color="#059669" />
        <StatCard label="Clicks" value={stats?.clicks ?? 0} icon={MousePointer} color="#7c3aed" />
        <StatCard label="Click Rate" value={`${clickRate}%`} icon={BarChart3} color="#0891b2" />
        <StatCard label="Bounces" value={stats?.bounces ?? 0} icon={AlertTriangle} color="#dc2626" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Unique Opens" value={stats?.unique_opens ?? 0} icon={Mail} />
        <StatCard label="Unique Clicks" value={stats?.unique_clicks ?? 0} icon={MousePointer} />
        <StatCard label="Unsubscribes" value={stats?.unsubscribes ?? 0} icon={UserMinus} color="#991b1b" />
      </div>
    </div>
  );
}

export default function EmailCampaignsPage() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [view, setView] = useState('list'); // list | editor | detail
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [campaignStats, setCampaignStats] = useState(null);
  const [lists, setLists] = useState([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [cData, lData] = await Promise.all([
        getEmailCampaigns(),
        getEmailLists().catch(() => ({ lists: [] })),
      ]);
      setCampaigns(cData.campaigns || []);
      setLists(lData.lists || lData || []);
    } catch (e) {
      setToast({ message: 'Failed to load campaigns', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleViewCampaign(c) {
    setSelectedCampaign(c);
    if (c.status === 'sent' || c.status === 'sending') {
      try {
        const stats = await getCampaignStats(c.id);
        setCampaignStats(stats);
      } catch { setCampaignStats({}); }
      setView('detail');
    } else {
      setView('editor');
    }
  }

  async function handleSaveCampaign(form, action) {
    if (selectedCampaign?.id) {
      await updateEmailCampaign(selectedCampaign.id, form);
      if (action === 'send') await sendCampaign(selectedCampaign.id);
      setToast({ message: action === 'send' ? 'Campaign sent' : 'Campaign saved', type: 'success' });
    } else {
      const created = await createEmailCampaign(form);
      if (action === 'send' && created?.id) await sendCampaign(created.id);
      setToast({ message: action === 'send' ? 'Campaign created and sent' : 'Campaign created', type: 'success' });
    }
    setView('list');
    setSelectedCampaign(null);
    loadData();
  }

  async function handleDuplicate(id) {
    try {
      await duplicateCampaign(id);
      setToast({ message: 'Campaign duplicated', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to duplicate', type: 'error' });
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Delete this campaign?')) return;
    try {
      await deleteEmailCampaign(id);
      setToast({ message: 'Campaign deleted', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to delete', type: 'error' });
    }
  }

  if (loading && campaigns.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  if (view === 'editor') {
    return (
      <div>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
        <CampaignEditor
          campaign={selectedCampaign || {}}
          lists={lists}
          onSave={handleSaveCampaign}
          onCancel={() => { setView('list'); setSelectedCampaign(null); }}
        />
      </div>
    );
  }

  if (view === 'detail' && selectedCampaign) {
    return (
      <div>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
        <CampaignDetail
          campaign={selectedCampaign}
          stats={campaignStats}
          onBack={() => { setView('list'); setSelectedCampaign(null); }}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Campaigns</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Create and manage email campaigns</p>
        </div>
        <button onClick={() => { setSelectedCampaign(null); setView('editor'); }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-md"
          style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
          <Plus size={16} /> Create Campaign
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {campaigns.map(c => (
          <div key={c.id} className="rounded-xl p-5 transition-all duration-200 hover:shadow-lg cursor-pointer"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)',
              boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
            }}
            onClick={() => handleViewCampaign(c)}>
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold truncate" style={{ color: '#1b2a4a' }}>{c.name}</h3>
                <p className="text-xs mt-0.5 truncate" style={{ color: '#6b7a99' }}>{c.subject}</p>
              </div>
              <StatusBadge status={c.status || 'draft'} />
            </div>
            <div className="flex items-center gap-4 text-xs mb-3" style={{ color: '#9aa5bd' }}>
              {c.list_name && <span>List: {c.list_name}</span>}
              {c.created_at && <span>{new Date(c.created_at).toLocaleDateString()}</span>}
            </div>
            {(c.status === 'sent' || c.status === 'sending') && (
              <div className="flex items-center gap-4 text-xs font-medium" style={{ color: '#374a6d' }}>
                <span>Sent: {c.sent_count ?? 0}</span>
                <span>Opens: {c.open_count ?? 0}</span>
                <span>Clicks: {c.click_count ?? 0}</span>
              </div>
            )}
            <div className="flex items-center gap-1 mt-3 pt-3" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.1)' }}>
              <button onClick={e => { e.stopPropagation(); handleDuplicate(c.id); }}
                className="p-1.5 rounded-lg hover:bg-blue-50 transition-colors" title="Duplicate">
                <Copy size={14} style={{ color: '#2b5797' }} />
              </button>
              <button onClick={e => { e.stopPropagation(); handleDelete(c.id); }}
                className="p-1.5 rounded-lg hover:bg-red-50 transition-colors" title="Delete">
                <Trash2 size={14} style={{ color: '#991b1b' }} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {campaigns.length === 0 && (
        <div className="text-center py-16">
          <Send size={40} className="mx-auto mb-3" style={{ color: '#d1d5db' }} />
          <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>No campaigns yet</p>
          <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>Create your first campaign to get started</p>
        </div>
      )}
    </div>
  );
}
