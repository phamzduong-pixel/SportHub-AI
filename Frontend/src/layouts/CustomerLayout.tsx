import { Bell, CalendarDays, Heart, LayoutDashboard, MoreHorizontal, ReceiptText, Settings, Star, Store, UserRound, MessageSquareWarning } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Drawer } from '@/components/common';
import { PublicHeader } from '@/components/layout/PublicHeader';
import { useAuth } from '@/contexts/AuthContext';

const primaryItems = [
  { to: '/customer/dashboard', label: 'Tổng quan', icon: LayoutDashboard },
  { to: '/customer/bookings', label: 'Lịch đặt', icon: CalendarDays },
  { to: '/customer/transactions', label: 'Giao dịch', icon: ReceiptText },
  { to: '/customer/profile', label: 'Hồ sơ', icon: UserRound },
];

const allItems = [
  { to: '/customer/dashboard', label: 'Tổng quan', icon: LayoutDashboard },
  { to: '/customer/bookings', label: 'Lịch đặt của tôi', icon: CalendarDays },
  { to: '/customer/favorites', label: 'Sân yêu thích', icon: Heart },
  { to: '/customer/reviews', label: 'Đánh giá sân', icon: Star },
  { to: '/customer/complaints', label: 'Khiếu nại của tôi', icon: MessageSquareWarning },
  { to: '/customer/transactions', label: 'Giao dịch', icon: ReceiptText },
  { to: '/customer/notifications', label: 'Thông báo', icon: Bell },
  { to: '/customer/profile', label: 'Hồ sơ cá nhân', icon: UserRound },
  { to: '/customer/settings', label: 'Cài đặt', icon: Settings },
  { to: '/owner-application', label: 'Trở thành đối tác', icon: Store },
];

export function CustomerLayout() {
  const { user } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);
  const avatar = user?.full_name.split(/\s+/).slice(-2).map((part) => part[0]).join('').toUpperCase();

  return (
    <div className="app-canvas min-h-screen min-w-0 overflow-x-clip pb-[calc(4.5rem+env(safe-area-inset-bottom))] lg:pb-0">
      <PublicHeader />
      <div className="mx-auto grid min-w-0 max-w-7xl gap-5 px-3 py-4 sm:gap-7 sm:px-6 sm:py-6 lg:grid-cols-[240px_minmax(0,1fr)] lg:py-8">
        <aside className="hidden h-fit min-w-0 rounded-card border border-slate-200 bg-white p-3 shadow-sm lg:sticky lg:top-20 lg:block">
          <div className="mb-3 flex min-w-0 items-center gap-3 border-b border-slate-100 p-2 pb-4">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="" className="h-10 w-10 shrink-0 rounded-full object-cover" />
            ) : (
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand-100 font-bold text-brand-700">{avatar}</div>
            )}
            <div className="min-w-0">
              <b className="block truncate text-sm">{user?.full_name}</b>
              <span className="block truncate text-xs text-slate-500">{user?.email}</span>
            </div>
          </div>
          <nav className="grid gap-1">
            {allItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                    isActive ? 'bg-brand-50 text-brand-700 font-semibold' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`
                }
              >
                <Icon size={18} className="shrink-0" />
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 max-w-full"><Outlet /></main>
      </div>

      {/* Mobile Bottom Navigation Bar */}
      <nav
        aria-label="Điều hướng tài khoản"
        className="mobile-bottom-nav fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-slate-200 bg-white/95 px-1 pt-1.5 shadow-float backdrop-blur lg:hidden"
        style={{ paddingBottom: 'max(0.35rem, env(safe-area-inset-bottom))' }}
      >
        {primaryItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={label}
            className={({ isActive }) =>
              `flex min-h-[44px] min-w-0 flex-col items-center justify-center gap-1 rounded-xl px-1 py-1 text-[11px] font-medium transition ${
                isActive ? 'bg-brand-50/80 font-bold text-brand-700' : 'text-slate-500 hover:text-slate-900'
              }`
            }
          >
            <Icon size={19} className="shrink-0" />
            <span className="block w-full truncate text-center">{label}</span>
          </NavLink>
        ))}
        <button
          type="button"
          onClick={() => setMoreOpen(true)}
          className="flex min-h-[44px] min-w-0 flex-col items-center justify-center gap-1 rounded-xl px-1 py-1 text-[11px] font-medium text-slate-500 hover:text-slate-900"
          aria-label="Tất cả mục menu"
        >
          <MoreHorizontal size={19} className="shrink-0" />
          <span className="block w-full truncate text-center">Thêm</span>
        </button>
      </nav>

      <Drawer open={moreOpen} onClose={() => setMoreOpen(false)} title="Menu tài khoản">
        <nav className="grid gap-1">
          {allItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMoreOpen(false)}
              className={({ isActive }) =>
                `flex min-h-[44px] items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition ${
                  isActive ? 'bg-brand-50 font-bold text-brand-700' : 'text-slate-700 hover:bg-slate-50'
                }`
              }
            >
              <Icon size={19} className="shrink-0 text-brand-600" />
              {label}
            </NavLink>
          ))}
        </nav>
      </Drawer>
    </div>
  );
}

