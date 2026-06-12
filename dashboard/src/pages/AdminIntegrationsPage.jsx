import { useState, useEffect } from 'react';
import { Key, Eye, EyeOff, CheckCircle, XCircle, Loader2, Plus, Unplug, Zap, X } from 'lucide-react';
import { getIntegrations, updateIntegration, testIntegration, disconnectIntegration, createIntegration } from '../lib/api';

const CATEGORY_ICONS = {
  email: '\u{1F4E7}',
  social: '\u{1F310}',
  enrichment: '\u{1F50D}',
  ai: '\u{1F916}',
  scheduling: '\u{1F4C5}',
  custom: '\u{2699}\u{FE0F}',
};

const CATEGORY_LABELS = {
  email: 'Email Providers',
  social: 'Social Platforms',
  enrichment: 'Data Enrichment',
  ai: 'AI Services',
  scheduling: 'Scheduling',
  custom: 'Custom',
};

const CATEGORIES = ['email', 'social', 'enrichment', 'ai', 'scheduling', 'custom'];

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

function fieldLabel(name) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function isSecretField(name) {
  return /key|secret|token|password/i.test(name);
}

function IntegrationModal({ integration, onClose, onSave, onTest, onDisconnect }) {
  const [formData, setFormData] = useState({});
  const [showSecrets, setShowSecrets] = useState({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState(null);

  // extra_config.fields is an array of strings like ["api_key", "campaign_id"]
  const fields = integration?.extra_config?.fields || [];

  useEffect(() => {
    if (integration) {
      const initial = {};
      fields.forEach(f => { initial[f] = ''; });
      setFormData(initial);
    }
  }, [integration]);

  if (!integration) return null;

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      // Build the payload the backend expects
      // If there's a single api_key field, send it as api_key_encrypted
      // All other fields go into extra_config
      const payload = {};
      const extraConfig = { ...integration.extra_config };

      if (formData.api_key) {
        payload.api_key_encrypted = formData.api_key;
      }

      // Store all field values in extra_config for reference
      const configValues = {};
      fields.forEach(f => {
        if (f !== 'api_key' && formData[f]) {
          configValues[f] = formData[f];
        }
      });
      if (Object.keys(configValues).length > 0) {
        payload.extra_config = { ...extraConfig, values: configValues };
      }

      // If no api_key field but there's a primary secret field, use first one
      if (!payload.api_key_encrypted) {
        const secretField = fields.find(f => isSecretField(f));
        if (secretField && formData[secretField]) {
          payload.api_key_encrypted = formData[secretField];
        }
      }

      await onSave(integration.id, payload);
      setMessage({ type: 'success', text: 'Saved successfully' });
    } catch (e) {
      setMessage({ type: 'error', text: e.message || 'Failed to save' });
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setMessage(null);
    try {
      await onTest(integration.id);
      setMessage({ type: 'success', text: 'Connection test passed' });
    } catch (e) {
      setMessage({ type: 'error', text: e.message || 'Connection test failed' });
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(15, 26, 46, 0.5)', backdropFilter: 'blur(4px)' }}>
      <div
        className="w-full max-w-lg rounded-2xl p-6"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.98) 0%, rgba(243,245,252,0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 24px 64px rgba(15, 26, 46, 0.2)',
        }}
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{CATEGORY_ICONS[integration.service_category] || '\u{2699}\u{FE0F}'}</span>
            <div>
              <h3 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>{integration.display_name}</h3>
              <p className="text-xs capitalize" style={{ color: '#6b7a99' }}>{integration.service_category}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 transition-colors">
            <X size={20} style={{ color: '#6b7a99' }} />
          </button>
        </div>

        {integration.api_key_masked && (
          <div className="mb-4 px-4 py-2.5 rounded-lg text-xs" style={{ background: 'rgba(238, 241, 248, 0.7)', color: '#6b7a99' }}>
            Current key: <span className="font-mono">{integration.api_key_masked}</span>
          </div>
        )}

        {fields.length === 0 ? (
          <p className="text-sm py-4" style={{ color: '#6b7a99' }}>No configurable fields for this integration.</p>
        ) : (
          <div className="space-y-4">
            {fields.map(fieldName => {
              const secret = isSecretField(fieldName);
              return (
                <div key={fieldName}>
                  <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>
                    {fieldLabel(fieldName)}
                  </label>
                  <div className="relative">
                    <input
                      type={secret ? (showSecrets[fieldName] ? 'text' : 'password') : 'text'}
                      value={formData[fieldName] || ''}
                      onChange={e => setFormData(prev => ({ ...prev, [fieldName]: e.target.value }))}
                      placeholder={`Enter ${fieldLabel(fieldName).toLowerCase()}`}
                      className="w-full px-4 py-2.5 rounded-lg text-sm outline-none transition-all"
                      style={{
                        border: '1px solid rgba(91, 126, 194, 0.2)',
                        background: 'rgba(238, 241, 248, 0.5)',
                        color: '#1b2a4a',
                      }}
                      onFocus={e => { e.target.style.borderColor = '#5b7ec2'; e.target.style.boxShadow = '0 0 0 3px rgba(91, 126, 194, 0.1)'; }}
                      onBlur={e => { e.target.style.borderColor = 'rgba(91, 126, 194, 0.2)'; e.target.style.boxShadow = 'none'; }}
                    />
                    {secret && (
                      <button
                        type="button"
                        onClick={() => setShowSecrets(prev => ({ ...prev, [fieldName]: !prev[fieldName] }))}
                        className="absolute right-3 top-1/2 -translate-y-1/2"
                        style={{ color: '#6b7a99' }}
                      >
                        {showSecrets[fieldName] ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {message && (
          <div className="mt-4 flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium"
            style={{
              background: message.type === 'success' ? 'rgba(209, 250, 229, 0.5)' : 'rgba(254, 226, 226, 0.5)',
              color: message.type === 'success' ? '#065f46' : '#991b1b',
            }}
          >
            {message.type === 'success' ? <CheckCircle size={14} /> : <XCircle size={14} />}
            {message.text}
          </div>
        )}

        <div className="flex items-center justify-between mt-6 pt-4" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.1)' }}>
          <div className="flex items-center gap-2">
            {integration.is_connected && (
              <button
                onClick={() => onDisconnect(integration.id)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all hover:shadow-md"
                style={{ background: 'linear-gradient(135deg, #fee2e2, #fecaca)', color: '#991b1b' }}
              >
                <Unplug size={14} />
                Disconnect
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleTest}
              disabled={testing}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition-all hover:shadow-md disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af' }}
            >
              {testing ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
              Test
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white transition-all hover:shadow-md disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #059669, #10b981)' }}
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
              Save & Connect
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AdminIntegrationsPage() {
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [toast, setToast] = useState(null);

  useEffect(() => { loadData(); }, []);

  async function loadData() {
    try {
      const data = await getIntegrations();
      setIntegrations(data.integrations || []);
    } catch (e) {
      console.error('Failed to load integrations:', e);
      setToast({ message: 'Failed to load integrations', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(id, payload) {
    try {
      await updateIntegration(id, payload);
      setToast({ message: 'Integration saved successfully', type: 'success' });
      await loadData();
      setSelected(null);
    } catch (e) {
      setToast({ message: e.message || 'Failed to save integration', type: 'error' });
    }
  }

  async function handleTest(id) {
    try {
      const result = await testIntegration(id);
      setToast({ message: result.message || 'Connection test passed', type: 'success' });
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Connection test failed', type: 'error' });
    }
  }

  async function handleDisconnect(id) {
    if (!window.confirm('Disconnect this integration? Any active workflows using it will be affected.')) return;
    try {
      await disconnectIntegration(id);
      setToast({ message: 'Integration disconnected', type: 'success' });
      await loadData();
      setSelected(null);
    } catch (e) {
      setToast({ message: e.message || 'Failed to disconnect', type: 'error' });
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  const grouped = {};
  CATEGORIES.forEach(cat => { grouped[cat] = []; });
  integrations.forEach(integ => {
    const cat = integ.service_category || 'custom';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(integ);
  });

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Integrations</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Manage API connections and service integrations</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium px-3 py-1.5 rounded-full" style={{ background: 'linear-gradient(135deg, #d1fae5, #a7f3d0)', color: '#065f46' }}>
            {integrations.filter(i => i.is_connected).length} connected
          </span>
        </div>
      </div>

      {CATEGORIES.map(category => {
        const items = grouped[category];
        if (!items || items.length === 0) return null;

        return (
          <div key={category}>
            <h3 className="text-sm font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: '#374a6d' }}>
              <span>{CATEGORY_ICONS[category]}</span>
              {CATEGORY_LABELS[category] || category}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {items.map(integ => (
                <button
                  key={integ.id}
                  onClick={() => setSelected(integ)}
                  className="text-left rounded-xl p-5 transition-all duration-200 hover:shadow-lg"
                  style={{
                    background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
                    border: '1px solid rgba(255, 255, 255, 0.6)',
                    boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
                    borderLeft: integ.is_connected ? '3px solid #22c55e' : '3px solid transparent',
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-xl">{CATEGORY_ICONS[integ.service_category] || '\u{2699}\u{FE0F}'}</span>
                      <div>
                        <p className="text-sm font-semibold" style={{ color: '#1b2a4a' }}>{integ.display_name}</p>
                        <p className="text-xs" style={{ color: '#9aa5bd' }}>{integ.service_name}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div
                        className="w-2.5 h-2.5 rounded-full"
                        style={{
                          background: integ.is_connected ? '#22c55e' : '#d1d5db',
                          boxShadow: integ.is_connected ? '0 0 6px rgba(34, 197, 94, 0.5)' : 'none',
                        }}
                      />
                      <span className="text-xs font-medium" style={{ color: integ.is_connected ? '#059669' : '#9ca3af' }}>
                        {integ.is_connected ? 'Connected' : 'Not set'}
                      </span>
                    </div>
                  </div>
                  {integ.api_key_masked && (
                    <p className="text-xs mt-2 font-mono" style={{ color: '#9aa5bd' }}>{integ.api_key_masked}</p>
                  )}
                </button>
              ))}
            </div>
          </div>
        );
      })}

      {integrations.length === 0 && (
        <div className="text-center py-16">
          <Key size={40} style={{ color: '#d1d5db' }} className="mx-auto mb-3" />
          <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>No integrations configured</p>
          <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>Integrations will appear here once configured in the backend</p>
        </div>
      )}

      {selected && (
        <IntegrationModal
          integration={selected}
          onClose={() => setSelected(null)}
          onSave={handleSave}
          onTest={handleTest}
          onDisconnect={handleDisconnect}
        />
      )}
    </div>
  );
}
