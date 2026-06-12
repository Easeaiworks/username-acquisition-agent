/**
 * Auth context — stores the Dashboard API key and user role in memory for the session.
 * Uses sessionStorage so it survives page refreshes but not tab close.
 */

import { createContext, useContext, useState, useCallback } from 'react';

const AuthContext = createContext(null);

const STORAGE_KEY = 'sean_dashboard_api_key';
const ROLE_KEY = 'sean_dashboard_role';

export function AuthProvider({ children }) {
  const [apiKey, setApiKeyState] = useState(() => {
    try { return sessionStorage.getItem(STORAGE_KEY) || ''; }
    catch { return ''; }
  });

  const [userRole, setUserRoleState] = useState(() => {
    try { return sessionStorage.getItem(ROLE_KEY) || 'viewer'; }
    catch { return 'viewer'; }
  });

  const setApiKey = useCallback((key) => {
    setApiKeyState(key);
    try { sessionStorage.setItem(STORAGE_KEY, key); }
    catch { /* private browsing */ }
  }, []);

  const setUserRole = useCallback((role) => {
    setUserRoleState(role);
    try { sessionStorage.setItem(ROLE_KEY, role); }
    catch { /* private browsing */ }
  }, []);

  const logout = useCallback(() => {
    setApiKeyState('');
    setUserRoleState('viewer');
    try {
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(ROLE_KEY);
    } catch { /* ignore */ }
  }, []);

  return (
    <AuthContext.Provider value={{
      apiKey,
      setApiKey,
      logout,
      isAuthenticated: !!apiKey,
      userRole,
      setUserRole,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
