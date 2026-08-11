import { ArrowRight, Clock3, MapPin, Sparkles, Star } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Button, EmptyState, LoadingSkeleton } from '@/components/common';
import { getCustomerRecommendations, type CustomerRecommendation, type RecommendationResponse } from '@/services/recommendationService';
import { getSportImage } from '@/utils/sportImage';

export function PersonalizedRecommendations() {
  const [data, setData] = useState<RecommendationResponse>();
  const [error, setError] = useState(false);
  useEffect(() => { let active = true; getCustomerRecommendations().then((result) => active && setData(result)).catch(() => active && setError(true)); return () => { active = false; }; }, []);

  return <section className="border-y border-brand-100 bg-gradient-to-b from-brand-50/70 to-white py-16">
    <div className="mx-auto max-w-7xl px-4 sm:px-6">
      <div className="flex items-end justify-between gap-4"><div><p className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wider text-brand-700"><Sparkles size={16} />Đề xuất thông minh</p><h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">Gợi ý dành cho bạn</h2><p className="mt-2 text-sm text-slate-500">{data?.personalized ? 'Dựa trên môn chơi, khung giờ, khoảng giá và khu vực bạn yêu thích.' : 'Các sân phổ biến, được đánh giá cao và đang còn lịch trống.'}</p></div><Link to="/venues" className="hidden items-center gap-1 text-sm font-bold text-brand-700 sm:flex">Xem tất cả <ArrowRight size={16} /></Link></div>
      {!data && !error ? <div className="mt-8 grid gap-5 md:grid-cols-3">{[1, 2, 3].map((item) => <div key={item} className="rounded-card border bg-white p-4"><div className="h-40 animate-pulse rounded-xl bg-slate-200" /><LoadingSkeleton className="mt-4" lines={4} /></div>)}</div> : error ? <div className="mt-8"><EmptyState title="Chưa tải được gợi ý" description="Dữ liệu recommendation tạm thời chưa khả dụng. Vui lòng thử lại sau." /></div> : <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">{data?.items.map((item) => <RecommendationCard key={item.field_id} item={item} personalized={data.personalized} />)}</div>}
    </div>
  </section>;
}

function RecommendationCard({ item, personalized }: { item: CustomerRecommendation; personalized: boolean }) {
  return <article className="group overflow-hidden rounded-card border border-slate-200 bg-white shadow-sm transition hover:-translate-y-1 hover:shadow-card">
    <div className="relative h-44 overflow-hidden"><img src={item.image_url || getSportImage(item.sport_type)} alt={item.field_name} className="h-full w-full object-cover transition duration-300 group-hover:scale-105" /><Badge variant="ai" className="absolute left-3 top-3"><Sparkles size={12} />{personalized ? 'Dành cho bạn' : 'Phổ biến'}</Badge></div>
    <div className="p-5"><div className="flex items-center justify-between gap-3"><span className="text-xs font-bold uppercase text-brand-700">{item.sport_type}</span><span className="flex items-center gap-1 text-sm font-semibold"><Star size={15} className="fill-amber-400 text-amber-400" />{item.rating.toFixed(1)} <small className="font-normal text-slate-400">({item.review_count})</small></span></div><h3 className="mt-2 text-lg font-bold text-slate-950">{item.field_name}</h3><p className="mt-1.5 flex items-start gap-1.5 text-sm text-slate-500"><MapPin size={15} className="mt-0.5 shrink-0" />{item.location}</p><p className="mt-1 text-xs font-medium text-sportblue-600">{item.distance_km == null ? 'Khoảng cách chưa cập nhật' : `Cách bạn ${item.distance_km.toLocaleString('vi-VN')} km`}</p>
      <div className="mt-4 rounded-xl bg-brand-50 p-3"><p className="text-xs leading-5 text-brand-800">{item.reason}</p><div className="mt-2 flex flex-wrap gap-1.5">{item.available_slots.map((slot) => <span key={slot.id} className="rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-brand-700"><Clock3 size={11} className="mr-1 inline" />{slot.start_time}</span>)}</div></div>
      <div className="mt-4 flex items-end justify-between border-t border-slate-100 pt-4"><p><span className="block text-[11px] text-slate-400">Chỉ từ</span><b className="text-lg text-brand-700">{item.price.toLocaleString('vi-VN')}đ</b><span className="text-xs text-slate-500"> / giờ</span></p><Link to={`/courts/${item.field_id}`}><Button size="sm">Xem sân</Button></Link></div>
    </div>
  </article>;
}
