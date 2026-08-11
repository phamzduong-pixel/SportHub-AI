import { createContext, useContext, type ReactNode } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import type { ManagementModule, PermissionAction, ManagementUser } from '@/types/permissions';

interface PermissionContextValue { user: ManagementUser; can: (module: ManagementModule, action?: PermissionAction) => boolean; }
const PermissionContext = createContext<PermissionContextValue | null>(null);
const initials = (name: string) => name.split(/\s+/).slice(-2).map((part) => part[0]).join('').toUpperCase();

export function PermissionProvider({ children }: { children: ReactNode }) {
  const { user: authUser } = useAuth();
  if (!authUser || !['OWNER', 'MANAGER'].includes(authUser.role)) return null;
  const role = authUser.role as ManagementUser['role'];
  const user: ManagementUser = { id: String(authUser.id), name: authUser.full_name, email: authUser.email, role, title: role === 'OWNER' ? 'Chủ cơ sở' : 'Quản lý cơ sở', avatar: initials(authUser.full_name), avatarUrl: authUser.avatar_url, venueIds: [], status: 'active', lastActive: 'Đang hoạt động' };
  const can = (module: ManagementModule, action: PermissionAction = 'view') => role === 'OWNER' || authUser.management_permissions.includes(`${module}.${action}`) || authUser.management_permissions.includes(`${module}.manage`);
  return <PermissionContext.Provider value={{ user, can }}>{children}</PermissionContext.Provider>;
}
export function usePermission() { const value = useContext(PermissionContext); if (!value) throw new Error('usePermission phải nằm trong PermissionProvider'); return value; }
export function PermissionGuard({ module, action = 'view', children, fallback = null }: { module: ManagementModule; action?: PermissionAction; children: ReactNode; fallback?: ReactNode }) {
  const { can } = usePermission();
  return can(module, action) ? children : fallback;
}
