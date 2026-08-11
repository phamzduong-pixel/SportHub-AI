import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { LoadingSkeleton } from '@/components/common';
import { useAuth } from '@/contexts/AuthContext';
import type { AccountRole } from '@/types/auth';

function Pending() { return <div className="mx-auto max-w-4xl p-10"><LoadingSkeleton lines={5} /></div>; }
export function homeForRole(role: AccountRole) { return role === 'CUSTOMER' ? '/customer/dashboard' : role === 'SYSTEM_ADMIN' ? '/system-admin' : '/management/dashboard'; }
export function AuthGuard({ children }: { children: ReactNode }) { const { user, loading } = useAuth(); const location = useLocation(); if (loading) return <Pending />; return user ? children : <Navigate to="/login" replace state={{ from: location.pathname }} />; }
export function RoleGuard({ roles, children }: { roles: AccountRole[]; children: ReactNode }) { const { user, loading } = useAuth(); if (loading) return <Pending />; if (!user) return <Navigate to="/login" replace />; const granted = user.roles?.length ? user.roles : [user.role]; if (!roles.some((role) => granted.includes(role))) return <Navigate to={homeForRole(user.role)} replace />; return children; }
export function OwnerVerificationGuard({ children }: { children: ReactNode }) { const { user, loading } = useAuth(); if (loading) return <Pending />; return user?.role === 'OWNER' || user?.role === 'MANAGER' ? children : <Navigate to="/login" replace />; }
