import { CalendarDays, Search, Users } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { Badge, Button, EmptyState, Input, LoadingSkeleton, Modal, PageHeader, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';

interface CustomerSummary {
  id: number; full_name: string; email: string; phone: string | null; booking_count: number;
  completed_booking_count: number; active_booking_count: number; cancelled_booking_count: number;
  valid_transaction_value: number; last_booking_at: string; created_at: string;
}
interface CustomerBooking {
  id: number; booking_code: string; facility_name: string; field_name: string; booking_date: string;
  start_time: string; end_time: string; status: string; total_amount: number; deposit_amount: number;
  paid_amount: number; payment_status: string;
}
interface CustomerDetail extends CustomerSummary { bookings: CustomerBooking[]; }
interface CustomerList { items: CustomerSummary[]; total: number; page: number; page_size: number; pages: number; }

const money = (value: number) => `${Number(value || 0).toLocaleString('vi-VN')}đ`;
const dateTime = (value: string) => new Date(value).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
const statusLabels: Record<string, string> = { pending_payment: 'Chờ thanh toán', pending_confirmation: 'Chờ xác nhận', confirmed: 'Đã xác nhận', in_progress: 'Đang sử dụng', completed: 'Hoàn thành', cancelled_by_customer: 'Khách hủy', cancelled_by_owner: 'Chủ sân hủy', expired: 'Hết hạn', rejected: 'Từ chối', failed: 'Thất bại' };

export function ManagementCustomersPage() {
  const { toast } = useToast();
  const [data, setData] = useState<CustomerList>(); const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<CustomerDetail>(); const [detailLoading, setDetailLoading] = useState(false);
  const [search, setSearch] = useState(''); const [appliedSearch, setAppliedSearch] = useState('');
  const [hasActive, setHasActive] = useState(false); const [hasCompleted, setHasCompleted] = useState(false); const [hasCancelled, setHasCancelled] = useState(false);
  const [dateFrom, setDateFrom] = useState(''); const [dateTo, setDateTo] = useState('');
  const [sortBy, setSortBy] = useState('last_booking'); const [page, setPage] = useState(1);

  const load = async () => {
    setLoading(true);
    const query = new URLSearchParams({ page: String(page), page_size: '20', sort_by: sortBy, sort_order: 'desc' });
    if (appliedSearch) query.set('search', appliedSearch);
    if (hasActive) query.set('has_active', 'true'); if (hasCompleted) query.set('has_completed', 'true'); if (hasCancelled) query.set('has_cancelled', 'true');
    if (dateFrom) query.set('last_booking_from', dateFrom); if (dateTo) query.set('last_booking_to', dateTo);
    try { setData(await apiRequest<CustomerList>(`/management/customers?${query}`)); }
    catch (error) { toast(error instanceof Error ? error.message : 'Không tải được khách hàng.', 'error'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [appliedSearch, hasActive, hasCompleted, hasCancelled, dateFrom, dateTo, sortBy, page]);
  const submitSearch = (event: FormEvent) => { event.preventDefault(); setPage(1); setAppliedSearch(search.trim()); };
  const openDetail = async (customer: CustomerSummary) => { setDetailLoading(true); try { setDetail(await apiRequest<CustomerDetail>(`/management/customers/${customer.id}`)); } catch (error) { toast(error instanceof Error ? error.message : 'Không tải được lịch sử khách hàng.', 'error'); } finally { setDetailLoading(false); } };

  return <><PageHeader title="Khách hàng" description="Chỉ hiển thị khách đã đặt sân thuộc các cơ sở của OWNER hiện tại; dữ liệu lấy trực tiếp từ API." />
    <section className="mb-5 rounded-card border bg-white p-4"><form onSubmit={submitSearch} className="flex flex-col gap-3 lg:flex-row"><Input className="flex-1" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Tên, email hoặc số điện thoại" leftIcon={<Search size={16} />} /><Button type="submit">Tìm kiếm</Button><select className="field lg:max-w-56" value={sortBy} onChange={(event) => { setPage(1); setSortBy(event.target.value); }}><option value="last_booking">Đặt gần nhất</option><option value="booking_count">Số booking</option><option value="transaction_value">Giá trị giao dịch</option></select></form>
      <div className="mt-3 flex flex-wrap gap-4 text-sm"><Filter checked={hasActive} onChange={(value) => { setPage(1); setHasActive(value); }} label="Có booking hoạt động" /><Filter checked={hasCompleted} onChange={(value) => { setPage(1); setHasCompleted(value); }} label="Đã từng hoàn thành" /><Filter checked={hasCancelled} onChange={(value) => { setPage(1); setHasCancelled(value); }} label="Có booking hủy" /></div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:max-w-2xl"><Input label="Đặt gần nhất từ" type="date" value={dateFrom} onChange={(event) => { setPage(1); setDateFrom(event.target.value); }} /><Input label="Đến" type="date" value={dateTo} onChange={(event) => { setPage(1); setDateTo(event.target.value); }} /></div>
    </section>
    {loading ? <LoadingSkeleton lines={8} /> : data?.items.length ? <><div className="overflow-x-auto rounded-card border bg-white"><table className="w-full min-w-[1150px] text-left text-sm"><thead className="bg-slate-50"><tr>{['Khách hàng', 'Liên hệ', 'Booking', 'Hoàn thành', 'Hoạt động', 'Đã hủy', 'Giao dịch hợp lệ', 'Đặt gần nhất', 'Tạo tài khoản'].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{data.items.map((customer) => <tr key={customer.id} className="cursor-pointer border-t hover:bg-slate-50" onClick={() => void openDetail(customer)}><td className="px-4 py-3 font-semibold text-brand-700">{customer.full_name}</td><td className="px-4 py-3"><span className="block">{customer.email}</span><small className="text-slate-500">{customer.phone || 'Chưa có SĐT'}</small></td><td className="px-4 py-3">{customer.booking_count}</td><td className="px-4 py-3">{customer.completed_booking_count}</td><td className="px-4 py-3">{customer.active_booking_count}</td><td className="px-4 py-3">{customer.cancelled_booking_count}</td><td className="px-4 py-3 font-semibold">{money(customer.valid_transaction_value)}</td><td className="px-4 py-3">{dateTime(customer.last_booking_at)}</td><td className="px-4 py-3">{new Date(customer.created_at).toLocaleDateString('vi-VN')}</td></tr>)}</tbody></table></div><div className="mt-4 flex items-center justify-between text-sm"><span>{data.total} khách hàng</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Trước</Button><span className="px-2 py-2">{page}/{data.pages}</span><Button size="sm" variant="outline" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Sau</Button></div></div></> : <EmptyState icon={<Users />} title="Không có khách hàng phù hợp" description="Thử bỏ bớt bộ lọc hoặc chờ khi cơ sở có booking." />}
    <Modal open={Boolean(detail) || detailLoading} onClose={() => setDetail(undefined)} title={detail ? `Khách hàng · ${detail.full_name}` : 'Đang tải khách hàng'}>{detailLoading ? <LoadingSkeleton lines={6} /> : detail && <div><div className="grid gap-3 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-2"><p><b>Email:</b> {detail.email}</p><p><b>Số điện thoại:</b> {detail.phone || 'Chưa có'}</p><p><b>Tổng booking:</b> {detail.booking_count}</p><p><b>Giao dịch hợp lệ:</b> {money(detail.valid_transaction_value)}</p></div><h3 className="mt-5 flex items-center gap-2 font-bold"><CalendarDays size={17} />Lịch sử tại cơ sở của bạn</h3><div className="mt-3 max-h-[55vh] space-y-3 overflow-y-auto">{detail.bookings.map((booking) => <article key={booking.id} className="rounded-xl border p-4 text-sm"><div className="flex flex-wrap justify-between gap-2"><b className="text-brand-700">{booking.booking_code} · {booking.field_name}</b><Badge>{statusLabels[booking.status] || booking.status}</Badge></div><p className="mt-1 text-slate-600">{booking.facility_name} · {new Date(`${booking.booking_date}T00:00`).toLocaleDateString('vi-VN')} · {booking.start_time.slice(0, 5)}–{booking.end_time.slice(0, 5)}</p><div className="mt-2 grid grid-cols-3 gap-2 text-xs"><span>Tổng: <b>{money(booking.total_amount)}</b></span><span>Cọc: <b>{money(booking.deposit_amount)}</b></span><span>Payment: <b>{booking.payment_status}</b></span></div></article>)}</div></div>}</Modal>
  </>;
}

function Filter({ checked, onChange, label }: { checked: boolean; onChange: (value: boolean) => void; label: string }) {
  return <label className="flex cursor-pointer items-center gap-2"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />{label}</label>;
}
