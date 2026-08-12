import { Heart, MapPin, Navigation, Star } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { KeyboardEvent, MouseEvent } from 'react';
import type { Venue } from '@/types/index';
import { Badge, Button, useToast } from '@/components/common';
import { useFavoriteField } from '@/hooks/useFavoriteField';

export function VenueCard({ venue, horizontal = false }: { venue: Venue; horizontal?: boolean }) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { favorite, loading, enabled, toggle } = useFavoriteField(venue.id);
  const detailUrl = `/courts/${venue.id}`;

  const openDetail = () => navigate(detailUrl);
  const openDetailFromClick = (event: MouseEvent<HTMLElement>) => {
    if ((event.target as HTMLElement).closest('button, a')) return;
    openDetail();
  };
  const openDetailFromKeyboard = (event: KeyboardEvent<HTMLElement>) => {
    if (event.target !== event.currentTarget || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    openDetail();
  };
  const toggleFavorite = async (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (!enabled) {
      toast('Vui lòng đăng nhập CUSTOMER để lưu sân yêu thích.', 'info');
      return;
    }
    try {
      const next = await toggle();
      if (next !== null) toast(next ? 'Đã thêm sân vào yêu thích.' : 'Đã bỏ sân khỏi yêu thích.', 'success');
    } catch {
      toast('Không thể cập nhật sân yêu thích.', 'error');
    }
  };
  const book = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (venue.available) navigate(`/courts/${venue.id}`);
  };

  const statusVariant = venue.status === 'Còn sân' ? 'success' : venue.status === 'Sắp hết chỗ' ? 'warning' : 'neutral';
  return (
    <article
      role="link"
      tabIndex={0}
      aria-label={`Xem chi tiết ${venue.name}`}
      onClick={openDetailFromClick}
      onKeyDown={openDetailFromKeyboard}
      className={`group cursor-pointer overflow-hidden rounded-card border border-slate-200 bg-white shadow-sm transition duration-200 hover:-translate-y-1 hover:border-brand-300 hover:shadow-card focus:outline-none focus:ring-4 focus:ring-brand-100 ${horizontal ? 'sm:grid sm:grid-cols-[240px_1fr]' : ''}`}
    >
      <div className={`relative overflow-hidden ${horizontal ? 'h-52 sm:h-full' : 'h-52'}`}>
        <img src={venue.image} alt={venue.name} className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]" />
        <button
          type="button"
          disabled={loading}
          onClick={(event) => void toggleFavorite(event)}
          aria-label={favorite ? 'Bỏ yêu thích' : 'Thêm vào yêu thích'}
          className={`absolute right-3 top-3 rounded-full bg-white/95 p-2.5 shadow transition hover:scale-105 ${favorite ? 'text-red-500' : 'text-slate-600 hover:text-red-500'}`}
        >
          <Heart size={19} className={favorite ? 'fill-current' : ''} />
        </button>
        <Badge variant={statusVariant} className="absolute left-3 top-3" dot>{venue.status}</Badge>
      </div>
      <div className="flex flex-col p-5">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-bold uppercase tracking-wide text-brand-700">{venue.sports.join(' • ')}</span>
          <span className="flex shrink-0 items-center gap-1 text-sm font-semibold"><Star size={15} className="fill-amber-400 text-amber-400" />{venue.rating} <small className="font-normal text-slate-400">({venue.reviewCount})</small></span>
        </div>
        <h3 className="mt-2 text-lg font-bold text-slate-900 transition group-hover:text-brand-700">{venue.name}</h3>
        <p className="mt-1.5 flex items-start gap-1.5 text-sm text-slate-500"><MapPin size={16} className="mt-0.5 shrink-0" />{venue.address}</p>
        <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-sportblue-600"><Navigation size={14} />Cách bạn {venue.distance.toLocaleString('vi-VN')} km</p>
        <div className="mt-4 flex items-end justify-between gap-3 border-t border-slate-100 pt-4">
          <p><span className="block text-[11px] text-slate-400">Chỉ từ</span><b className="text-lg text-brand-700">{venue.price.toLocaleString('vi-VN')}đ</b><span className="text-xs text-slate-500"> / giờ</span></p>
          <Button className="min-w-28" variant={venue.available ? 'primary' : 'outline'} disabled={!venue.available} onClick={book}>
            Đặt sân
          </Button>
        </div>
      </div>
    </article>
  );
}
