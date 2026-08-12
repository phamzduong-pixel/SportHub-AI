import { LayoutGrid, List, Map, Search, SlidersHorizontal, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button, Drawer, EmptyState, Input, LoadingSkeleton, PageHeader, Pagination, Select } from '@/components/common';
import { MapMock } from '@/components/venue/MapMock';
import { VenueCard } from '@/components/venue/VenueCard';
import { emptyFilters, VenueFilters, type VenueFilterState } from '@/components/venue/VenueFilters';
import { useDisclosure } from '@/hooks/useDisclosure';
import { listVenues } from '@/services/venueService';
import type { Venue } from '@/types';

type ViewMode = 'grid' | 'list' | 'map';
const slotHour = (slot: string) => Number(slot.split(':')[0]);

export function VenuesPage() {
  const [params] = useSearchParams();
  const drawer = useDisclosure();
  const [query, setQuery] = useState(params.get('q') ?? '');
  const [filters, setFilters] = useState<VenueFilterState>({ ...emptyFilters, sport: params.get('sport') ?? '', date: params.get('date') ?? '', time: params.get('time')?.includes('Sáng') ? 'morning' : params.get('time')?.includes('Chiều') ? 'afternoon' : params.get('time')?.includes('Tối') ? 'evening' : '' });
  const [sort, setSort] = useState(params.get('sort') ?? 'recommended');
  const [view, setView] = useState<ViewMode>('grid');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [venues, setVenues] = useState<Venue[]>([]);
  const [selectedMapId, setSelectedMapId] = useState<number>();

  useEffect(() => {
    let active = true; setLoading(true); setLoadError('');
    const timer = window.setTimeout(() => {
      listVenues({ date: filters.date, search: query, sportType: filters.sport }).then((items) => { if (active) setVenues(items); }).catch((error) => { if (active) setLoadError(error instanceof Error ? error.message : 'Không tải được dữ liệu sân.'); }).finally(() => { if (active) setLoading(false); });
    }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [query, filters.date, filters.sport]);
  useEffect(() => setPage(1), [query, filters, sort]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const selectedDate = filters.date ? new Date(`${filters.date}T12:00:00`) : null;
    return venues.filter((venue) => {
      const matchesQuery = !normalized || `${venue.name} ${venue.address} ${venue.district} ${venue.sports.join(' ')}`.toLowerCase().includes(normalized);
      const matchesCity = !filters.city || venue.city === filters.city;
      const matchesSport = !filters.sport || venue.sports.some((sport) => sport.toLowerCase() === filters.sport.toLowerCase());
      const matchesPrice = !filters.maxPrice || venue.price <= Number(filters.maxPrice);
      const matchesRating = !filters.rating || venue.rating >= Number(filters.rating);
      const matchesAmenities = filters.amenities.every((item) => venue.amenities.includes(item));
      const allSlots = venue.courts.flatMap((court) => court.operatingSlots);
      const matchesTime = !filters.time || allSlots.some((slot) => { const hour = slotHour(slot); return filters.time === 'morning' ? hour < 12 : filters.time === 'afternoon' ? hour >= 12 && hour < 18 : hour >= 18; });
      const matchesDate = !selectedDate || venue.available;
      return matchesQuery && matchesCity && matchesSport && matchesPrice && matchesRating && matchesAmenities && matchesTime && matchesDate && venue.available;
    }).sort((a, b) => sort === 'price' ? a.price - b.price : sort === 'distance' ? a.distance - b.distance : sort === 'rating' ? b.rating - a.rating : b.reviewCount - a.reviewCount);
  }, [query, filters, sort]);

  const applied = [
    filters.city && { key: 'city', label: filters.city }, filters.sport && { key: 'sport', label: filters.sport }, filters.date && { key: 'date', label: new Date(`${filters.date}T12:00:00`).toLocaleDateString('vi-VN') },
    filters.time && { key: 'time', label: filters.time === 'morning' ? 'Buổi sáng' : filters.time === 'afternoon' ? 'Buổi chiều' : 'Buổi tối' }, filters.maxPrice && { key: 'maxPrice', label: `≤ ${Number(filters.maxPrice).toLocaleString('vi-VN')}đ` }, filters.rating && { key: 'rating', label: `Từ ${filters.rating} sao` },
    ...filters.amenities.map((item) => ({ key: `amenity:${item}`, label: item })),
  ].filter(Boolean) as Array<{ key: string; label: string }>;
  const removeFilter = (key: string) => key.startsWith('amenity:') ? setFilters((current) => ({ ...current, amenities: current.amenities.filter((item) => item !== key.slice(8)) })) : setFilters((current) => ({ ...current, [key]: '' }));
  const pageSize = 6; const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize)); const shown = filtered.slice((page - 1) * pageSize, page * pageSize);
  const filtersUi = <VenueFilters value={filters} onChange={setFilters} onReset={() => setFilters(emptyFilters)} />;

  return <div className="mx-auto min-w-0 max-w-[1440px] px-3 py-5 min-[375px]:px-4 sm:px-6 sm:py-8">
    <PageHeader title="Tìm sân thể thao" description="So sánh địa điểm, lịch trống và mức giá để chọn sân phù hợp nhất." breadcrumb={[{ label: 'Trang chủ', href: '/' }, { label: 'Tìm sân' }]} />
    <form onSubmit={(event) => event.preventDefault()} className="mb-5 flex gap-2 rounded-card border border-slate-200 bg-white p-3 shadow-sm"><div className="flex-1"><Input value={query} onChange={(event) => setQuery(event.target.value)} leftIcon={<Search size={18} />} placeholder="Tìm theo tên sân, quận hoặc môn thể thao..." /></div><Button type="submit" className="hidden sm:inline-flex">Tìm kiếm</Button><Button type="button" variant="outline" leftIcon={<SlidersHorizontal size={17} />} onClick={drawer.open} className="lg:hidden">Lọc</Button></form>
    {applied.length > 0 && <div className="mb-5 flex flex-wrap items-center gap-2"><span className="text-xs font-semibold text-slate-500">Đang lọc:</span>{applied.map((item) => <button key={item.key} onClick={() => removeFilter(item.key)} className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700">{item.label}<X size={13} /></button>)}<button onClick={() => setFilters(emptyFilters)} className="text-xs font-semibold text-red-600">Xóa tất cả</button></div>}
    <div className="grid gap-6 lg:grid-cols-[270px_1fr]"><aside className="hidden h-fit rounded-card border border-slate-200 bg-white p-5 shadow-sm lg:block lg:sticky lg:top-20">{filtersUi}</aside><section className="min-w-0"><div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><p className="text-sm text-slate-500">Tìm thấy <b className="text-slate-900">{filtered.length}</b> sân phù hợp</p><div className="flex items-center gap-2"><Select aria-label="Sắp xếp" value={sort} onChange={(event) => setSort(event.target.value)} options={[{ label: 'Phù hợp nhất', value: 'recommended' }, { label: 'Giá thấp nhất', value: 'price' }, { label: 'Gần nhất', value: 'distance' }, { label: 'Đánh giá cao', value: 'rating' }]} className="w-44" /><div className="flex rounded-lg border border-slate-200 bg-white p-1"><button aria-label="Dạng lưới" onClick={() => setView('grid')} className={`rounded p-1.5 ${view === 'grid' ? 'bg-brand-50 text-brand-700' : 'text-slate-400'}`}><LayoutGrid size={17} /></button><button aria-label="Dạng danh sách" onClick={() => setView('list')} className={`rounded p-1.5 ${view === 'list' ? 'bg-brand-50 text-brand-700' : 'text-slate-400'}`}><List size={17} /></button><button aria-label="Bản đồ" onClick={() => setView('map')} className={`rounded p-1.5 ${view === 'map' ? 'bg-sportblue-50 text-sportblue-600' : 'text-slate-400'}`}><Map size={17} /></button></div></div></div>
      {loading ? <div className={view === 'list' ? 'grid gap-4' : 'grid gap-5 md:grid-cols-2 xl:grid-cols-3'}>{Array.from({ length: 6 }).map((_, index) => <div key={index} className="rounded-card border border-slate-200 bg-white p-4"><div className="mb-4 h-44 animate-pulse rounded-lg bg-slate-200" /><LoadingSkeleton lines={4} /></div>)}</div> : loadError ? <EmptyState title="Không tải được dữ liệu sân" description={loadError} action={<Button variant="outline" onClick={() => setFilters((current) => ({ ...current }))}>Thử lại</Button>} /> : filtered.length === 0 ? <EmptyState title="Không tìm thấy sân phù hợp" description="Hãy thử bỏ bớt bộ lọc, thay đổi khu vực hoặc chọn khung giờ khác." action={<Button variant="outline" onClick={() => { setFilters(emptyFilters); setQuery(''); }}>Đặt lại tìm kiếm</Button>} /> : view === 'map' ? <div className="grid gap-4 xl:grid-cols-[1fr_320px]"><MapMock venues={filtered} selectedId={selectedMapId} onSelect={setSelectedMapId} className="h-[620px]" /><div className="max-h-[620px] space-y-3 overflow-auto pr-1">{filtered.map((venue) => <button key={venue.id} onClick={() => setSelectedMapId(venue.id)} className={`w-full rounded-card border bg-white p-4 text-left transition ${selectedMapId === venue.id ? 'border-sportblue-500 ring-2 ring-blue-100' : 'border-slate-200'}`}><b className="text-sm text-slate-900">{venue.name}</b><p className="mt-1 text-xs text-slate-500">{venue.distance} km • {venue.price.toLocaleString('vi-VN')}đ/giờ</p></button>)}</div></div> : <><div className={view === 'list' ? 'grid gap-4' : 'grid gap-5 md:grid-cols-2 xl:grid-cols-3'}>{shown.map((venue) => <VenueCard key={venue.id} venue={venue} horizontal={view === 'list'} />)}</div>{totalPages > 1 && <div className="mt-6 overflow-hidden rounded-card border border-slate-200 bg-white"><Pagination page={page} totalPages={totalPages} onChange={(nextPage) => { setPage(nextPage); window.scrollTo({ top: 250, behavior: 'smooth' }); }} /></div>}</>}
    </section></div>
    <Drawer open={drawer.isOpen} onClose={drawer.close} title="Lọc sân thể thao"><VenueFilters value={filters} onChange={setFilters} onReset={() => setFilters(emptyFilters)} onApply={drawer.close} /></Drawer>
  </div>;
}
