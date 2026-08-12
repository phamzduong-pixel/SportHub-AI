import { CalendarDays, CheckCircle2, Clock3, ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { Venue } from '@/types/index';
import { Button, Input, Select, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';

interface AvailableSlot {
  id: number;
  field_id: number;
  name: string;
  start_time: string;
  end_time: string;
  price: number;
}

interface Availability {
  available_slots: AvailableSlot[];
}

interface BookingContext {
  venueId: number;
  courtId: number;
  date: string;
  slotId: number;
  startTime: string;
  endTime: string;
  price: number;
}

const localToday = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};

export function VenueBookingPanel({ venue }: { venue: Venue }) {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [date, setDate] = useState(searchParams.get('date') || '');
  const [courtId, setCourtId] = useState(venue.courts[0]?.id ?? '');
  const [slots, setSlots] = useState<AvailableSlot[]>([]);
  const [slotId, setSlotId] = useState(Number(searchParams.get('slot')) || 0);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const court = useMemo(() => venue.courts.find((item) => item.id === courtId), [venue.courts, courtId]);
  const selectedSlot = slots.find((item) => item.id === slotId);
  const price = selectedSlot?.price ?? court?.price ?? venue.price;

  useEffect(() => {
    if (!date || !courtId) {
      setSlots([]);
      setSlotId(0);
      return;
    }
    let active = true;
    setLoadingSlots(true);
    apiRequest<Availability[]>(`/availability?date=${encodeURIComponent(date)}&field_id=${courtId}`)
      .then((result) => {
        if (!active) return;
        const available = result[0]?.available_slots || [];
        setSlots(available);
        setSlotId((current) => available.some((item) => item.id === current) ? current : 0);
      })
      .catch((error) => {
        if (!active) return;
        setSlots([]);
        setSlotId(0);
        toast(error instanceof Error ? error.message : 'Không tải được lịch trống.', 'error');
      })
      .finally(() => { if (active) setLoadingSlots(false); });
    return () => { active = false; };
  }, [courtId, date]);

  const continueBooking = () => {
    if (!date || !courtId || !selectedSlot) {
      toast('Vui lòng chọn đầy đủ ngày, sân và khung giờ.', 'error');
      return;
    }
    const context: BookingContext = {
      venueId: venue.facilityId ?? venue.id,
      courtId: Number(courtId),
      date,
      slotId: selectedSlot.id,
      startTime: selectedSlot.start_time,
      endTime: selectedSlot.end_time,
      price: selectedSlot.price,
    };
    sessionStorage.setItem('sporthub_booking_context', JSON.stringify(context));
    const params = new URLSearchParams({ date, slot: String(selectedSlot.id) });
    navigate(`/booking/${courtId}?${params.toString()}`);
  };

  return <aside className="rounded-card border border-slate-200 bg-white p-5 shadow-card lg:sticky lg:top-20">
    <div className="flex items-end justify-between border-b border-slate-100 pb-4">
      <div><span className="text-xs text-slate-500">Giá sân</span><p><b className="text-2xl text-brand-700">{price.toLocaleString('vi-VN')}đ</b><span className="text-xs text-slate-500"> / khung giờ</span></p></div>
      <span className="flex items-center gap-1 text-xs font-semibold text-brand-700"><CheckCircle2 size={15} />Còn lịch</span>
    </div>
    <div className="mt-5 space-y-4">
      <Input label="Chọn ngày" type="date" min={localToday()} value={date} onChange={(event) => { setDate(event.target.value); setSlotId(0); }} leftIcon={<CalendarDays size={17} />} disabled={!venue.available} />
      <Select label="Chọn sân" value={courtId} onChange={(event) => { setCourtId(event.target.value); setSlotId(0); }} options={venue.courts.map((item) => ({ label: `${item.name} · ${item.type}`, value: item.id }))} disabled={!venue.available} />
      <fieldset>
        <legend className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700"><Clock3 size={16} />Chọn khung giờ</legend>
        <div className="grid grid-cols-2 gap-2">
          {loadingSlots ? <p className="col-span-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">Đang kiểm tra lịch trống…</p> : slots.length ? slots.map((item) =>
            <button type="button" key={item.id} onClick={() => setSlotId(item.id)} className={`rounded-lg border px-2 py-2 text-xs font-semibold ${slotId === item.id ? 'border-brand-600 bg-brand-50 text-brand-700 ring-2 ring-brand-100' : 'border-slate-200 text-slate-600 hover:border-brand-400'}`}>
              {item.start_time.slice(0, 5)}–{item.end_time.slice(0, 5)}
              <span className='mt-1 block font-normal'>{item.price.toLocaleString('vi-VN')} VND</span>
            </button>
          ) : <p className="col-span-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">{date ? 'Ngày này không còn khung giờ trống.' : 'Chọn ngày để xem lịch trống thực tế.'}</p>}
        </div>
      </fieldset>
    </div>
    <div className="mt-5 border-t border-slate-100 pt-4 text-sm">
      <div className="flex justify-between text-slate-500"><span>Tiền sân dự kiến</span><span>{price.toLocaleString('vi-VN')}đ</span></div>
      <div className="mt-3 flex justify-between font-bold"><span>Tổng cộng</span><span>{price.toLocaleString('vi-VN')}đ</span></div>
    </div>
    <Button onClick={continueBooking} disabled={!venue.available || !selectedSlot} size="lg" className="mt-5 w-full">{venue.available ? 'Tiếp tục đặt sân' : 'Tạm ngưng nhận đặt'}</Button>
    <p className="mt-3 flex items-center justify-center gap-1.5 text-xs text-slate-500"><ShieldCheck size={14} />Bạn chưa bị tính phí ở bước này</p>
  </aside>;
}
