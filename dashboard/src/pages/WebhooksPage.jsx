import { useState, useEffect, useCallback } from 'react';
import { Globe, Plus, Edit2, Trash2, Zap, ArrowLeft, X, CheckCircle, XCircle, Loader2, ToggleLeft, ToggleRight, AlertTriangle, Clock, Eye } from 'lucide-react';
import {
  getWebhooks, createWebhook, updateWebhook, deleteWebhook,
  toggleWebhook, testWebhook, getWebhookDeliveries, getWebhookEvents,
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

const DEFAULT_EVENTS = [
  'lead_scored', 'company_approved', 'company_rejected', 'outreach_sent',
  'stage_changed', 'contact_created', 'contact_updated', 'email_opened',
  'email_clicked', 'email_bounced', 'campaign_sent', 'sequence_completed',
];

function WebhookModal({ webhook, onClose, onSave, availableEvents }) {
  const [form, setForm] = useState({
    name: '', url: '', secret: '', events: [], is_active: true,
    ...webhook,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const events = availableEvents.length > 0 ? availableEvents : DEFAULT_EVENTS;

  function update(field, value) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  function toggleEvent(event) {
    const current = form.events || [];
    if (current.includes(event)) {
      update('events', current.filter(e => e !== event));
    } else {
      update('events', [...current, event]);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save webhook');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(15, 26, 46, 0.5)', backdropFilter: 'blur(4px)' }}>
      <div className="w-full max-w-lg rounded-2xl p-6 max-h-[90vh] overflow-y-auto"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.98) 0%, rgba(243,245,252,0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 24px 64px rgba(15, 26, 46, 0.2)',
        }}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>{webhook?.id ? 'Edit Webhook' : 'Add Webhook'}</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100"><X size={20} style={{ color: '#6b7a99' }} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Name</label>
            <input value={form.name || ''} onChange={e => update('name', e.target.value)} required
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              placeholder="CRM Sync" />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>URL</label>
            <input value={form.url || ''} onChange={e => update('url', e.target.value)} required
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none font-mono"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              placeholder="https://api.example.com/webhook" />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Secret (optional)</label>
            <input value={form.secret || ''} onChange={e => update('secret', e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none font-mono"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              placeholder="whsec_..." />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: '#6b7a99' }}>Events</label>
            <div className="grid grid-cols-2 gap-2">
              {events.map(event => (
                <label key={event} className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all"
                  style={{
                    background: (form.events || []).includes(event) ? 'rgba(43, 87, 151, 0.08)' : 'rgba(238, 241, 248, 0.5)',
                    border: (form.events || []).includes(event) ? '1px solid rgba(43, 87, 151, 0.3)' : '1px solid rgba(91, 126, 194, 0.1)',
                  }}>
                  <input type="checkbox" checked={(form.events || []).includes(event)}
                    onChange={() => toggleEvent(event)} className="rounded" />
                  <span className="text-xs font-medium" style={{ color: '#374a6d' }}>
                    {event.replace(/_/g, ' ')}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {error && <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm font-medium" style={{ color: '#6b7a99' }}>Cancel</button>
            <button type="submit" disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
              {webhook?.id ? 'Update' : 'Add Webhook'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DeliveryLog({ webhook, onBack }) {
  const [deliveries, setDeliveries] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getWebhookDeliveries(webhook.id);
        setDeliveries(data.deliveries || data || []);
      } catch { setDeliveries([]); }
      finally { setLoading(false); }
    }
    load();
  }, [webhook.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 text-sm font-medium" style={{ color: '#2b5797' }}>
          <ArrowLeft size={16} /> Back to Webhooks
        </button>
        <div>
          <h3 className="text-sm font-bold" style={{ color: '#1b2a4a' }}>{webhook.name}</h3>
          <p className="text-xs font-mono" style={{ color: '#6b7a99' }}>{webhook.url}</p>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
        }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(91, 126, 194, 0.1)' }}>
              {['Event', 'Timestamp', 'HTTP Status', 'Result'].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {deliveries.map((d, i) => (
              <tr key={i} style={{ borderBottom: '1px solid rgba(91, 126, 194, 0.06)' }}>
                <td className="px-4 py-3">
                  <span className="text-xs font-medium px-2 py-0.5 rounded" style={{ background: 'rgba(43, 87, 151, 0.1)', color: '#2b5797' }}>
                    {d.event_type?.replace(/_/g, ' ') || '-'}
                  </span>
                </td>
                <td className="px-4 py-3" style={{ color: '#6b7a99' }}>
                  {d.created_at ? new Date(d.created_at).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-3">
                  <span className="font-mono text-xs font-semibold"
                    style={{ color: d.http_status >= 200 && d.http_status < 300 ? '#059669' : '#dc2626' }}>
                    {d.http_status || '-'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold"
                    style={{
                      background: d.success ? '#d1fae5' : '#fee2e2',
                      color: d.success ? '#065f46' : '#991b1b',
                    }}>
                    {d.success ? 'Success' : 'Failed'}
                  </span>
                </td>
              </tr>
            ))}
            {deliveries.length === 0 && (
              <tr>
                <td colSpan={4} className="text-center py-12">
                  <Clock size={32} className="mx-auto mb-2" style={{ color: '#d1d5db' }} />
                  <p className="text-sm" style={{ color: '#6b7a99' }}>No deliveries yet</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function WebhooksPage() {
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState(null);
  const [viewingDeliveries, setViewingDeliveries] = useState(null);
  const [availableEvents, setAvailableEvents] = useState([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [whData, evData] = await Promise.all([
        getWebhooks(),
        getWebhookEvents().catch(() => ({ events: [] })),
      ]);
      setWebhooks(whData.data || whData.webhooks || []);
      setAvailableEvents(evData.data || evData.events || []);
    } catch (e) {
      setToast({ message: 'Failed to load webhooks', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleSave(form) {
    if (form.id) {
      await updateWebhook(form.id, form);
      setToast({ message: 'Webhook updated', type: 'success' });
    } else {
      await createWebhook(form);
      setToast({ message: 'Webhook created', type: 'success' });
    }
    loadData();
  }

  async function handleToggle(id) {
    try {
      await toggleWebhook(id);
      setToast({ message: 'Webhook toggled', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to toggle', type: 'error' });
    }
  }

  async function handleTest(id) {
    try {
      await testWebhook(id);
      setToast({ message: 'Test delivery sent', type: 'success' });
    } catch (e) {
      setToast({ message: e.message || 'Test failed', type: 'error' });
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Delete this webhook?')) return;
    try {
      await deleteWebhook(id);
      setToast({ message: 'Webhook deleted', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to delete', type: 'error' });
    }
  }

  if (loading && webhooks.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  if (viewingDeliveries) {
    return (
      <div>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
        <DeliveryLog webhook={viewingDeliveries} onBack={() => setViewingDeliveries(null)} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Webhooks</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Send real-time notifications to external services</p>
        </div>
        <button onClick={() => { setEditingWebhook(null); setShowModal(true); }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-md"
          style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
          <Plus size={16} /> Add Webhook
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {webhooks.map(wh => (
          <div key={wh.id} className="rounded-xl p-5 transition-all duration-200 hover:shadow-lg"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)',
              boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
              borderLeft: wh.is_active ? '3px solid #22c55e' : '3px solid transparent',
            }}>
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(43, 87, 151, 0.1)' }}>
                  <Globe size={20} style={{ color: '#2b5797' }} />
                </div>
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold" style={{ color: '#1b2a4a' }}>{wh.name}</h3>
                  <p className="text-xs font-mono truncate max-w-[200px]" style={{ color: '#6b7a99' }}>{wh.url}</p>
                </div>
              </div>
              <span className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0"
                style={{
                  background: wh.is_active ? '#d1fae5' : '#e5e7eb',
                  color: wh.is_active ? '#065f46' : '#374151',
                }}>
                {wh.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>

            <div className="flex flex-wrap gap-1 mb-3">
              {(wh.events || []).slice(0, 4).map(e => (
                <span key={e} className="inline-flex px-2 py-0.5 rounded text-xs font-medium"
                  style={{ background: 'rgba(43, 87, 151, 0.08)', color: '#2b5797' }}>
                  {e.replace(/_/g, ' ')}
                </span>
              ))}
              {(wh.events || []).length > 4 && (
                <span className="text-xs" style={{ color: '#9aa5bd' }}>+{wh.events.length - 4}</span>
              )}
            </div>

            <div className="flex items-center gap-4 text-xs mb-3" style={{ color: '#9aa5bd' }}>
              {wh.failure_count > 0 && (
                <span className="flex items-center gap-1" style={{ color: '#dc2626' }}>
                  <AlertTriangle size={12} /> {wh.failure_count} failures
                </span>
              )}
              {wh.last_triggered_at && (
                <span className="flex items-center gap-1">
                  <Clock size={12} /> {new Date(wh.last_triggered_at).toLocaleDateString()}
                </span>
              )}
            </div>

            <div className="flex items-center gap-1 pt-3" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.1)' }}>
              <button onClick={() => { setEditingWebhook(wh); setShowModal(true); }}
                className="p-1.5 rounded-lg hover:bg-blue-50 transition-colors" title="Edit">
                <Edit2 size={14} style={{ color: '#2b5797' }} />
              </button>
              <button onClick={() => handleTest(wh.id)}
                className="p-1.5 rounded-lg hover:bg-green-50 transition-colors" title="Test">
                <Zap size={14} style={{ color: '#059669' }} />
              </button>
              <button onClick={() => setViewingDeliveries(wh)}
                className="p-1.5 rounded-lg hover:bg-blue-50 transition-colors" title="View Deliveries">
                <Eye size={14} style={{ color: '#2b5797' }} />
              </button>
              <button onClick={() => handleToggle(wh.id)}
                className="p-1.5 rounded-lg hover:bg-yellow-50 transition-colors" title="Toggle">
                {wh.is_active ? <ToggleRight size={14} style={{ color: '#059669' }} /> : <ToggleLeft size={14} style={{ color: '#9ca3af' }} />}
              </button>
              <button onClick={() => handleDelete(wh.id)}
                className="p-1.5 rounded-lg hover:bg-red-50 transition-colors ml-auto" title="Delete">
                <Trash2 size={14} style={{ color: '#991b1b' }} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {webhooks.length === 0 && (
        <div className="text-center py-16">
          <Globe size={40} className="mx-auto mb-3" style={{ color: '#d1d5db' }} />
          <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>No webhooks configured</p>
          <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>Add a webhook to send event notifications to external services</p>
        </div>
      )}

      {showModal && (
        <WebhookModal
          webhook={editingWebhook}
          availableEvents={availableEvents}
          onClose={() => { setShowModal(false); setEditingWebhook(null); }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
