import { BarChart3, Building2, CalendarCheck2, LogOut, Search, ShieldCheck, UserCog, Users } from 'lucide-react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Badge, Button, EmptyState, Input, LoadingSkeleton, useToast } from '@/components/common';
import { useAuth } from '@/contexts/AuthContext';
import { apiRequest } from '@/services/apiClient';
import type { AccountRole, AuthUser } from '@/types/auth';

type Tab = 'overview' | 'users' | 'owners' | 'statistics';
interface AdminSummary { total_users: number; customers: number; owners: number; system_admins: number; active_users: number; facilities: number; active_facilities: number; fields: number; bookings: number; pending_applications: number; pending_facilities: number; }
interface AdminOwner { id: number; full_name: string; email: string; phone: string | null; avatar_url: string | null; is_active: boolean; approved_at: string | null; facility_count: number; field_count: number; }
interface PendingApplication { id: number; customer_name: string; customer_email: string; submitted_at: string | null; venue: Record<string, unknown>; }

const roleLabel: Record<AccountRole, string> = { CUSTOMER: 'Khách hàng', OWNER: 'Chủ sân', SYSTEM_ADMIN: 'Quản trị hệ thống' };
const tabs: Array<{ id: Tab; label: string; icon: typeof Users }> = [
  { id: 'overview', label: 'Tổng quan', icon: BarChart3 }, { id: 'users', label: 'Người dùng', icon: Users },
  { id: 'owners', label: 'Chủ sân / Đối tác', icon: Building2 }, { id: 'statistics', label: 'Thống kê hệ thống', icon: CalendarCheck2 },
];

export function SystemAdminPage() {
  const { user, logout } = useAuth(); const navigate = useNavigate(); const { toast } = useToast();
  const [tab, setTab] = useState<Tab>('overview'); const [summary, setSummary] = useState<AdminSummary>();
  const [users, setUsers] = useState<AuthUser[]>([]); const [owners, setOwners] = useState<AdminOwner[]>([]);
  const [pending, setPending] = useState<PendingApplication[]>([]); const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState(''); const [role, setRole] = useState(''); const [active, setActive] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const [overview, userResult, ownerResult, applications] = await Promise.all([
        apiRequest<AdminSummary>('/admin/summary'), apiRequest<{ items: AuthUser[] }>('/admin/users?page_size=100'),
        apiRequest<{ items: AdminOwner[] }>('/admin/owners?page_size=100'), apiRequest<PendingApplication[]>('/admin/owner-applications?status=PENDING'),
      ]);
      setSummary(overview); setUsers(userResult.items); setOwners(ownerResult.items); setPending(applications);
    } catch (error) { toast(error instanceof Error ? error.message : 'Không tải được dữ liệu quản trị.', 'error'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const visibleUsers = useMemo(() => users.filter((item) => {
    const matchesQuery = `${item.full_name} ${item.email} ${item.phone || ''}`.toLocaleLowerCase('vi').includes(query.trim().toLocaleLowerCase('vi'));
    return matchesQuery && (!role || item.role === role) && (!active || item.is_active === (active === 'active'));
  }), [users, query, role, active]);
  const setUserStatus = async (item: AuthUser) => {
    try {
      const updated = await apiRequest<AuthUser>(`/admin/users/${item.id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active: !item.is_active }) });
      setUsers((current) => current.map((value) => value.id === updated.id ? updated : value));
      setOwners((current) => current.map((value) => value.id === updated.id ? { ...value, is_active: updated.is_active } : value));
      toast(updated.is_active ? 'Đã mở khóa tài khoản.' : 'Đã khóa tài khoản.', 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không thể cập nhật tài khoản.', 'error'); }
  };
  const signOut = () => { logout(); navigate('/login', { replace: true }); };
  if (loading) return <div className="mx-auto max-w-7xl p-6"><LoadingSkeleton lines={10} /></div>;

  return <div className="min-h-screen bg-slate-50"><header className="border-b bg-slate-950 text-white"><div className="mx-auto flex min-h-16 max-w-7xl items-center gap-3 px-4 py-2 sm:px-6"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-500/15 text-emerald-400"><ShieldCheck size={22} /></span><div className="min-w-0"><b className="block truncate">Quản trị SportHub</b><p className="truncate text-xs text-slate-400">{user?.full_name} · Quản trị nền tảng</p></div><Button variant="ghost" className="ml-auto !text-white" leftIcon={<LogOut size={16} />} onClick={signOut}><span className="hidden sm:inline">Đăng xuất</span></Button></div></header>
    <div className="border-b bg-white"><nav className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-3 py-2 sm:px-6" aria-label="Khu vực quản trị">{tabs.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => setTab(id)} className={`inline-flex min-h-10 shrink-0 items-center gap-2 rounded-xl px-3 text-sm font-semibold transition ${tab === id ? 'bg-brand-50 text-brand-700' : 'text-slate-500 hover:bg-slate-50'}`}><Icon size={17} />{label}</button>)}<Link to="/system-admin/partner-applications" className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-slate-500 hover:bg-slate-50 hover:text-brand-700"><UserCog size={17} />Hồ sơ đối tác{pending.length > 0 && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">{pending.length}</span>}</Link><Link to="/system-admin/facility-applications" className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-slate-500 hover:bg-slate-50 hover:text-brand-700"><Building2 size={17} />Duyệt cơ sở</Link></nav></div>

    <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      {tab === 'overview' && <><SectionHeading title="Tổng quan hệ thống" description="Dữ liệu vận hành thật trên toàn nền tảng SportHub." /><MetricGrid summary={summary} />
        <section className="overflow-hidden rounded-2xl border bg-white shadow-sm"><div className="flex flex-col gap-3 border-b p-5 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="font-bold text-slate-900">Hồ sơ cần xử lý</h2><p className="mt-1 text-sm text-slate-500">Các hồ sơ đang chờ SYSTEM_ADMIN xét duyệt.</p></div><Link to="/system-admin/partner-applications"><Button variant="outline">Xem tất cả hồ sơ</Button></Link></div>{pending.length ? <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">{pending.slice(0, 6).map((item) => <article key={item.id} className="rounded-xl border border-slate-200 p-4"><div className="flex items-start justify-between gap-2"><div className="min-w-0"><b className="block truncate">{item.customer_name}</b><p className="truncate text-sm text-slate-500">{item.customer_email}</p></div><Badge variant="warning">Chờ duyệt</Badge></div><p className="mt-3 truncate text-sm font-medium text-slate-700">{String(item.venue.name || 'Chưa nhập tên cơ sở')}</p><p className="mt-1 text-xs text-slate-400">{item.submitted_at ? new Date(item.submitted_at).toLocaleString('vi-VN') : 'Chưa có ngày gửi'}</p><Link to="/system-admin/partner-applications"><Button className="mt-4 w-full" size="sm" variant="outline">Mở hồ sơ</Button></Link></article>)}</div> : <EmptyState title="Không có hồ sơ chờ duyệt" description="Tất cả hồ sơ đối tác đã được xử lý." />}</section>
      </>}

      {tab === 'users' && <><SectionHeading title="Quản lý người dùng" description="Tìm kiếm, lọc và khóa hoặc mở khóa tài khoản ở cấp nền tảng." /><section className="rounded-2xl border bg-white p-4 shadow-sm"><div className="grid gap-3 md:grid-cols-[2fr_1fr_1fr]"><Input leftIcon={<Search size={17} />} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tên, email hoặc số điện thoại" /><select className="h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm" value={role} onChange={(event) => setRole(event.target.value)}><option value="">Mọi vai trò</option>{Object.entries(roleLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><select className="h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm" value={active} onChange={(event) => setActive(event.target.value)}><option value="">Mọi trạng thái</option><option value="active">Hoạt động</option><option value="locked">Đã khóa</option></select></div></section><UserTable items={visibleUsers} currentUserId={user?.id} onStatus={setUserStatus} /></>}

      {tab === 'owners' && <><SectionHeading title="Chủ sân / Đối tác" description="Theo dõi OWNER đã được duyệt, quy mô cơ sở và trạng thái tài khoản." /><OwnerTable items={owners} onStatus={(owner) => { const account = users.find((item) => item.id === owner.id); if (account) void setUserStatus(account); }} /></>}

      {tab === 'statistics' && <><SectionHeading title="Thống kê hệ thống" description="Các chỉ số tổng hợp cấp nền tảng; SYSTEM_ADMIN không can thiệp vận hành hàng ngày của OWNER." /><MetricGrid summary={summary} />{summary && <section className="grid gap-4 lg:grid-cols-2"><StatPanel title="Cơ cấu tài khoản" rows={[['CUSTOMER', summary.customers], ['OWNER', summary.owners], ['SYSTEM_ADMIN', summary.system_admins]]} /><StatPanel title="Nguồn lực nền tảng" rows={[['Cơ sở', summary.facilities], ['Cơ sở hoạt động', summary.active_facilities], ['Sân', summary.fields], ['Booking', summary.bookings]]} /></section>}</>}
    </main>
  </div>;
}

function SectionHeading({ title, description }: { title: string; description: string }) { return <div><h1 className="text-2xl font-black tracking-tight text-slate-900">{title}</h1><p className="mt-1 text-sm text-slate-500">{description}</p></div>; }
function MetricGrid({ summary }: { summary?: AdminSummary }) { if (!summary) return null; return <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-7"><Metric icon={<Users />} label="Tổng người dùng" value={summary.total_users} /><Metric icon={<Users />} label="CUSTOMER" value={summary.customers} /><Metric icon={<Building2 />} label="OWNER" value={summary.owners} /><Metric icon={<Building2 />} label="Cơ sở / Sân" value={`${summary.facilities} / ${summary.fields}`} /><Metric icon={<UserCog />} label="Đối tác chờ duyệt" value={summary.pending_applications} /><Metric icon={<Building2 />} label="Cơ sở chờ duyệt" value={summary.pending_facilities} /><Metric icon={<CalendarCheck2 />} label="Booking" value={summary.bookings} /></section>; }
function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: number | string }) { return <article className="rounded-2xl border bg-white p-4 shadow-sm"><span className="text-brand-600 [&>svg]:h-5 [&>svg]:w-5">{icon}</span><p className="mt-3 text-[11px] font-bold uppercase tracking-wide text-slate-500">{label}</p><strong className="mt-1 block text-2xl text-slate-900">{value}</strong></article>; }
function UserTable({ items, currentUserId, onStatus }: { items: AuthUser[]; currentUserId?: number; onStatus: (item: AuthUser) => void }) { return <section className="overflow-hidden rounded-2xl border bg-white shadow-sm">{items.length ? <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr>{['Người dùng', 'Vai trò', 'Ngày tạo', 'Trạng thái', ''].map((label) => <th key={label} className="px-5 py-3">{label}</th>)}</tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-t"><td className="px-5 py-3"><div className="flex items-center gap-3">{item.avatar_url ? <img src={item.avatar_url} alt="" className="h-9 w-9 rounded-full object-cover" /> : <span className="grid h-9 w-9 place-items-center rounded-full bg-brand-50 text-xs font-bold text-brand-700">{item.full_name.slice(0, 1)}</span>}<div><b>{item.full_name}</b><small className="block text-slate-500">{item.email}</small></div></div></td><td className="px-5 py-3"><Badge>{roleLabel[item.role]}</Badge></td><td className="px-5 py-3 text-slate-500">{new Date(item.created_at).toLocaleDateString('vi-VN')}</td><td className="px-5 py-3"><Badge variant={item.is_active ? 'success' : 'danger'}>{item.is_active ? 'Hoạt động' : 'Đã khóa'}</Badge></td><td className="px-5 py-3 text-right"><Button size="sm" variant={item.is_active ? 'danger' : 'outline'} disabled={item.id === currentUserId} onClick={() => onStatus(item)}>{item.is_active ? 'Khóa' : 'Mở khóa'}</Button></td></tr>)}</tbody></table></div> : <EmptyState title="Không có người dùng phù hợp" description="Hãy thay đổi bộ lọc tìm kiếm." />}</section>; }
function OwnerTable({ items, onStatus }: { items: AdminOwner[]; onStatus: (item: AdminOwner) => void }) { return <section className="overflow-hidden rounded-2xl border bg-white shadow-sm">{items.length ? <div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left text-sm"><thead className="bg-slate-50"><tr>{['Đối tác', 'Ngày duyệt', 'Cơ sở', 'Sân', 'Trạng thái', ''].map((label) => <th key={label} className="px-5 py-3">{label}</th>)}</tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-t"><td className="px-5 py-3"><b>{item.full_name}</b><small className="block text-slate-500">{item.email}</small></td><td className="px-5 py-3 text-slate-500">{item.approved_at ? new Date(item.approved_at).toLocaleDateString('vi-VN') : 'Tài khoản OWNER khởi tạo'}</td><td className="px-5 py-3 font-semibold">{item.facility_count}</td><td className="px-5 py-3 font-semibold">{item.field_count}</td><td className="px-5 py-3"><Badge variant={item.is_active ? 'success' : 'danger'}>{item.is_active ? 'Hoạt động' : 'Đã khóa'}</Badge></td><td className="px-5 py-3 text-right"><Button size="sm" variant={item.is_active ? 'danger' : 'outline'} onClick={() => onStatus(item)}>{item.is_active ? 'Khóa' : 'Mở khóa'}</Button></td></tr>)}</tbody></table></div> : <EmptyState title="Chưa có OWNER" description="OWNER xuất hiện sau khi hồ sơ đối tác được duyệt." />}</section>; }
function StatPanel({ title, rows }: { title: string; rows: [string, number][] }) { const total = rows.reduce((sum, [, value]) => sum + value, 0); return <section className="rounded-2xl border bg-white p-5 shadow-sm"><h2 className="font-bold text-slate-900">{title}</h2><div className="mt-5 space-y-4">{rows.map(([label, value]) => <div key={label}><div className="mb-1 flex justify-between text-sm"><span className="text-slate-600">{label}</span><b>{value}</b></div><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-500" style={{ width: `${total ? Math.max(4, value / total * 100) : 0}%` }} /></div></div>)}</div></section>; }
