import { RotateCcw } from 'lucide-react';
import { Button, Input, Select } from '@/components/common';

export interface VenueFilterState {
  city: string; sport: string; date: string; time: string; maxPrice: string; rating: string; amenities: string[];
}
export const emptyFilters: VenueFilterState = { city: '', sport: '', date: '', time: '', maxPrice: '', rating: '', amenities: [] };
const amenities = ['Bãi đỗ xe', 'Phòng thay đồ', 'Mái che', 'Phòng tắm', 'Cho thuê vợt', 'Căng tin'];

export function VenueFilters({ value, onChange, onReset, onApply }: { value: VenueFilterState; onChange: (next: VenueFilterState) => void; onReset: () => void; onApply?: () => void }) {
  const update = (key: keyof VenueFilterState, nextValue: string | string[]) => onChange({ ...value, [key]: nextValue });
  const toggleAmenity = (amenity: string) => update('amenities', value.amenities.includes(amenity) ? value.amenities.filter((item) => item !== amenity) : [...value.amenities, amenity]);
  return <div className="min-w-0 space-y-5">
    <div className="flex items-center justify-between gap-3"><h2 className="font-bold text-slate-900">Bộ lọc</h2><button type="button" onClick={onReset} className="flex min-h-10 items-center gap-1 text-xs font-semibold text-brand-700"><RotateCcw size={14} />Đặt lại</button></div>
    <Select label="Địa điểm" value={value.city} onChange={(event) => update('city', event.target.value)} options={['TP. Hồ Chí Minh', 'Hà Nội'].map((item) => ({ label: item, value: item }))} placeholder="Tất cả địa điểm" />
    <Select label="Môn thể thao" value={value.sport} onChange={(event) => update('sport', event.target.value)} options={['Bóng đá', 'Cầu lông', 'Pickleball', 'Tennis', 'Bóng rổ', 'Bóng chuyền'].map((item) => ({ label: item, value: item }))} placeholder="Tất cả môn" />
    <div className="grid grid-cols-1 gap-3 min-[375px]:grid-cols-2"><Input label="Ngày chơi" type="date" value={value.date} onChange={(event) => update('date', event.target.value)} /><Select label="Khung giờ" value={value.time} onChange={(event) => update('time', event.target.value)} options={[{ label: 'Buổi sáng', value: 'morning' }, { label: 'Buổi chiều', value: 'afternoon' }, { label: 'Buổi tối', value: 'evening' }]} placeholder="Bất kỳ" /></div>
    <Select label="Mức giá tối đa" value={value.maxPrice} onChange={(event) => update('maxPrice', event.target.value)} options={[{ label: 'Dưới 200.000đ', value: '200000' }, { label: 'Dưới 400.000đ', value: '400000' }, { label: 'Dưới 600.000đ', value: '600000' }]} placeholder="Không giới hạn" />
    <Select label="Đánh giá tối thiểu" value={value.rating} onChange={(event) => update('rating', event.target.value)} options={[{ label: 'Từ 4,0 sao', value: '4' }, { label: 'Từ 4,5 sao', value: '4.5' }, { label: 'Từ 4,8 sao', value: '4.8' }]} placeholder="Tất cả đánh giá" />
    <fieldset><legend className="mb-3 text-sm font-medium text-slate-700">Tiện ích</legend><div className="grid grid-cols-1 gap-2 min-[360px]:grid-cols-2">{amenities.map((amenity) => <label key={amenity} className="flex min-w-0 cursor-pointer items-start gap-2 rounded-lg border border-slate-200 p-2.5 text-xs text-slate-600 hover:bg-slate-50"><input type="checkbox" checked={value.amenities.includes(amenity)} onChange={() => toggleAmenity(amenity)} className="mt-0.5 h-4 w-4 shrink-0 accent-brand-600" /><span className="break-words">{amenity}</span></label>)}</div></fieldset>
    {onApply && <Button type="button" onClick={onApply} className="w-full lg:hidden">Áp dụng bộ lọc</Button>}
  </div>;
}
