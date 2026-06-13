import { useState, useEffect, useCallback } from 'react';
import { Server, Plus, Edit2, Trash2, Zap, Star, X, CheckCircle, XCircle, Loader2, Shield, Eye, EyeOff } from 'lucide-react';
import {
  getEmailSenders, createEmailSender, updateEmailSender,
  deleteEmailSender, verifyEmailSender, setDefaultSender,
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

const TYPE_STYLES = {
  smtp: { bg: '#dbeafe', color: '#1e40af', label: 'SMTP' },
  sendgrid: { bg: '#d1fae5', color: '#065f46', label: 'SendGrid' },
  ses: { bg: '#fef3c7', color: '#92400e', label: 'SES' },
};

function TypeBadge({ type }) {
  const s = TYPE_STYLES[type] || TYPE_STYLES.smtp;
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold"
      style={{ background: s.bg, color: s.color }}>
      {s.label}
    </span>
  );
}

function SenderModal({ sender, onClose, onSave }) {
  const [form, setForm] = useState({
    name: '', sender_type: 'smtp', from_email: '', from_name: '', daily_limit: 500,
    // SMTP fields
    smtp_host: '', smtp_port: 587, smtp_username: '', smtp_password: '', smtp_tls: true,
    // SendGrid
    sendgrid_api_key: '',
    // SES
    ses_access_key_id: '', ses_secret_access_key: '', ses_region: 'us-east-1',
    ...sender,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [showSecrets, setShowSecrets] = useState({});

  function update(field, value) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  function toggleSecret(field) {
    setShowSecrets(prev => ({ ...prev, [field]: !prev[field] }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save sender');
    } finally {
      setSaving(false);
    }
  }

  function SecretInput({ field, label, placeholder }) {
    return (
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>{label}</label>
        <div className="relative">
          <input
            type={showSecrets[field] ? 'text' : 'password'}
            value={form[field] || ''}
            onChange={e => update(field, e.target.value)}
            className="w-full px-4 py-2.5 rounded-lg text-sm outline-none pr-10"
            style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
            placeholder={placeholder}
          />
          <button type="button" onClick={() => toggleSecret(field)}
            className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: '#6b7a99' }}>
            {showSecrets[field] ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
      </div>
    );
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
          <h3 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>{sender?.id ? 'Edit Sender' : 'Add Sender'}</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100"><X size={20} style={{ color: '#6b7a99' }} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Sender Name</label>
            <input value={form.name || ''} onChange={e => update('name', e.target.value)} required
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              placeholder="Primary Sender" />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: '#6b7a99' }}>Sender Type</label>
            <div className="flex gap-3">
              {['smtp', 'sendgrid', 'ses'].map(t => (
                <label key={t} className="flex items-center gap-2 px-4 py-2.5 rounded-lg cursor-pointer transition-all"
                  style={{
                    border: form.sender_type === t ? '2px solid #2b5797' : '1px solid rgba(91, 126, 194, 0.2)',
                    background: form.sender_type === t ? 'rgba(43, 87, 151, 0.05)' : 'rgba(238, 241, 248, 0.5)',
                  }}>
                  <input type="radio" name="sender_type" value={t} checked={form.sender_type === t}
                    onChange={() => update('sender_type', t)} className="sr-only" />
                  <span className="text-sm font-medium" style={{ color: form.sender_type === t ? '#1e3a5f' : '#6b7a99' }}>
                    {t.toUpperCase()}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* SMTP fields */}
          {form.sender_type === 'smtp' && (
            <>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Host</label>
                  <input value={form.smtp_host || ''} onChange={e => update('smtp_host', e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                    placeholder="smtp.gmail.com" />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Port</label>
                  <input type="number" value={form.smtp_port || 587} onChange={e => update('smtp_port', parseInt(e.target.value))}
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }} />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Username</label>
                <input value={form.smtp_username || ''} onChange={e => update('smtp_username', e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                  placeholder="user@gmail.com" />
              </div>
              <SecretInput field="smtp_password" label="Password" placeholder="App password" />
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.smtp_tls !== false}
                  onChange={e => update('smtp_tls', e.target.checked)}
                  className="rounded" />
                <span className="text-sm" style={{ color: '#374a6d' }}>Use TLS</span>
              </label>
            </>
          )}

          {/* SendGrid fields */}
          {form.sender_type === 'sendgrid' && (
            <SecretInput field="sendgrid_api_key" label="API Key" placeholder="SG.xxxxx" />
          )}

          {/* SES fields */}
          {form.sender_type === 'ses' && (
            <>
              <SecretInput field="ses_access_key_id" label="Access Key ID" placeholder="AKIA..." />
              <SecretInput field="ses_secret_access_key" label="Secret Access Key" placeholder="..." />
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Region</label>
                <input value={form.ses_region || 'us-east-1'} onChange={e => update('ses_region', e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                  placeholder="us-east-1" />
              </div>
            </>
          )}

          <div className="pt-2" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.1)' }}>
            <h4 className="text-xs font-bold uppercase tracking-wider mb-3" style={{ color: '#374a6d' }}>Sender Details</h4>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>From Email</label>
            <input value={form.from_email || ''} onChange={e => update('from_email', e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              placeholder="hello@company.com" />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>From Name</label>
            <input value={form.from_name || ''} onChange={e => update('from_name', e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              placeholder="Your Company" />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Daily Send Limit</label>
            <input type="number" value={form.daily_limit || 500} onChange={e => update('daily_limit', parseInt(e.target.value))}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }} />
          </div>

          {error && <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm font-medium" style={{ color: '#6b7a99' }}>Cancel</button>
            <button type="submit" disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
              {sender?.id ? 'Update Sender' : 'Add Sender'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function EmailSendersPage() {
  const [senders, setSenders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingSender, setEditingSender] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getEmailSenders();
      setSenders(data.senders || data || []);
    } catch (e) {
      setToast({ message: 'Failed to load senders', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleSave(form) {
    if (form.id) {
      await updateEmailSender(form.id, form);
      setToast({ message: 'Sender updated', type: 'success' });
    } else {
      await createEmailSender(form);
      setToast({ message: 'Sender created', type: 'success' });
    }
    loadData();
  }

  async function handleVerify(id) {
    try {
      await verifyEmailSender(id);
      setToast({ message: 'Verification initiated', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Verification failed', type: 'error' });
    }
  }

  async function handleSetDefault(id) {
    try {
      await setDefaultSender(id);
      setToast({ message: 'Default sender updated', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to set default', type: 'error' });
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Delete this sender configuration?')) return;
    try {
      await deleteEmailSender(id);
      setToast({ message: 'Sender deleted', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to delete', type: 'error' });
    }
  }

  if (loading && senders.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Email Senders</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Configure SMTP, SendGrid, and SES senders</p>
        </div>
        <button onClick={() => { setEditingSender(null); setShowModal(true); }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-md"
          style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
          <Plus size={16} /> Add Sender
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {senders.map(s => (
          <div key={s.id} className="rounded-xl p-5 transition-all duration-200 hover:shadow-lg"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)',
              boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
              borderLeft: s.is_default ? '3px solid #22c55e' : '3px solid transparent',
            }}>
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(43, 87, 151, 0.1)' }}>
                  <Server size={20} style={{ color: '#2b5797' }} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold" style={{ color: '#1b2a4a' }}>{s.name}</h3>
                    {s.is_default && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold"
                        style={{ background: '#d1fae5', color: '#065f46' }}>
                        <Star size={10} /> Default
                      </span>
                    )}
                  </div>
                  <p className="text-xs mt-0.5" style={{ color: '#6b7a99' }}>{s.from_email}</p>
                </div>
              </div>
              <TypeBadge type={s.sender_type} />
            </div>

            <div className="flex items-center gap-3 mb-3 text-xs" style={{ color: '#9aa5bd' }}>
              <div className="flex items-center gap-1">
                {s.is_verified ? (
                  <><Shield size={12} style={{ color: '#059669' }} /> <span style={{ color: '#059669' }}>Verified</span></>
                ) : (
                  <><Shield size={12} /> <span>Not verified</span></>
                )}
              </div>
              <span>{s.sent_today ?? 0} / {s.daily_limit ?? 500} today</span>
            </div>

            {/* Progress bar for daily usage */}
            <div className="w-full h-1.5 rounded-full mb-3" style={{ background: 'rgba(91, 126, 194, 0.1)' }}>
              <div className="h-full rounded-full transition-all"
                style={{
                  width: `${Math.min(100, ((s.sent_today || 0) / (s.daily_limit || 500)) * 100)}%`,
                  background: ((s.sent_today || 0) / (s.daily_limit || 500)) > 0.9 ? '#ef4444' : '#2b5797',
                }} />
            </div>

            <div className="flex items-center gap-1 pt-3" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.1)' }}>
              <button onClick={() => { setEditingSender(s); setShowModal(true); }}
                className="p-1.5 rounded-lg hover:bg-blue-50 transition-colors" title="Edit">
                <Edit2 size={14} style={{ color: '#2b5797' }} />
              </button>
              <button onClick={() => handleVerify(s.id)}
                className="p-1.5 rounded-lg hover:bg-green-50 transition-colors" title="Test / Verify">
                <Zap size={14} style={{ color: '#059669' }} />
              </button>
              {!s.is_default && (
                <button onClick={() => handleSetDefault(s.id)}
                  className="p-1.5 rounded-lg hover:bg-yellow-50 transition-colors" title="Set as Default">
                  <Star size={14} style={{ color: '#92400e' }} />
                </button>
              )}
              <button onClick={() => handleDelete(s.id)}
                className="p-1.5 rounded-lg hover:bg-red-50 transition-colors ml-auto" title="Delete">
                <Trash2 size={14} style={{ color: '#991b1b' }} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {senders.length === 0 && (
        <div className="text-center py-16">
          <Server size={40} className="mx-auto mb-3" style={{ color: '#d1d5db' }} />
          <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>No email senders configured</p>
          <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>Add an SMTP, SendGrid, or SES sender to start sending emails</p>
        </div>
      )}

      {showModal && (
        <SenderModal
          sender={editingSender}
          onClose={() => { setShowModal(false); setEditingSender(null); }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
