import { Bell, Building2, ChevronDown, Menu, Plus, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Dropdown, useToast } from '@/components/common';
import { useAuth } from '@/contexts/AuthContext';
import { PermissionGuard, usePermission } from '@/contexts/PermissionContext';
import { apiRequest } from '@/services/apiClient';

const names: Record<string, string> = { dashboard: 'Tổng quan', calendar: 'Lịch đặt sân', bookings: 'Danh sách booking', venues: 'Cơ sở', courts: 'Sân', schedules: 'Khung giờ', pricing: 'Bảng giá', customers: 'Khách hàng', payments: 'Thanh toán', complaints: 'Khiếu nại', reports: 'Báo cáo', 'ai-insights': 'Phân tích AI', settings: 'Cài đặt' };

export function ManagementHeader({ onMenu }: { onMenu: () => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = usePermission();
  const { logout } = useAuth();
  const part = location.pathname.split('/')[2] || 'dashboard';
  const [venues, setVenues] = useState<Array<{ id: number; name: string }>>([]);
  useEffect(() => { apiRequest<{ items: Array<{ id: number; name: string }> }>('/fields?page_size=100').then((response) => setVenues(response.items)).catch(() => setVenues([])); }, []);
  const signOut = () => { logout(); toast('Đã đăng xuất an toàn.', 'success'); navigate('/login', { replace: true }); };

  return <header className="sticky top-0 z-30 flex h-16 min-w-0 items-center gap-1.5 border-b border-slate-200 bg-white/95 px-2 backdrop-blur min-[375px]:gap-3 min-[375px]:px-3 sm:px-6">
    <button onClick={onMenu} className="grid h-10 w-10 shrink-0 place-items-center rounded-lg hover:bg-slate-100 lg:hidden" aria-label="Mở điều hướng"><Menu size={21} /></button>
    <div className="hidden min-w-0 sm:block"><p className="text-[11px] text-slate-400">Quản lý /</p><b className="block truncate text-sm text-slate-800">{names[part] ?? 'Chi tiết'}</b></div>
    <div className="relative ml-2 hidden max-w-xs flex-1 xl:block"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input aria-label="Tìm kiếm" placeholder="Tìm booking, khách hàng..." className="h-9 w-full rounded-lg bg-slate-100 pl-9 pr-3 text-sm outline-none" /></div>
    <div className="ml-auto flex min-w-0 items-center gap-0.5 min-[375px]:gap-1.5">
      <label className="hidden items-center gap-2 rounded-lg border border-slate-200 px-2.5 py-1.5 md:flex"><Building2 size={16} className="shrink-0 text-brand-700" /><select aria-label="Cơ sở đang quản lý" className="max-w-36 bg-transparent text-xs font-semibold outline-none">{venues.map((venue) => <option key={venue.id}>{venue.name}</option>)}</select></label>
      <PermissionGuard module="calendar" action="create"><Dropdown trigger={<span className="flex h-10 items-center gap-1.5 rounded-lg bg-brand-600 px-2.5 text-xs font-semibold text-white sm:h-9"><Plus size={17} /><span className="hidden sm:inline">Tạo nhanh</span></span>} items={[{ label: 'Tạo booking', onClick: () => navigate('/management/calendar') }, { label: 'Khóa khung giờ', onClick: () => navigate('/management/schedules') }]} /></PermissionGuard>
      <Dropdown trigger={<span className="relative grid h-10 w-10 place-items-center rounded-lg text-slate-600 hover:bg-slate-100 sm:h-9 sm:w-9"><Bell size={19} /></span>} items={[{ label: 'Xem danh sách booking', onClick: () => navigate('/management/bookings') }]} />
      <Dropdown trigger={<span className="flex min-w-0 items-center gap-1 rounded-lg p-1 hover:bg-slate-50 sm:gap-2 sm:p-1.5">{user.avatarUrl ? <img src={user.avatarUrl} alt="" className="h-8 w-8 shrink-0 rounded-full object-cover" /> : <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">{user.avatar}</span>}<span className="hidden min-w-0 text-left lg:block"><b className="block truncate text-xs text-slate-800">{user.name}</b><small className="text-[10px] text-slate-500">{user.role === 'OWNER' ? 'Chủ sân' : user.title}</small></span><ChevronDown size={14} className="hidden shrink-0 min-[375px]:block" /></span>} items={[{ label: 'Cài đặt tài khoản', onClick: () => navigate('/management/settings') }, { label: 'Đăng xuất', danger: true, onClick: signOut }]} />
    </div>
  </header>;
}

