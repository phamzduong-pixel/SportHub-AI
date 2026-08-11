import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { apiRequest, clearToken, readToken, saveRefreshToken, saveToken } from '@/services/apiClient';
import type { AuthUser } from '@/types/auth';

interface AuthValue { user: AuthUser | null; loading: boolean; login: (email: string, password: string) => Promise<AuthUser>; register: (input: { full_name: string; email: string; phone: string; password: string }) => Promise<void>; logout: () => void; refreshUser: () => Promise<void>; }
const AuthContext = createContext<AuthValue | null>(null);
const clearUserScopedCache = () => { localStorage.removeItem('sporthub_auth'); localStorage.removeItem('sporthub_customer_profile'); localStorage.removeItem('sporthub_customer_bookings'); localStorage.removeItem('sporthub_customer_favorites'); sessionStorage.removeItem('sporthub_latest_booking'); };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null); const [loading, setLoading] = useState(true);
  const logout = useCallback(() => { void apiRequest('/auth/logout', { method: 'POST' }).catch(() => undefined); clearToken(); clearUserScopedCache(); setUser(null); window.dispatchEvent(new Event('sporthub-auth-updated')); }, []);
  const refreshUser = useCallback(async () => { if (!readToken()) { setUser(null); setLoading(false); return; } try { const fresh = await apiRequest<AuthUser>('/auth/me'); setUser(fresh); localStorage.setItem('sporthub_auth', JSON.stringify(fresh)); } catch { logout(); } finally { setLoading(false); } }, [logout]);
  useEffect(() => { void refreshUser(); const expired = () => { logout(); setLoading(false); }; window.addEventListener('sporthub-session-expired', expired); return () => window.removeEventListener('sporthub-session-expired', expired); }, [refreshUser, logout]);
  const login = useCallback(async (email: string, password: string) => { clearToken(); clearUserScopedCache(); const result = await apiRequest<{ access_token: string; refresh_token: string; user: AuthUser }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }); saveToken(result.access_token); saveRefreshToken(result.refresh_token); setUser(result.user); localStorage.setItem('sporthub_auth', JSON.stringify(result.user)); return result.user; }, []);
  const register = useCallback(async (input: { full_name: string; email: string; phone: string; password: string }) => { await apiRequest('/auth/register', { method: 'POST', body: JSON.stringify(input) }); }, []);
  const value = useMemo(() => ({ user, loading, login, register, logout, refreshUser }), [user, loading, login, register, logout, refreshUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('useAuth phải nằm trong AuthProvider'); return value; }
