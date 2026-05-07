import { useState } from 'react';
import { Shield, Eye, EyeOff, AlertCircle, ArrowRight } from 'lucide-react';

export default function LoginPage({ onLogin }) {
  const [key, setKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!key.trim()) return;

    setLoading(true);
    setError('');

    try {
      // Validate the key by hitting the health-adjacent system status endpoint
      const res = await fetch('/api/settings/system/status', {
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': key.trim(),
        },
      });

      if (res.status === 401 || res.status === 403) {
        setError('Invalid API key. Check your DASHBOARD_API_KEY in Railway.');
        setLoading(false);
        return;
      }

      if (!res.ok) {
        setError(`Server error: ${res.status}`);
        setLoading(false);
        return;
      }

      // Key is valid — store it and proceed
      onLogin(key.trim());
    } catch (err) {
      setError('Could not connect to backend. Is the server running?');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#eef1f8' }}>
      <div className="w-full max-w-md mx-4">
        {/* Logo / Header */}
        <div className="text-center mb-8">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{ background: 'linear-gradient(135deg, #1e3a5f 0%, #2b5797 100%)' }}
          >
            <Shield size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold" style={{ color: '#1e293b' }}>Sean Lead Agent</h1>
          <p className="text-sm mt-1" style={{ color: '#64748b' }}>Username Acquisition System</p>
        </div>

        {/* Login Card */}
        <div className="rounded-2xl p-8 shadow-lg" style={{ background: 'white', border: '1px solid #e2e8f0' }}>
          <h2 className="text-lg font-semibold mb-1" style={{ color: '#1e293b' }}>Dashboard Access</h2>
          <p className="text-sm mb-6" style={{ color: '#64748b' }}>
            Enter your Dashboard API key to continue. This is the <code style={{ background: '#f1f5f9', padding: '2px 6px', borderRadius: '4px', fontSize: '12px' }}>DASHBOARD_API_KEY</code> set in Railway.
          </p>

          <form onSubmit={handleSubmit}>
            <div className="relative mb-4">
              <input
                type={showKey ? 'text' : 'password'}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="Enter your API key"
                className="w-full px-4 py-3 pr-12 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: '#f8fafc',
                  border: error ? '2px solid #ef4444' : '2px solid #e2e8f0',
                  color: '#1e293b',
                }}
                onFocus={(e) => { if (!error) e.target.style.borderColor = '#2b5797'; }}
                onBlur={(e) => { if (!error) e.target.style.borderColor = '#e2e8f0'; }}
                autoFocus
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2"
                style={{ color: '#94a3b8' }}
                tabIndex={-1}
              >
                {showKey ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>

            {error && (
              <div className="flex items-center gap-2 mb-4 p-3 rounded-lg" style={{ background: '#fef2f2', color: '#dc2626' }}>
                <AlertCircle size={16} />
                <span className="text-sm">{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !key.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold text-white transition-all"
              style={{
                background: loading || !key.trim()
                  ? '#94a3b8'
                  : 'linear-gradient(135deg, #1e3a5f 0%, #2b5797 100%)',
                cursor: loading || !key.trim() ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Verifying...
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs mt-6" style={{ color: '#94a3b8' }}>
          Secured with API key authentication
        </p>
      </div>
    </div>
  );
}
