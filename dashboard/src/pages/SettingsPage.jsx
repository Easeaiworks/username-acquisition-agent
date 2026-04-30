import { useState, useEffect } from 'react';
import { Settings, Zap, Mail, MapPin, Calendar, Eye, EyeOff, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { getSettings, updateSetting, testInstantly, autoSetupInstantly } from '../lib/api';

function SettingRow({ setting, onSave }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  const displayValue = setting.is_secret && !showSecret
    ? (setting.has_value ? setting.value : '')
    : (setting.has_value ? setting.value : '');

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(setting.key, value);
      setEditing(false);
    } catch (e) {
      console.error('Save error:', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="flex items-center justify-between py-4 px-4 transition-all duration-200"
      style={{ borderBottom: '1px solid rgba(15,26,46,0.04)' }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(91, 126, 194, 0.04)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium" style={{ color: '#1b2a4a' }}>
            {setting.key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          </p>
          {setting.has_value && (
            <CheckCircle size={14} style={{ color: '#059669' }} />
          )}
        </div>
        <p className="text-xs mt-0.5" style={{ color: '#9aa5bd' }}>{setting.description}</p>

        {!editing && (
          <div className="flex items-center gap-1.5 mt-1">
            <p className="text-sm font-mono" style={{ color: setting.has_value ? '#374a6d' : '#c4cfe0' }}>
              {setting.has_value ? displayValue : 'Not configured'}
            </p>
            {setting.is_secret && setting.has_value && (
              <button
                onClick={() => setShowSecret(!showSecret)}
                className="p-0.5 rounded"
                style={{ color: '#9aa5bd' }}
              >
                {showSecret ? <EyeOff size={12} /> : <Eye size={12} />}
              </button>
            )}
          </div>
        )}

        {editing && (
          <div className="flex items-center gap-2 mt-2">
            <input
              type={setting.is_secret ? 'password' : 'text'}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={`Enter ${setting.key.replace(/_/g, ' ')}`}
              className="flex-1 px-3 py-1.5 text-sm rounded-lg"
              style={{
                border: '1px solid rgba(91,126,194,0.2)',
                background: 'rgba(255,255,255,0.9)',
                color: '#1b2a4a',
                outline: 'none',
              }}
              onFocus={(e) => { e.target.style.borderColor = 'rgba(58,82,137,0.5)'; }}
              onBlur={(e) => { e.target.style.borderColor = 'rgba(91,126,194,0.2)'; }}
              autoFocus
            />
            <button
              onClick={handleSave}
              disabled={saving || !value.trim()}
              className="px-3 py-1.5 text-xs font-medium rounded-lg text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #3a5289, #2b3f6b)' }}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={() => setEditing(false)}
              className="px-3 py-1.5 text-xs font-medium rounded-lg"
              style={{ color: '#6b7a99', border: '1px solid rgba(91,126,194,0.15)' }}
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {!editing && (
        <button
          onClick={() => { setEditing(true); setValue(''); }}
          className="px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200"
          style={{
            color: '#3a5289',
            border: '1px solid rgba(58,82,137,0.2)',
            background: 'rgba(58,82,137,0.04)',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(58,82,137,0.1)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(58,82,137,0.04)'; }}
        >
          {setting.has_value ? 'Update' : 'Configure'}
        </button>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  // Auto-setup state
  const [setupMode, setSetupMode] = useState(false);
  const [setupKey, setSetupKey] = useState('');
  const [setupName, setSetupName] = useState('S2Media - Username Acquisition Outreach');
  const [setupLoading, setSetupLoading] = useState(false);
  const [setupResult, setSetupResult] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getSettings();
      setSettings(data.settings || []);
    } catch (e) {
      console.error('Settings load error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSave = async (key, value) => {
    await updateSetting(key, value);
    await load();
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testInstantly();
      setTestResult(result);
    } catch (e) {
      setTestResult({ ok: false, error: e.message });
    } finally {
      setTesting(false);
    }
  };

  const handleAutoSetup = async () => {
    if (!setupKey.trim()) return;
    setSetupLoading(true);
    setSetupResult(null);
    try {
      const result = await autoSetupInstantly(setupKey, setupName);
      setSetupResult(result);
      if (result.ok) {
        await load();
        setSetupMode(false);
      }
    } catch (e) {
      setSetupResult({ ok: false, error: e.message });
    } finally {
      setSetupLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  const instantlySettings = settings.filter(s => s.key.startsWith('instantly_'));
  const senderSettings = settings.filter(s => ['sender_email', 'sender_name', 'physical_address'].includes(s.key));
  const otherSettings = settings.filter(s => !s.key.startsWith('instantly_') && !['sender_email', 'sender_name', 'physical_address'].includes(s.key));

  const hasInstantlyKey = instantlySettings.find(s => s.key === 'instantly_api_key')?.has_value;
  const hasInstantlyCampaign = instantlySettings.find(s => s.key === 'instantly_campaign_id')?.has_value;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Settings</h2>
        <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>
          Configure your outreach provider, sender details, and integrations
        </p>
      </div>

      {/* Instantly Integration Card */}
      <div className="glass-card rounded-xl overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between" style={{
          background: 'linear-gradient(145deg, rgba(58,82,137,0.08), rgba(58,82,137,0.03))',
          borderBottom: '1px solid rgba(91,126,194,0.08)',
        }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{
              background: 'linear-gradient(135deg, #3a5289, #2b3f6b)',
            }}>
              <Zap size={18} className="text-white" />
            </div>
            <div>
              <h3 className="text-sm font-semibold" style={{ color: '#1b2a4a' }}>Instantly.ai Integration</h3>
              <p className="text-xs" style={{ color: '#9aa5bd' }}>
                {hasInstantlyKey && hasInstantlyCampaign
                  ? 'Connected and ready to send'
                  : 'Connect your Instantly account to enable outreach'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {hasInstantlyKey && (
              <button
                onClick={handleTest}
                disabled={testing}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200"
                style={{
                  color: '#3a5289',
                  border: '1px solid rgba(58,82,137,0.2)',
                  background: 'rgba(58,82,137,0.04)',
                }}
              >
                {testing ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
                {testing ? 'Testing...' : 'Test Connection'}
              </button>
            )}
            {!hasInstantlyKey && !setupMode && (
              <button
                onClick={() => setSetupMode(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-white"
                style={{ background: 'linear-gradient(135deg, #3a5289, #2b3f6b)' }}
              >
                <Zap size={12} />
                Quick Setup
              </button>
            )}
          </div>
        </div>

        {/* Test result */}
        {testResult && (
          <div className="px-5 py-3" style={{
            background: testResult.ok ? 'rgba(5,150,105,0.06)' : 'rgba(220,38,38,0.06)',
            borderBottom: '1px solid rgba(91,126,194,0.06)',
          }}>
            <div className="flex items-center gap-2">
              {testResult.ok ? (
                <CheckCircle size={14} style={{ color: '#059669' }} />
              ) : (
                <XCircle size={14} style={{ color: '#dc2626' }} />
              )}
              <span className="text-sm font-medium" style={{ color: testResult.ok ? '#059669' : '#dc2626' }}>
                {testResult.ok
                  ? `Connected — ${testResult.sending_accounts} sending account${testResult.sending_accounts !== 1 ? 's' : ''} found`
                  : testResult.error}
              </span>
            </div>
            {testResult.ok && testResult.accounts?.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {testResult.accounts.map((a, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full" style={{
                    background: 'rgba(5,150,105,0.1)',
                    color: '#059669',
                  }}>
                    {a.email}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Quick setup form */}
        {setupMode && (
          <div className="px-5 py-4" style={{
            background: 'rgba(58,82,137,0.03)',
            borderBottom: '1px solid rgba(91,126,194,0.06)',
          }}>
            <h4 className="text-sm font-semibold mb-3" style={{ color: '#374a6d' }}>Quick Setup</h4>
            <p className="text-xs mb-3" style={{ color: '#6b7a99' }}>
              Enter your Instantly V2 API key and we'll automatically create a campaign with the right template variables.
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: '#374a6d' }}>API Key</label>
                <input
                  type="password"
                  value={setupKey}
                  onChange={(e) => setSetupKey(e.target.value)}
                  placeholder="Paste your Instantly V2 API key"
                  className="w-full px-3 py-2 text-sm rounded-lg"
                  style={{
                    border: '1px solid rgba(91,126,194,0.2)',
                    background: 'rgba(255,255,255,0.9)',
                    color: '#1b2a4a',
                    outline: 'none',
                  }}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: '#374a6d' }}>Campaign Name</label>
                <input
                  type="text"
                  value={setupName}
                  onChange={(e) => setSetupName(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg"
                  style={{
                    border: '1px solid rgba(91,126,194,0.2)',
                    background: 'rgba(255,255,255,0.9)',
                    color: '#1b2a4a',
                    outline: 'none',
                  }}
                />
              </div>
              {setupResult && !setupResult.ok && (
                <div className="flex items-center gap-2 text-sm" style={{ color: '#dc2626' }}>
                  <XCircle size={14} />
                  {setupResult.error}
                </div>
              )}
              {setupResult && setupResult.ok && (
                <div className="flex items-center gap-2 text-sm" style={{ color: '#059669' }}>
                  <CheckCircle size={14} />
                  {setupResult.message} (Campaign: {setupResult.campaign_id?.slice(0, 8)}...)
                </div>
              )}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleAutoSetup}
                  disabled={setupLoading || !setupKey.trim()}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg text-white disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg, #3a5289, #2b3f6b)' }}
                >
                  {setupLoading ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                  {setupLoading ? 'Setting up...' : 'Connect & Create Campaign'}
                </button>
                <button
                  onClick={() => { setSetupMode(false); setSetupResult(null); }}
                  className="px-4 py-2 text-sm font-medium rounded-lg"
                  style={{ color: '#6b7a99', border: '1px solid rgba(91,126,194,0.15)' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Instantly settings rows */}
        {instantlySettings.map(s => (
          <SettingRow key={s.key} setting={s} onSave={handleSave} />
        ))}
      </div>

      {/* Sender Info Card */}
      <div className="glass-card rounded-xl overflow-hidden">
        <div className="px-5 py-4" style={{
          background: 'linear-gradient(145deg, rgba(58,82,137,0.08), rgba(58,82,137,0.03))',
          borderBottom: '1px solid rgba(91,126,194,0.08)',
        }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{
              background: 'linear-gradient(135deg, #22c55e, #16a34a)',
            }}>
              <Mail size={18} className="text-white" />
            </div>
            <div>
              <h3 className="text-sm font-semibold" style={{ color: '#1b2a4a' }}>Sender Details</h3>
              <p className="text-xs" style={{ color: '#9aa5bd' }}>Configure who outreach emails come from</p>
            </div>
          </div>
        </div>
        {senderSettings.map(s => (
          <SettingRow key={s.key} setting={s} onSave={handleSave} />
        ))}
      </div>

      {/* Other Settings Card */}
      {otherSettings.length > 0 && (
        <div className="glass-card rounded-xl overflow-hidden">
          <div className="px-5 py-4" style={{
            background: 'linear-gradient(145deg, rgba(58,82,137,0.08), rgba(58,82,137,0.03))',
            borderBottom: '1px solid rgba(91,126,194,0.08)',
          }}>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #a855f7, #7c3aed)',
              }}>
                <Calendar size={18} className="text-white" />
              </div>
              <div>
                <h3 className="text-sm font-semibold" style={{ color: '#1b2a4a' }}>Other Integrations</h3>
                <p className="text-xs" style={{ color: '#9aa5bd' }}>Calendly and other connected services</p>
              </div>
            </div>
          </div>
          {otherSettings.map(s => (
            <SettingRow key={s.key} setting={s} onSave={handleSave} />
          ))}
        </div>
      )}
    </div>
  );
}
