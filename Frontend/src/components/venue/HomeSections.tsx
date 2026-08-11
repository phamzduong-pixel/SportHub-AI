import { ArrowRight, Bot, CalendarCheck2, Check, MapPin, Search, Sparkles, Store, WalletCards } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Button, EmptyState, LoadingSkeleton } from '@/components/common';
import { listVenues } from '@/services/venueService';
import type { Venue } from '@/types';
import { VenueCard } from './VenueCard';

const sportCategories = [
  { name: 'Bóng đá', icon: '⚽' }, { name: 'Cầu lông', icon: '🏸' },
  { name: 'Pickleball', icon: '🏓' }, { name: 'Tennis', icon: '🎾' },
  { name: 'Bóng rổ', icon: '🏀' }, { name: 'Bóng chuyền', icon: '🏐' },
];

function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description?: string }) {
  return <div><p className="text-sm font-bold uppercase tracking-wider text-brand-700">{eyebrow}</p><h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">{title}</h2>{description && <p className="mt-2 text-sm text-slate-500">{description}</p>}</div>;
}

export function SportCategories() {
  return <section id="sports" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-16 sm:px-6"><div className="text-center"><SectionHeading eyebrow="Chơi môn bạn yêu thích" title="Khám phá theo môn thể thao" /></div><div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">{sportCategories.map((item) => <Link key={item.name} to={`/venues?sport=${encodeURIComponent(item.name)}`} className="group rounded-card border border-slate-200 bg-white p-5 text-center shadow-sm transition hover:-translate-y-1 hover:border-brand-300 hover:shadow-card"><span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-brand-50 text-2xl group-hover:bg-brand-100">{item.icon}</span><h3 className="mt-3 text-sm font-bold text-slate-900">{item.name}</h3></Link>)}</div></section>;
}

export function FeaturedVenues() {
  const { venues, loading } = useLiveVenues();
  const featured = [...venues].sort((a, b) => b.rating - a.rating || b.reviewCount - a.reviewCount).slice(0, 3);
  return <section id="offers" className="scroll-mt-20 bg-white py-16"><div className="mx-auto max-w-7xl px-4 sm:px-6"><div className="flex items-end justify-between gap-4"><SectionHeading eyebrow="Được yêu thích" title="Sân nổi bật tuần này" description="Những địa điểm có chất lượng dịch vụ và đánh giá tốt nhất." /><Link to="/venues" className="hidden items-center gap-1 text-sm font-bold text-brand-700 sm:flex">Xem tất cả <ArrowRight size={16} /></Link></div>{loading ? <LoadingSkeleton lines={6} /> : featured.length ? <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">{featured.map((venue) => <VenueCard key={venue.id} venue={venue} />)}</div> : <EmptyState title="Chưa có sân nổi bật" description="Dữ liệu sẽ xuất hiện khi OWNER tạo sân và lịch hoạt động." />}</div></section>;
}

export function NearbyVenues() {
  const { venues, loading } = useLiveVenues();
  const nearby = [...venues].filter((venue) => venue.available).sort((a, b) => a.distance - b.distance).slice(0, 3);
  return <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6"><div className="flex items-center justify-between gap-4"><div><p className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wider text-sportblue-600"><MapPin size={16} />Gần vị trí của bạn</p><h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">Sân gần bạn</h2></div><Link to="/venues?sort=distance"><Button variant="outline">Xem trên bản đồ</Button></Link></div>{loading ? <LoadingSkeleton lines={6} /> : nearby.length ? <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">{nearby.map((venue) => <VenueCard key={venue.id} venue={venue} />)}</div> : <EmptyState title="Chưa có sân khả dụng" description="Hãy quay lại sau khi chủ sân cập nhật lịch hoạt động." />}</section>;
}

function useLiveVenues() {
  const [venues, setVenues] = useState<Venue[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { listVenues().then(setVenues).catch(() => setVenues([])).finally(() => setLoading(false)); }, []);
  return { venues, loading };
}

const steps = [
  { icon: Search, title: 'Tìm sân', text: 'Chọn địa điểm, môn thể thao và thời gian phù hợp.' },
  { icon: CalendarCheck2, title: 'Chọn lịch', text: 'Xem lịch trống và chọn đúng sân bạn muốn chơi.' },
  { icon: WalletCards, title: 'Xác nhận', text: 'Kiểm tra chi phí, thông tin và hoàn tất đặt sân.' },
  { icon: Check, title: 'Đến chơi', text: 'Nhận xác nhận tức thì và sẵn sàng cho trận đấu.' },
];
export function BookingSteps() {
  return <section className="border-y border-slate-200 bg-white py-16"><div className="mx-auto max-w-7xl px-4 sm:px-6"><div className="text-center"><SectionHeading eyebrow="Nhanh chóng và minh bạch" title="Đặt sân chỉ với bốn bước" /></div><div className="mt-10 grid gap-8 md:grid-cols-4">{steps.map(({ icon: Icon, title, text }, index) => <div key={title} className="relative text-center"><div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-brand-600 text-white shadow-lg shadow-brand-600/20"><Icon size={23} /></div><span className="absolute left-1/2 top-0 ml-7 rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-extrabold text-brand-700">0{index + 1}</span><h3 className="mt-4 font-bold text-slate-900">{title}</h3><p className="mx-auto mt-2 max-w-[230px] text-sm leading-6 text-slate-500">{text}</p></div>)}</div></div></section>;
}

export function AIRecommendation() {
  return <section id="ai" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-16 sm:px-6"><div className="grid items-center gap-10 overflow-hidden rounded-2xl border border-ai-500/20 bg-ai-50 px-6 py-10 sm:px-10 lg:grid-cols-[1fr_.75fr]"><div><span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-bold text-ai-600 shadow-sm"><Sparkles size={14} />SportHub AI Assistant</span><h2 className="mt-4 max-w-xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Chưa biết nên chọn sân nào?</h2><p className="mt-4 max-w-xl leading-7 text-slate-600">Cho trợ lý AI biết môn chơi, khu vực, ngân sách và quy mô nhóm. Bạn sẽ nhận được gợi ý phù hợp chỉ trong vài giây.</p><div className="mt-6 flex flex-wrap gap-3"><Link to="/venues?sort=rating"><Button variant="ai" size="lg" leftIcon={<Bot size={19} />}>Khám phá trợ lý AI</Button></Link><Link to="/venues"><Button variant="outline" size="lg">Tự tìm sân</Button></Link></div></div><div className="rounded-card border border-ai-500/20 bg-white p-5 shadow-float"><div className="flex gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-ai-50 text-ai-600"><Bot size={19} /></span><div><b className="text-sm">Gợi ý dành cho bạn</b><p className="mt-1 text-sm leading-6 text-slate-500">Nhóm 8 người, chơi bóng đá tối thứ Sáu, cách Quận 3 dưới 5 km.</p></div></div><div className="mt-4 rounded-lg bg-brand-50 p-4"><b className="text-sm text-brand-900">SportHub Phú Thọ</b><p className="mt-1 text-xs text-brand-700">Phù hợp 96% • Còn sân lúc 20:00 • 450.000đ/giờ</p></div></div></div></section>;
}

export function OwnerSolution() {
  return <section id="owners" className="scroll-mt-20 bg-brand-900 py-16 text-white"><div className="mx-auto grid max-w-7xl items-center gap-10 px-4 sm:px-6 lg:grid-cols-2"><div><span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold text-brand-100"><Store size={15} />Giải pháp cho chủ sân</span><h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">Quản lý sân thông minh, tăng hiệu quả vận hành</h2><p className="mt-4 max-w-xl leading-7 text-brand-100/80">Quản lý lịch đặt, khách hàng, thanh toán và doanh thu trên một màn hình. AI hỗ trợ dự báo nhu cầu để tối ưu giá và công suất sân.</p><Link to="/quan-ly"><Button variant="outline" size="lg" className="mt-6 !border-white !bg-white !text-brand-900 hover:!border-brand-100 hover:!bg-brand-50 hover:!text-brand-900">Khám phá giải pháp <ArrowRight size={18} /></Button></Link></div><div className="grid gap-3 sm:grid-cols-2">{['Lịch đặt tập trung', 'Báo cáo doanh thu', 'Quản lý nhiều cơ sở', 'Dự báo nhu cầu AI'].map((item) => <div key={item} className="flex items-center gap-3 rounded-card border border-white/10 bg-white/5 p-4"><span className="grid h-8 w-8 place-items-center rounded-full bg-brand-500/20 text-brand-100"><Check size={17} /></span><span className="text-sm font-semibold">{item}</span></div>)}</div></div></section>;
}
