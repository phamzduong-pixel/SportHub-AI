import { Bot, Heart, MapPin, Share2, Star } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { VenueBookingPanel } from '@/components/booking/VenueBookingPanel';
import { Badge, Breadcrumb, Button, EmptyState, LoadingSkeleton, useToast } from '@/components/common';
import { VenueDetailTabs } from '@/components/venue/VenueDetailTabs';
import { VenueGallery } from '@/components/venue/VenueGallery';
import { useFavoriteField } from '@/hooks/useFavoriteField';
import { VenueReviews } from '@/components/venue/VenueReviews';
import { ApiError } from '@/services/apiClient';
import { getVenue } from '@/services/venueService';
import type { Venue } from '@/types';

export function VenueDetailPage() {
  const { courtId } = useParams();
  const [venue, setVenue] = useState<Venue>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const numericCourtId = Number(courtId);
  const { favorite, enabled, toggle } = useFavoriteField(Number.isInteger(numericCourtId) ? numericCourtId : 0);
  const { toast } = useToast();

  useEffect(() => {
    const id = Number(courtId);
    if (!Number.isInteger(id) || id <= 0) { setError('Đường dẫn sân không hợp lệ.'); setLoading(false); return; }
    let active = true; setLoading(true); setError(''); setVenue(undefined);
    getVenue(id).then((result) => { if (active) setVenue(result); }).catch((reason) => {
      if (!active) return;
      setError(reason instanceof ApiError && reason.status === 404
        ? 'Sân này không tồn tại hoặc đã ngừng hoạt động.'
        : 'Không thể tải thông tin sân. Vui lòng thử lại.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [courtId, reloadKey]);

  if (loading) return <div className="mx-auto max-w-7xl px-4 py-16"><LoadingSkeleton lines={10} /></div>;
  if (!venue) { const notFound = error.startsWith('Sân này') || error.startsWith('Đường dẫn'); return <div className="mx-auto max-w-7xl px-4 py-16"><EmptyState title={notFound ? 'Không tìm thấy sân' : 'Không tải được thông tin sân'} description={error} action={notFound ? <Link to="/venues"><Button>Quay lại tìm sân</Button></Link> : <Button onClick={() => setReloadKey((value) => value + 1)}>Thử lại</Button>} /></div>; }

  const share = async () => {
    try {
      if (navigator.share) await navigator.share({ title: venue.name, url: window.location.href });
      else if (navigator.clipboard) await navigator.clipboard.writeText(window.location.href);
      else throw new Error('Trình duyệt không hỗ trợ chia sẻ');
      toast('Đã chia sẻ thông tin sân.', 'info');
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      toast('Không thể chia sẻ. Vui lòng sao chép đường dẫn trên trình duyệt.', 'error');
    }
  };

  const toggleFavorite = async () => { if (!enabled) { toast('Vui lòng đăng nhập CUSTOMER để lưu sân yêu thích.', 'info'); return; } try { const next = await toggle(); if (next !== null) toast(next ? 'Đã thêm vào yêu thích.' : 'Đã bỏ yêu thích.', 'success'); } catch { toast('Không thể cập nhật sân yêu thích.', 'error'); } };

  return <div className="mx-auto w-full min-w-0 max-w-7xl px-3 py-4 sm:px-6 sm:py-8">
    <Breadcrumb items={[{ label: 'Trang chủ', href: '/' }, { label: 'Tìm sân', href: '/venues' }, { label: venue.name }]} />
    <VenueGallery images={venue.gallery} name={venue.name} />
    <header className="my-5 flex min-w-0 flex-col justify-between gap-4 sm:my-7 sm:flex-row sm:items-start sm:gap-5">
      <div>
        <div className="flex flex-wrap items-center gap-2"><Badge variant={venue.status === 'Còn sân' ? 'success' : venue.status === 'Sắp hết chỗ' ? 'warning' : 'neutral'} dot>{venue.status}</Badge><span className="text-xs font-bold uppercase tracking-wide text-brand-700">{venue.sports.join(' • ')}</span></div>
        <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-slate-950 sm:text-4xl">{venue.name}</h1>
        {venue.facilityName && venue.facilityName !== venue.name && <p className="mt-1 font-semibold text-brand-700">Cơ sở: {venue.facilityName}</p>}
        <p className="mt-2 flex items-start gap-2 text-sm text-slate-500"><MapPin size={17} className="mt-0.5 shrink-0" />{venue.address}, {venue.city}</p>
        <p className="mt-2 flex items-center gap-1 text-sm"><Star size={17} className="fill-amber-400 text-amber-400" /><b>{venue.rating}</b><span className="text-slate-500">({venue.reviewCount} đánh giá) • Cách bạn {venue.distance} km</span></p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Link to={`/ai-assistant?courtId=${venue.id}`}><Button variant="ai" leftIcon={<Bot size={17} />}>Hỏi AI về sân này</Button></Link>
        <Button variant="outline" leftIcon={<Share2 size={17} />} onClick={() => void share()}>Chia sẻ</Button>
        <Button variant={favorite ? 'danger' : 'outline'} leftIcon={<Heart size={17} className={favorite ? 'fill-current' : ''} />} onClick={toggleFavorite}>{favorite ? 'Đã thích' : 'Yêu thích'}</Button>
      </div>
    </header>
<div className="grid min-w-0 items-start gap-5 sm:gap-6 lg:grid-cols-[minmax(0,1fr)_350px]"><div className="min-w-0"><VenueDetailTabs venue={venue} /><VenueReviews fieldId={venue.id} /></div><VenueBookingPanel venue={venue} /></div>
  </div>;
}
