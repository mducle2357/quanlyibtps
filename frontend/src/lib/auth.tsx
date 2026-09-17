import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { REFRESH_TOKEN_KEY, api, setAccessToken, setUnauthorizedHandler } from './api';

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  must_reset_password: boolean;
}

interface AuthState {
  status: 'loading' | 'authenticated' | 'unauthenticated';
  user: CurrentUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthState['status']>('loading');
  const [user, setUser] = useState<CurrentUser | null>(null);

  const clear = useCallback(() => {
    setAccessToken(null);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setUser(null);
    setStatus('unauthenticated');
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(clear);
  }, [clear]);

  useEffect(() => {
    const rt = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!rt) {
      setStatus('unauthenticated');
      return;
    }
    (async () => {
      try {
        const { data } = await api.post('/auth/refresh', { refresh_token: rt });
        setAccessToken(data.access_token);
        localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
        const me = await api.get('/auth/me');
        setUser(me.data);
        setStatus('authenticated');
      } catch {
        clear();
      }
    })();
  }, [clear]);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post('/auth/login', { email, password });
    setAccessToken(data.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
    const me = await api.get('/auth/me');
    setUser(me.data);
    setStatus('authenticated');
  }, []);

  const logout = useCallback(async () => {
    const rt = localStorage.getItem(REFRESH_TOKEN_KEY);
    try {
      if (rt) await api.post('/auth/logout', { refresh_token: rt });
    } finally {
      clear();
    }
  }, [clear]);

  const hasRole = useCallback((...roles: string[]) => !!user && roles.some((r) => user.roles.includes(r)), [user]);

  const value = useMemo(() => ({ status, user, login, logout, hasRole }), [status, user, login, logout, hasRole]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
