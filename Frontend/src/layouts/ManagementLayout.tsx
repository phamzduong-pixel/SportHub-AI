import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { ManagementHeader } from '@/components/layout/ManagementHeader';
import { ManagementSidebar } from '@/components/layout/ManagementSidebar';
import { PermissionProvider } from '@/contexts/PermissionContext';

export function ManagementLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  return <PermissionProvider>
    <div className="app-canvas min-h-screen min-w-0 overflow-x-clip">
      <ManagementSidebar collapsed={collapsed} mobileOpen={mobileOpen} onToggle={() => setCollapsed((value) => !value)} onMobileClose={() => setMobileOpen(false)} />
      <div className={`min-w-0 transition-[margin] duration-200 ${collapsed ? 'lg:ml-[76px]' : 'lg:ml-64'}`}>
        <ManagementHeader onMenu={() => setMobileOpen(true)} />
        <main className="mx-auto min-w-0 max-w-[1600px] p-3 min-[375px]:p-4 sm:p-6 lg:p-7"><Outlet /></main>
      </div>
    </div>
  </PermissionProvider>;
}
