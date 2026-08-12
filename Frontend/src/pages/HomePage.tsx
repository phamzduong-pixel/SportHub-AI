import { Bot, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/common';
import { AIRecommendation, BookingSteps, FeaturedVenues, NearbyVenues, OwnerSolution, SportCategories } from '@/components/venue/HomeSections';
import { VenueSearchBar } from '@/components/venue/VenueSearchBar';
import { PersonalizedRecommendations } from '@/components/venue/PersonalizedRecommendations';

export function HomePage() {
  return <>
    <section className="relative overflow-hidden bg-white">
      <div className="pointer-events-none absolute -right-48 -top-48 h-[600px] w-[600px] rounded-full bg-brand-50" />
      <div className="relative mx-auto grid max-w-7xl items-center gap-10 px-4 pb-16 pt-12 sm:px-6 lg:grid-cols-[1.05fr_.95fr] lg:pb-24 lg:pt-20">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1.5 text-xs font-bold text-brand-700"><CheckCircle2 size={14} />Hơn 250 sân đã được xác minh</span>
          <h1 className="mt-5 max-w-2xl text-balance text-4xl font-extrabold leading-[1.1] tracking-tight text-slate-950 sm:text-5xl lg:text-6xl">Tìm sân phù hợp, <span className="text-brand-600">đặt lịch trong vài phút</span></h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-slate-600 sm:text-lg">Khám phá sân thể thao chất lượng quanh bạn, xem lịch trống và đặt sân dễ dàng trên SportHub AI.</p>
          <Link to="/ai-assistant" className="inline-block"><Button size="lg" variant="ai" leftIcon={<Bot size={19} />} className="mt-7">Khám phá trợ lý AI</Button></Link>
          <div className="mt-8 flex flex-wrap gap-7 text-sm text-slate-500"><span><b className="block text-xl text-slate-900">250+</b>Sân thể thao</span><span><b className="block text-xl text-slate-900">12.000+</b>Lượt đặt thành công</span><span><b className="block text-xl text-slate-900">4,8/5</b>Đánh giá trung bình</span></div>
        </div>
        <div className="relative"><img className="h-[360px] w-full rounded-2xl object-cover shadow-float sm:h-[480px]" src="https://images.unsplash.com/photo-1526232761682-d26e03ac148e?auto=format&fit=crop&w=1200&q=85" alt="Sân thể thao hiện đại" /><div className="absolute bottom-5 left-5 rounded-card bg-white/95 p-4 shadow-card backdrop-blur"><b className="block text-sm text-slate-900">Sân gần bạn đang sẵn sàng</b><span className="mt-1 block text-xs text-slate-500">32 khung giờ trống tối nay</span></div></div>
      </div>
      <div className="relative mx-auto -mt-7 max-w-7xl px-4 pb-8 sm:px-6"><div className="rounded-card border border-slate-200 bg-white p-4 shadow-float sm:p-5"><VenueSearchBar /></div></div>
    </section>
    <SportCategories />
    <PersonalizedRecommendations />
    <FeaturedVenues />
    <NearbyVenues />
    <BookingSteps />
    <AIRecommendation />
    <OwnerSolution />
  </>;
}
