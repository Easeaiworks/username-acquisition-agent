import { useState, useEffect, useCallback } from 'react';
import { Users, Plus, Upload, Search, X, Edit2, UserMinus, Trash2, ChevronLeft, ChevronRight, CheckCircle, XCircle, Loader2, Tag } from 'lucide-react';
import {
  getEmailContacts, createEmailContact, updateEmailContact,
  deleteEmailContact, importEmailContacts, unsubscribeContact,
} from '../lib/api';

function Toast({ message, type, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div
      className="fixed top-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg text-sm font-medium"
      style={{
        background: type === 'success' ? 'linear-gradient(135deg, #d1fae5, #a7f3d0)' : 'linear-gradient(135deg, #fee2e2, #fecaca)',
        color: type === 'success' ? '#065f46' : '#991b1b',
        border: type === 'success' ? '1px solid rgba(6, 95, 70, 0.15)' : '1px solid rgba(153, 27, 27, 0.15)',
      }}
    >
      {type === 'success' ? <CheckCircle size={16} /> : <XCircle size={16} />}
      {message}
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100"><X size={14} /></button>
    </div>
  );
}

const STATUS_COLORS = {
  subscribed: { bg: '#d1fae5', color: '#065f46' },
  unsubscribed: { bg: '#fee2e2', color: '#991b1b' },
  bounced: { bg: '#fef3c7', color: '#92400e' },
  pending: { bg: '#dbeafe', color: '#1e40af' },
};

function StatusBadge({ status }) {
  const s = STATUS_COLORS[status] || STATUS_COLORS.pending;
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold"
      style={{ background: s.bg, color: s.color }}>
      {status}
    </span>
  );
}

function TagBadge({ tag }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
      style={{ background: 'rgba(43, 87, 151, 0.1)', color: '#2b5797' }}>
      {tag}
    </span>
  );
}

function AddContactModal({ onClose, onSave }) {
  const [form, setForm] = useState({ email: '', first_name: '', last_name: '', company: '', tags: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const data = { ...form, tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [] };
      await onSave(data);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to create contact');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(15, 26, 46, 0.5)', backdropFilter: 'blur(4px)' }}>
      <div className="w-full max-w-lg rounded-2xl p-6"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.98) 0%, rgba(243,245,252,0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 24px 64px rgba(15, 26, 46, 0.2)',
        }}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>Add Contact</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100"><X size={20} style={{ color: '#6b7a99' }} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {['email', 'first_name', 'last_name', 'company'].map(field => (
            <div key={field}>
              <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>
                {field.replace(/_/g, ' ')}
              </label>
              <input
                type={field === 'email' ? 'email' : 'text'}
                required={field === 'email'}
                value={form[field]}
                onChange={e => setForm(prev => ({ ...prev, [field]: e.target.value }))}
                className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                placeholder={field === 'email' ? 'name@example.com' : ''}
              />
            </div>
          ))}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Tags (comma separated)</label>
            <input
              value={form.tags}
              onChange={e => setForm(prev => ({ ...prev, tags: e.target.value }))}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              placeholder="lead, newsletter, vip"
            />
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm font-medium" style={{ color: '#6b7a99' }}>Cancel</button>
            <button type="submit" disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
              Add Contact
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ImportModal({ onClose, onImport }) {
  const [json, setJson] = useState('');
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [importing, setImporting] = useState(false);

  function handlePreview() {
    setError(null);
    try {
      const parsed = JSON.parse(json);
      if (!Array.isArray(parsed)) throw new Error('Input must be a JSON array');
      setPreview(parsed);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleImport() {
    setImporting(true);
    setError(null);
    try {
      await onImport(preview);
      onClose();
    } catch (err) {
      setError(err.message || 'Import failed');
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(15, 26, 46, 0.5)', backdropFilter: 'blur(4px)' }}>
      <div className="w-full max-w-2xl rounded-2xl p-6"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.98) 0%, rgba(243,245,252,0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 24px 64px rgba(15, 26, 46, 0.2)',
        }}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>Import Contacts</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100"><X size={20} style={{ color: '#6b7a99' }} /></button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>
              Paste JSON Array
            </label>
            <textarea
              value={json}
              onChange={e => { setJson(e.target.value); setPreview(null); }}
              rows={8}
              className="w-full px-4 py-3 rounded-lg text-sm outline-none font-mono"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a', resize: 'vertical' }}
              placeholder='[{"email":"a@b.com","first_name":"Alice"},{"email":"c@d.com"}]'
            />
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          {preview && (
            <div className="rounded-lg p-4" style={{ background: 'rgba(238, 241, 248, 0.7)', border: '1px solid rgba(91, 126, 194, 0.1)' }}>
              <p className="text-sm font-semibold mb-2" style={{ color: '#1b2a4a' }}>Preview: {preview.length} contacts</p>
              <div className="max-h-40 overflow-auto text-xs font-mono" style={{ color: '#6b7a99' }}>
                {preview.slice(0, 10).map((c, i) => (
                  <div key={i}>{c.email} {c.first_name ? `- ${c.first_name} ${c.last_name || ''}` : ''}</div>
                ))}
                {preview.length > 10 && <div>... and {preview.length - 10} more</div>}
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm font-medium" style={{ color: '#6b7a99' }}>Cancel</button>
            {!preview ? (
              <button onClick={handlePreview} className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
                style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
                Preview
              </button>
            ) : (
              <button onClick={handleImport} disabled={importing}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg, #059669, #10b981)' }}>
                {importing ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                Import {preview.length} Contacts
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function EmailContactsPage() {
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState({ subscribed: 0, unsubscribed: 0, bounced: 0 });
  const [showAdd, setShowAdd] = useState(false);
  const [showImport, setShowImport] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, per_page: 25 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (tagFilter) params.tag = tagFilter;
      const data = await getEmailContacts(params);
      setContacts(data.contacts || []);
      setTotal(data.total || 0);
      setTotalPages(data.total_pages || 1);
      if (data.stats) setStats(data.stats);
    } catch (e) {
      setToast({ message: 'Failed to load contacts', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, tagFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleCreate(data) {
    await createEmailContact(data);
    setToast({ message: 'Contact created', type: 'success' });
    loadData();
  }

  async function handleImport(contactsArray) {
    const result = await importEmailContacts(contactsArray);
    setToast({ message: `Imported ${result.imported || contactsArray.length} contacts`, type: 'success' });
    loadData();
  }

  async function handleUnsubscribe(id) {
    if (!window.confirm('Unsubscribe this contact?')) return;
    try {
      await unsubscribeContact(id);
      setToast({ message: 'Contact unsubscribed', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to unsubscribe', type: 'error' });
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Delete this contact permanently?')) return;
    try {
      await deleteEmailContact(id);
      setToast({ message: 'Contact deleted', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to delete', type: 'error' });
    }
  }

  const bounceRate = total > 0 ? ((stats.bounced || 0) / total * 100).toFixed(1) : '0.0';

  if (loading && contacts.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Contacts</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Manage your email contacts and subscribers</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setShowImport(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:shadow-md"
            style={{ background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af' }}>
            <Upload size={16} /> Import
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-md"
            style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
            <Plus size={16} /> Add Contact
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Contacts', value: total, color: '#1e3a5f' },
          { label: 'Subscribed', value: stats.subscribed || 0, color: '#059669' },
          { label: 'Unsubscribed', value: stats.unsubscribed || 0, color: '#991b1b' },
          { label: 'Bounce Rate', value: `${bounceRate}%`, color: '#92400e' },
        ].map(stat => (
          <div key={stat.label} className="rounded-xl p-4"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)',
              boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
            }}>
            <p className="text-xs font-medium" style={{ color: '#6b7a99' }}>{stat.label}</p>
            <p className="text-2xl font-bold mt-1" style={{ color: stat.color }}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Search / Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: '#9aa5bd' }} />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search by email or name..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm outline-none"
            style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(255,255,255,0.8)', color: '#1b2a4a' }}
          />
        </div>
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
          className="px-3 py-2.5 rounded-lg text-sm outline-none"
          style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(255,255,255,0.8)', color: '#1b2a4a' }}>
          <option value="">All Statuses</option>
          <option value="subscribed">Subscribed</option>
          <option value="unsubscribed">Unsubscribed</option>
          <option value="bounced">Bounced</option>
        </select>
        <div className="relative min-w-[160px]">
          <Tag size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: '#9aa5bd' }} />
          <input
            value={tagFilter}
            onChange={e => { setTagFilter(e.target.value); setPage(1); }}
            placeholder="Filter by tag..."
            className="w-full pl-9 pr-4 py-2.5 rounded-lg text-sm outline-none"
            style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(255,255,255,0.8)', color: '#1b2a4a' }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl overflow-hidden"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
        }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(91, 126, 194, 0.1)' }}>
                {['Email', 'Name', 'Company', 'Status', 'Tags', 'Opens', 'Clicks', 'Last Emailed', 'Actions'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {contacts.map(c => (
                <tr key={c.id} className="hover:bg-blue-50/30 transition-colors" style={{ borderBottom: '1px solid rgba(91, 126, 194, 0.06)' }}>
                  <td className="px-4 py-3 font-medium" style={{ color: '#1b2a4a' }}>{c.email}</td>
                  <td className="px-4 py-3" style={{ color: '#374a6d' }}>{[c.first_name, c.last_name].filter(Boolean).join(' ') || '-'}</td>
                  <td className="px-4 py-3" style={{ color: '#6b7a99' }}>{c.company || '-'}</td>
                  <td className="px-4 py-3"><StatusBadge status={c.status || 'subscribed'} /></td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {(c.tags || []).slice(0, 3).map(t => <TagBadge key={t} tag={t} />)}
                      {(c.tags || []).length > 3 && <span className="text-xs" style={{ color: '#9aa5bd' }}>+{c.tags.length - 3}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center" style={{ color: '#374a6d' }}>{c.opens ?? 0}</td>
                  <td className="px-4 py-3 text-center" style={{ color: '#374a6d' }}>{c.clicks ?? 0}</td>
                  <td className="px-4 py-3" style={{ color: '#6b7a99' }}>
                    {c.last_emailed ? new Date(c.last_emailed).toLocaleDateString() : '-'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button title="Edit" className="p-1.5 rounded-lg hover:bg-blue-50 transition-colors"><Edit2 size={14} style={{ color: '#2b5797' }} /></button>
                      <button title="Unsubscribe" onClick={() => handleUnsubscribe(c.id)} className="p-1.5 rounded-lg hover:bg-yellow-50 transition-colors"><UserMinus size={14} style={{ color: '#92400e' }} /></button>
                      <button title="Delete" onClick={() => handleDelete(c.id)} className="p-1.5 rounded-lg hover:bg-red-50 transition-colors"><Trash2 size={14} style={{ color: '#991b1b' }} /></button>
                    </div>
                  </td>
                </tr>
              ))}
              {contacts.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center py-12">
                    <Users size={40} className="mx-auto mb-3" style={{ color: '#d1d5db' }} />
                    <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>No contacts found</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs" style={{ color: '#6b7a99' }}>
            Page {page} of {totalPages} ({total} contacts)
          </p>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-40"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', color: '#2b5797' }}>
              <ChevronLeft size={14} /> Previous
            </button>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-40"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', color: '#2b5797' }}>
              Next <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}

      {showAdd && <AddContactModal onClose={() => setShowAdd(false)} onSave={handleCreate} />}
      {showImport && <ImportModal onClose={() => setShowImport(false)} onImport={handleImport} />}
    </div>
  );
}
