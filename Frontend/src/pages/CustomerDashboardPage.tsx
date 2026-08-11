import { ArrowRight, CalendarDays, Clock3, MapPin, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Button, LoadingSkeleton, PageHeader } from '@/components/common';
import { useAuth } from '@/contexts/AuthContext';
import { getMyBookings, type ApiBooking } from '@/services/customerApi';

export function CustomerDashboardPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ApiBooking[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { getMyBookings().then((result) => setItems(result.items)).finally(() => setLoading(false)); }, []);
  const upcoming = items.find((item) => ['pending_payment', 'pending_confirmation', 'confirmed'].includes(item.status));

  return <>
    <PageHeader title={`Xin chào, ${user?.full_name || ''}`} description="Theo dõi lịch đặt và hoạt động của đúng tài khoản bạn đang đăng nhập." action={<Link to="/venues"><Button>Đặt sân mới</Button></Link>} />
    <div className="grid gap-5 sm:grid-cols-3"><Metric label="Tổng booking" value={String(items.length)} /><Metric label="Sắp tới" value={String(items.filter((item) => ['pending_payment', 'pending_confirmation', 'confirmed'].includes(item.status)).length)} /><Metric label="Đã hoàn thành" value={String(items.filter((item) => item.status === 'completed').length)} /></div>
    <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]">
      <section className="rounded-card border bg-white">
        <div className="flex items-center justify-between border-b p-5"><h2 className="font-bold">Lịch đặt sân của tôi</h2><Link to="/customer/bookings" className="flex items-center gap-1 text-sm font-semibold text-brand-700">Xem tất cả <ArrowRight size={15} /></Link></div>
        {loading ? <div className="p-5"><LoadingSkeleton lines={4} /></div> : upcoming ? <div className="p-5"><div className="flex justify-between gap-3"><div><h3 className="font-bold">{upcoming.field_name}</h3><p className="text-sm text-brand-700">{upcoming.sport_type}</p></div><Badge variant="success">{upcoming.booking_code}</Badge></div><div className="mt-4 grid gap-2 text-sm text-slate-600 sm:grid-cols-2"><p><CalendarDays size={16} className="mr-2 inline text-brand-600" />{upcoming.booking_date}</p><p><Clock3 size={16} className="mr-2 inline text-brand-600" />{upcoming.start_time_snapshot.slice(0, 5)}–{upcoming.end_time_snapshot.slice(0, 5)}</p><p className="sm:col-span-2"><MapPin size={16} className="mr-2 inline text-brand-600" />{upcoming.location}</p></div><Link to={`/customer/bookings/${upcoming.id}`}><Button size="sm" className="mt-4">Xem chi tiết</Button></Link></div> : <p className="p-8 text-center text-sm text-slate-500">Bạn chưa có lịch chơi sắp tới.</p>}
      </section>
      <section className="rounded-card border border-teal-200 bg-ai-50 p-6 text-slate-800 shadow-sm"><span className="grid h-11 w-11 place-items-center rounded-xl bg-white text-ai-600 shadow-sm"><Sparkles size={23} /></span><h2 className="mt-4 text-xl font-bold">Gợi ý dành cho bạn</h2><p className="mt-2 text-sm leading-6 text-slate-600">Khám phá sân phù hợp dựa trên lịch sử booking của chính tài khoản này.</p><Link to="/"><Button variant="outline" className="mt-5">Xem gợi ý</Button></Link></section>
    </div>
  </>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-card border bg-white p-5"><p className="text-sm text-slate-500">{label}</p><b className="mt-2 block text-2xl text-slate-800">{value}</b></div>; }
