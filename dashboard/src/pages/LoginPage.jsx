import { useState } from 'react';
import { Shield, Eye, EyeOff, AlertCircle, ArrowRight, Mail, Lock } from 'lucide-react';
import { login } from '../lib/api';

export default function LoginPage({ onLogin, onLoginSuccess }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;

    setLoading(true);
    setError('');

    try {
      const data = await login(email.trim(), password);

      // data = { api_key, user_id, email, name, role }
      // Store the API key for subsequent requests
      onLogin(data.api_key);

      // If the parent wants the full user info (for role, name, etc.)
      if (onLoginSuccess) {
        onLoginSuccess(data);
      }
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.');
    } finally {
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
          <h2 className="text-lg font-semibold mb-1" style={{ color: '#1e293b' }}>Sign In</h2>
          <p className="text-sm mb-6" style={{ color: '#64748b' }}>
            Enter your credentials to access the dashboard.
          </p>

          <form onSubmit={handleSubmit}>
            {/* Email field */}
            <div className="relative mb-4">
              <div className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: '#94a3b8' }}>
                <Mail size={18} />
              </div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email address"
                className="w-full pl-10 pr-4 py-3 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: '#f8fafc',
                  border: error ? '2px solid #ef4444' : '2px solid #e2e8f0',
                  color: '#1e293b',
                }}
                onFocus={(e) => { if (!error) e.target.style.borderColor = '#2b5797'; }}
                onBlur={(e) => { if (!error) e.target.style.borderColor = '#e2e8f0'; }}
                autoFocus
                autoComplete="email"
              />
            </div>

            {/* Password field */}
            <div className="relative mb-4">
              <div className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: '#94a3b8' }}>
                <Lock size={18} />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full pl-10 pr-12 py-3 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: '#f8fafc',
                  border: error ? '2px solid #ef4444' : '2px solid #e2e8f0',
                  color: '#1e293b',
                }}
                onFocus={(e) => { if (!error) e.target.style.borderColor = '#2b5797'; }}
                onBlur={(e) => { if (!error) e.target.style.borderColor = '#e2e8f0'; }}
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2"
                style={{ color: '#94a3b8' }}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
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
              disabled={loading || !email.trim() || !password.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold text-white transition-all"
              style={{
                background: loading || !email.trim() || !password.trim()
                  ? '#94a3b8'
                  : 'linear-gradient(135deg, #1e3a5f 0%, #2b5797 100%)',
                cursor: loading || !email.trim() || !password.trim() ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Signing in...
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
          Secured with encrypted password authentication
        </p>
      </div>
    </div>
  );
}
