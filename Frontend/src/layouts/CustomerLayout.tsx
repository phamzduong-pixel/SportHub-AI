import { Bell, CalendarDays, Heart, LayoutDashboard, ReceiptText, Settings, Store, UserRound } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';
import { PublicHeader } from '@/components/layout/PublicHeader';
import { useAuth } from '@/contexts/AuthContext';

const items = [
  { to: '/customer/dashboard', label: 'Tổng quan', short: 'Tổng quan', icon: LayoutDashboard },
  { to: '/customer/bookings', label: 'Lịch đặt của tôi', short: 'Lịch đặt', icon: CalendarDays },
  { to: '/customer/favorites', label: 'Sân yêu thích', short: 'Yêu thích', icon: Heart },
  { to: '/customer/notifications', label: 'Thông báo', short: 'Thông báo', icon: Bell },
  { to: '/customer/transactions', label: 'Giao dịch', short: 'Giao dịch', icon: ReceiptText },
  { to: '/customer/profile', label: 'Hồ sơ', short: 'Hồ sơ', icon: UserRound },
  { to: '/customer/settings', label: 'Cài đặt', short: 'Cài đặt', icon: Settings },
  { to: '/owner-application', label: 'Trở thành đối tác', short: 'Đối tác', icon: Store },
];

export function CustomerLayout() {
  const { user } = useAuth();
  const avatar = user?.full_name.split(/\s+/).slice(-2).map((part) => part[0]).join('').toUpperCase();
  return <div className="app-canvas min-h-screen min-w-0 overflow-x-clip pb-[calc(4rem+env(safe-area-inset-bottom))] lg:pb-0">
    <PublicHeader />
    <div className="mx-auto grid min-w-0 max-w-7xl gap-5 px-3 py-4 sm:gap-7 sm:px-6 sm:py-6 lg:grid-cols-[240px_minmax(0,1fr)] lg:py-8">
      <aside className="hidden h-fit min-w-0 rounded-card border border-slate-200 bg-white p-3 shadow-sm lg:sticky lg:top-20 lg:block">
        <div className="mb-3 flex min-w-0 items-center gap-3 border-b border-slate-100 p-2 pb-4">
          {user?.avatar_url ? <img src={user.avatar_url} alt="" className="h-10 w-10 shrink-0 rounded-full object-cover" /> : <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand-100 font-bold text-brand-700">{avatar}</div>}
          <div className="min-w-0"><b className="block truncate text-sm">{user?.full_name}</b><span className="block truncate text-xs text-slate-500">{user?.email}</span></div>
        </div>
        <nav className="grid gap-1">{items.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50'}`}><Icon size={18} className="shrink-0" />{label}</NavLink>)}</nav>
      </aside>
      <main className="min-w-0 max-w-full"><Outlet /></main>
    </div>
    <nav aria-label="Điều hướng tài khoản" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-8 border-t border-slate-200 bg-white/95 px-0.5 pt-1 shadow-lg backdrop-blur lg:hidden" style={{ paddingBottom: 'max(0.25rem, env(safe-area-inset-bottom))' }}>
      {items.map(({ to, short, icon: Icon }) => <NavLink key={to} to={to} title={short} className={({ isActive }) => `flex min-w-0 flex-col items-center gap-0.5 rounded-lg px-0.5 py-1.5 text-[9px] font-semibold ${isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-500'}`}><Icon size={18} className="shrink-0" /><span className="block w-full truncate text-center">{short}</span></NavLink>)}
    </nav>
  </div>;
}
