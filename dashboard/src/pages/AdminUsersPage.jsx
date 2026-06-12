import { useState, useEffect } from 'react';
import { Users, Plus, RefreshCw, Shield, ShieldCheck, Eye, X, CheckCircle, XCircle, Loader2, Copy, Check } from 'lucide-react';
import { getAdminUsers, createAdminUser, updateAdminUser, deleteAdminUser, regenerateUserKey } from '../lib/api';

const ROLE_STYLES = {
  super_admin: { bg: 'linear-gradient(135deg, #ede9fe, #ddd6fe)', color: '#5b21b6' },
  admin: { bg: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af' },
  viewer: { bg: 'linear-gradient(135deg, #f3f4f6, #e5e7eb)', color: '#374151' },
};

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

function NewKeyDialog({ apiKey, onClose }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(apiKey).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(15, 26, 46, 0.5)', backdropFilter: 'blur(4px)' }}>
      <div
        className="w-full max-w-md rounded-2xl p-6"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.98) 0%, rgba(243,245,252,0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 24px 64px rgba(15, 26, 46, 0.2)',
        }}
      >
        <div className="text-center mb-4">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3" style={{ background: 'linear-gradient(135deg, #d1fae5, #a7f3d0)' }}>
            <ShieldCheck size={24} style={{ color: '#059669' }} />
          </div>
          <h3 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>New API Key Generated</h3>
          <p className="text-xs mt-1" style={{ color: '#ef4444' }}>
            Copy this key now. It will not be shown again.
          </p>
        </div>

        <div className="flex items-center gap-2 p-3 rounded-lg font-mono text-sm" style={{ background: 'rgba(15, 26, 46, 0.04)', border: '1px solid rgba(91, 126, 194, 0.15)' }}>
          <code className="flex-1 break-all" style={{ color: '#1b2a4a' }}>{apiKey}</code>
          <button
            onClick={handleCopy}
            className="shrink-0 p-2 rounded-lg transition-all hover:shadow-sm"
            style={{ background: copied ? 'rgba(16, 185, 129, 0.1)' : 'rgba(91, 126, 194, 0.08)' }}
            title="Copy to clipboard"
          >
            {copied ? <Check size={16} style={{ color: '#059669' }} /> : <Copy size={16} style={{ color: '#5b7ec2' }} />}
          </button>
        </div>

        <button
          onClick={onClose}
          className="w-full mt-4 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-lg"
          style={{ background: 'linear-gradient(135deg, #3a5289, #5b7ec2)' }}
        >
          I've Copied the Key
        </button>
      </div>
    </div>
  );
}

function CreateUserModal({ onClose, onCreate }) {
  const [form, setForm] = useState({ email: '', name: '', role: 'viewer' });
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await onCreate(form);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(15, 26, 46, 0.5)', backdropFilter: 'blur(4px)' }}>
      <div
        className="w-full max-w-md rounded-2xl p-6"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.98) 0%, rgba(243,245,252,0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 24px 64px rgba(15, 26, 46, 0.2)',
        }}
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>Add User</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100"><X size={20} style={{ color: '#6b7a99' }} /></button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>
              Email <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="email"
              required
              value={form.email}
              onChange={e => setForm(prev => ({ ...prev, email: e.target.value }))}
              placeholder="user@company.com"
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              onFocus={e => { e.target.style.borderColor = '#5b7ec2'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(91, 126, 194, 0.2)'; }}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>
              Name <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="text"
              required
              value={form.name}
              onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Full name"
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              onFocus={e => { e.target.style.borderColor = '#5b7ec2'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(91, 126, 194, 0.2)'; }}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Role</label>
            <select
              value={form.role}
              onChange={e => setForm(prev => ({ ...prev, role: e.target.value }))}
              className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
            >
              <option value="viewer">Viewer</option>
              <option value="admin">Admin</option>
              <option value="super_admin">Super Admin</option>
            </select>
          </div>

          <div className="flex justify-end gap-3 pt-4" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.1)' }}>
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-gray-100" style={{ color: '#6b7a99' }}>
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-lg disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #3a5289, #5b7ec2)' }}
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              Add User
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKey, setNewKey] = useState(null);
  const [editingRole, setEditingRole] = useState(null);

  useEffect(() => { loadData(); }, []);

  async function loadData() {
    try {
      const data = await getAdminUsers();
      setUsers(Array.isArray(data) ? data : data.users || []);
    } catch (e) {
      console.error('Failed to load users:', e);
      setToast({ message: 'Failed to load users', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(formData) {
    try {
      const result = await createAdminUser(formData);
      setToast({ message: 'User created successfully', type: 'success' });
      setShowCreateModal(false);
      if (result.api_key) {
        setNewKey(result.api_key);
      }
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to create user', type: 'error' });
    }
  }

  async function handleRoleChange(id, newRole) {
    try {
      await updateAdminUser(id, { role: newRole });
      setToast({ message: 'Role updated', type: 'success' });
      setEditingRole(null);
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to update role', type: 'error' });
    }
  }

  async function handleToggleActive(id, currentlyActive) {
    try {
      await updateAdminUser(id, { is_active: !currentlyActive });
      setToast({ message: currentlyActive ? 'User deactivated' : 'User reactivated', type: 'success' });
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to update user', type: 'error' });
    }
  }

  async function handleRegenerateKey(id, name) {
    if (!window.confirm(`Regenerate API key for ${name}? The current key will stop working immediately.`)) return;
    try {
      const result = await regenerateUserKey(id);
      if (result.api_key) {
        setNewKey(result.api_key);
      }
      setToast({ message: 'API key regenerated', type: 'success' });
    } catch (e) {
      setToast({ message: e.message || 'Failed to regenerate key', type: 'error' });
    }
  }

  function maskApiKey(key) {
    if (!key) return '--------';
    if (key.length <= 8) return key.substring(0, 4) + '****';
    return key.substring(0, 4) + '****' + key.substring(key.length - 4);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      {newKey && <NewKeyDialog apiKey={newKey} onClose={() => setNewKey(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2" style={{ color: '#1b2a4a' }}>
            <Shield size={22} style={{ color: '#5b7ec2' }} />
            User Management
          </h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Manage dashboard users and API access</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-lg"
          style={{ background: 'linear-gradient(135deg, #3a5289, #5b7ec2)' }}
        >
          <Plus size={16} />
          Add User
        </button>
      </div>

      {/* Users Table */}
      <div className="glass-table rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(15, 26, 46, 0.06)', background: 'rgba(238, 241, 248, 0.5)' }}>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Role</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Last Login</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>API Key</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm" style={{ color: '#9aa5bd' }}>
                    <Users size={32} className="mx-auto mb-2 opacity-40" />
                    No users found
                  </td>
                </tr>
              ) : (
                users.map(user => {
                  const roleStyle = ROLE_STYLES[user.role] || ROLE_STYLES.viewer;
                  return (
                    <tr
                      key={user.id}
                      className="transition-all duration-200"
                      style={{ borderBottom: '1px solid rgba(15, 26, 46, 0.04)' }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(91, 126, 194, 0.04)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white"
                            style={{ background: 'linear-gradient(135deg, #3a5289, #5b7ec2)' }}
                          >
                            {(user.name || user.email || '?').charAt(0).toUpperCase()}
                          </div>
                          <span className="font-medium" style={{ color: '#374a6d' }}>{user.name || '(unnamed)'}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: '#6b7a99' }}>
                        {user.email}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {editingRole === user.id ? (
                          <select
                            value={user.role}
                            onChange={e => handleRoleChange(user.id, e.target.value)}
                            onBlur={() => setEditingRole(null)}
                            autoFocus
                            className="px-2 py-1 rounded text-xs font-semibold outline-none"
                            style={{ border: '1px solid rgba(91, 126, 194, 0.3)', background: 'white', color: '#1b2a4a' }}
                          >
                            <option value="viewer">Viewer</option>
                            <option value="admin">Admin</option>
                            <option value="super_admin">Super Admin</option>
                          </select>
                        ) : (
                          <button
                            onClick={() => setEditingRole(user.id)}
                            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize cursor-pointer transition-all hover:shadow-sm"
                            style={{ background: roleStyle.bg, color: roleStyle.color }}
                            title="Click to change role"
                          >
                            {(user.role || 'viewer').replace(/_/g, ' ')}
                          </button>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <button
                          onClick={() => handleToggleActive(user.id, user.is_active)}
                          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold cursor-pointer transition-all hover:shadow-sm"
                          style={{
                            background: user.is_active
                              ? 'linear-gradient(135deg, #d1fae5, #a7f3d0)'
                              : 'linear-gradient(135deg, #fee2e2, #fecaca)',
                            color: user.is_active ? '#065f46' : '#991b1b',
                          }}
                          title={user.is_active ? 'Click to deactivate' : 'Click to reactivate'}
                        >
                          {user.is_active ? 'Active' : 'Inactive'}
                        </button>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: '#6b7a99' }}>
                        {user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <code className="text-xs font-mono px-2 py-1 rounded" style={{ background: 'rgba(15, 26, 46, 0.04)', color: '#6b7a99' }}>
                          {maskApiKey(user.api_key_preview || user.api_key)}
                        </code>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleRegenerateKey(user.id, user.name || user.email)}
                            className="p-1.5 rounded-lg transition-all hover:shadow-sm"
                            style={{ background: 'rgba(91, 126, 194, 0.08)' }}
                            title="Regenerate API Key"
                          >
                            <RefreshCw size={14} style={{ color: '#5b7ec2' }} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <CreateUserModal onClose={() => setShowCreateModal(false)} onCreate={handleCreate} />
      )}
    </div>
  );
}
