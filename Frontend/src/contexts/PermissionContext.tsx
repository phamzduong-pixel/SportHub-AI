import { createContext, useContext, type ReactNode } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import type { ManagementModule, PermissionAction, ManagementUser } from '@/types/permissions';

interface PermissionContextValue { user: ManagementUser; can: (module: ManagementModule, action?: PermissionAction) => boolean; }
const PermissionContext = createContext<PermissionContextValue | null>(null);
const initials = (name: string) => name.split(/\s+/).slice(-2).map((part) => part[0]).join('').toUpperCase();

export function PermissionProvider({ children }: { children: ReactNode }) {
  const { user: authUser } = useAuth();
  if (!authUser || authUser.role !== 'OWNER') return null;
  const role: ManagementUser['role'] = 'OWNER';
  const user: ManagementUser = { id: String(authUser.id), name: authUser.full_name, email: authUser.email, role, title: 'Chủ cơ sở', avatar: initials(authUser.full_name), avatarUrl: authUser.avatar_url, venueIds: [], status: 'active', lastActive: 'Đang hoạt động' };
  const can = (_module: ManagementModule, _action: PermissionAction = 'view') => true;
  return <PermissionContext.Provider value={{ user, can }}>{children}</PermissionContext.Provider>;
}
export function usePermission() { const value = useContext(PermissionContext); if (!value) throw new Error('usePermission phải nằm trong PermissionProvider'); return value; }
export function PermissionGuard({ module, action = 'view', children, fallback = null }: { module: ManagementModule; action?: PermissionAction; children: ReactNode; fallback?: ReactNode }) {
  const { can } = usePermission();
  return can(module, action) ? children : fallback;
}
