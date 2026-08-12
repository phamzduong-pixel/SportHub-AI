import { CalendarDays, CheckCircle2, Clock3, MapPin, QrCode } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button, EmptyState, LoadingSkeleton, PageHeader, useToast } from '@/components/common';
import { ApiError, apiRequest } from '@/services/apiClient';
import { createBankIntent, getBookingQuote, getMyBooking, type ApiBooking, type BookingQuote } from '@/services/customerApi';

interface BookingContext {
  venueId: number;
  courtId: number;
  date: string;
  slotId: number;
  startTime: string;
  endTime: string;
  price: number;
}

interface BookingDraft {
  courtId: number;
  date: string;
  slotId: number;
  note: string;
  accepted: boolean;
}

const money = (value: number) => `${value.toLocaleString('vi-VN')}đ`;
const contextKey = 'sporthub_booking_context';
const draftKey = 'sporthub_booking_draft';

function storedContext(): BookingContext | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(contextKey) || 'null') as Partial<BookingContext> & { fieldId?: number } | null;
    const courtId = Number(value?.courtId ?? value?.fieldId);
    if (!value || !Number.isInteger(courtId) || typeof value.date !== 'string' || !Number.isInteger(value.slotId)) return null;
    return {
      venueId: Number(value.venueId || courtId),
      courtId,
      date: value.date,
      slotId: Number(value.slotId),
      startTime: value.startTime || '',
      endTime: value.endTime || '',
      price: Number(value.price || 0),
    };
  } catch {
    return null;
  }
}

function storedDraft(context: BookingContext): BookingDraft | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(draftKey) || 'null') as Partial<BookingDraft> | null;
    return value?.courtId === context.courtId && value.date === context.date && value.slotId === context.slotId
      ? value as BookingDraft
      : null;
  } catch {
    return null;
  }
}

export function BookingPage() {
  const { venueId = '' } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const courtId = Number(venueId);
  const date = params.get('date') || '';
  const slotId = Number(params.get('slot')) || 0;
  const saved = storedContext();
  const context: BookingContext = saved?.courtId === courtId && saved.date === date && saved.slotId === slotId
    ? saved
    : { venueId: courtId, courtId, date, slotId, startTime: '', endTime: '', price: 0 };
  const initialDraft = storedDraft(context);
  const [quote, setQuote] = useState<BookingQuote>();
  const [note, setNote] = useState(initialDraft?.note || '');
  const [accepted, setAccepted] = useState(initialDraft?.accepted || false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [stale, setStale] = useState(false);
  const validContext = Number.isInteger(context.courtId) && context.courtId > 0
    && /^\d{4}-\d{2}-\d{2}$/.test(context.date)
    && Number.isInteger(context.slotId) && context.slotId > 0;

  useEffect(() => {
    if (!validContext) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setStale(false);
    getBookingQuote(context.courtId, context.slotId, context.date)
      .then((result) => {
        if (!active) return;
        setQuote(result);
        sessionStorage.setItem(contextKey, JSON.stringify({
          venueId: result.venue_id ?? context.venueId,
          courtId: result.field_id,
          date: result.booking_date,
          slotId: result.time_slot_id,
          startTime: result.start_time,
          endTime: result.end_time,
          price: result.price,
        } satisfies BookingContext));
      })
      .catch((error) => {
        if (!active) return;
        setQuote(undefined);
        setStale(error instanceof ApiError && error.status === 409);
        if (!(error instanceof ApiError && error.status === 409)) {
          toast(error instanceof Error ? error.message : 'Không thể xác nhận thông tin lịch đặt.', 'error');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [context.courtId, context.date, context.slotId, validContext]);

  useEffect(() => {
    if (!validContext) return;
    sessionStorage.setItem(draftKey, JSON.stringify({
      courtId: context.courtId,
      date: context.date,
      slotId: context.slotId,
      note,
      accepted,
    } satisfies BookingDraft));
  }, [accepted, context.courtId, context.date, context.slotId, note, validContext]);

  const submit = async () => {
    if (!accepted || !quote) return;
    setSubmitting(true);
    try {
      const pending = await apiRequest<ApiBooking>('/bookings', {
        method: 'POST',
        body: JSON.stringify({
          field_id: context.courtId,
          time_slot_id: context.slotId,
          booking_date: context.date,
          note: note.trim() || null,
        }),
      });
      sessionStorage.setItem('sporthub_latest_booking', String(pending.id));
      sessionStorage.removeItem(draftKey);
      const payment = await createBankIntent(pending.id);
      navigate(`/booking/payment/${payment.id}`, { state: { booking: pending, payment } });
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setStale(true);
        setQuote(undefined);
        toast('Khung giờ này vừa được người khác đặt hoặc không còn khả dụng. Vui lòng chọn khung giờ khác.', 'error');
      } else {
        toast(error instanceof Error ? error.message : 'Không thể tạo yêu cầu thanh toán.', 'error');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const changeUrl = `/courts/${context.courtId}?date=${encodeURIComponent(context.date)}&slot=${context.slotId}`;
  if (!validContext) {
    return <div className='mx-auto max-w-3xl px-4 py-16'><EmptyState title='Chưa có lịch được chọn' description='Hãy chọn ngày, sân và khung giờ còn trống tại trang chi tiết trước khi tiếp tục.' action={<Link to={courtId > 0 ? `/courts/${courtId}` : '/venues'}><Button>Chọn lịch đặt sân</Button></Link>} /></div>;
  }
  if (loading) return <div className='mx-auto max-w-5xl px-4 py-10'><LoadingSkeleton lines={9} /></div>;
  if (stale || !quote) {
    return <div className='mx-auto max-w-3xl px-4 py-16'><EmptyState title='Khung giờ không còn khả dụng' description='Khung giờ bạn chọn vừa được người khác đặt, bị khóa hoặc chuyển sang bảo trì. Hệ thống không tự đổi sang slot khác.' action={<Link to={changeUrl}><Button>Chọn khung giờ khác</Button></Link>} /></div>;
  }

  return <div className='mx-auto max-w-5xl px-4 py-8 sm:px-6'>
    <PageHeader title='Xác nhận lịch đặt sân' description='Thông tin dưới đây là lịch đã chọn; bạn không cần chọn lại ngày hoặc khung giờ.' actions={<Link to={changeUrl}><Button variant='outline'>Thay đổi lịch</Button></Link>} />
    <div className='grid items-start gap-6 lg:grid-cols-[1fr_340px]'>
      <section className='rounded-card border bg-white p-5 sm:p-7'>
        <div className='rounded-xl bg-brand-50 p-4'>
          <p className='text-xs font-bold uppercase text-brand-700'>{quote.sport_type}</p>
          <h2 className='mt-1 text-xl font-bold'>{quote.venue_name}</h2>
          <p className='mt-1 font-semibold text-slate-800'>Sân: {quote.field_name}</p>
          <p className='mt-1 text-sm text-slate-600'>Loại/cấu hình sân: <b>{quote.field_type}</b></p>
          <p className='mt-2 flex gap-2 text-sm text-slate-600'><MapPin size={16} />{quote.location}</p>
        </div>
        <div className='mt-6 grid gap-4 rounded-xl border border-slate-200 p-4 sm:grid-cols-2'>
          <div><span className='text-xs text-slate-500'>Ngày chơi</span><p className='mt-1 font-bold'><CalendarDays size={16} className='mr-2 inline text-brand-600' />{new Date(`${quote.booking_date}T00:00:00`).toLocaleDateString('vi-VN')}</p></div>
          <div><span className='text-xs text-slate-500'>Khung giờ đã chọn</span><p className='mt-1 font-bold'><Clock3 size={16} className='mr-2 inline text-brand-600' />{quote.start_time.slice(0, 5)}–{quote.end_time.slice(0, 5)}</p></div>
        </div>
        <label className='mt-6 block text-sm font-medium'>Ghi chú<textarea className='field mt-2 min-h-24 py-2' value={note} onChange={(event) => setNote(event.target.value)} placeholder='Yêu cầu thêm cho chủ sân (không bắt buộc)' /></label>
        <label className='mt-5 flex gap-3 text-sm text-slate-600'><input type='checkbox' checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />Tôi đồng ý chính sách đặt và hủy sân.</label>
      </section>
      <aside className='rounded-card border bg-white p-5 lg:sticky lg:top-20'>
        <h2 className='font-bold'>Tóm tắt thanh toán</h2>
        <div className='mt-4 space-y-3 text-sm'>
          <MoneyRow label='Giá sân theo slot' value={quote.price} strong />
          <MoneyRow label={`Tiền cọc${quote.deposit_type === 'percentage' ? ` (${quote.deposit_value}%)` : ''}`} value={quote.deposit_amount} />
          <MoneyRow label='Còn lại sau cọc' value={quote.remaining_amount} />
        </div>
        <div className='mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800'><b>Chính sách hủy và hoàn cọc:</b> {quote.cancellation_policy_summary}</div>
        <Button className='mt-5 w-full' loading={submitting} disabled={!accepted} onClick={() => void submit()}>Thanh toán đặt cọc {money(quote.deposit_amount)}</Button>
        <p className='mt-3 text-center text-xs text-slate-400'>Backend xác nhận lại đúng court, ngày, slot và giá ngay trước khi tạo booking tạm.</p>
      </aside>
    </div>
  </div>;
}

function MoneyRow({ label, value, strong }: { label: string; value: number; strong?: boolean }) {
  return <div className={`flex justify-between border-t pt-3 ${strong ? 'font-bold' : ''}`}><span>{label}</span><span>{money(value)}</span></div>;
}

export function BookingSuccessPage() {
  const location = useLocation();
  const [booking, setBooking] = useState<ApiBooking | undefined>((location.state as { booking?: ApiBooking } | null)?.booking);
  useEffect(() => {
    if (!booking) {
      const id = sessionStorage.getItem('sporthub_latest_booking');
      if (id) getMyBooking(id).then(setBooking);
    }
  }, [booking]);
  if (!booking) return <div className='mx-auto max-w-2xl p-10'><LoadingSkeleton lines={7} /></div>;
  return <div className='mx-auto max-w-2xl px-4 py-12'><div className='overflow-hidden rounded-2xl border bg-white shadow-card'><div className='bg-brand-600 p-7 text-center text-white'><CheckCircle2 className='mx-auto' size={50} /><h1 className='mt-3 text-2xl font-extrabold'>Đặt cọc thành công!</h1><p className='mt-1 text-sm text-brand-100'>Booking đã được xác nhận và sân đã được giữ.</p></div><div className='p-6'><div className='flex gap-5'><QrCode size={90} /><div><b className='text-brand-700'>{booking.booking_code}</b><p>{booking.facility_name}<br />{booking.field_name} · {booking.sport_type}<br />{booking.booking_date} · {booking.start_time_snapshot.slice(0, 5)}–{booking.end_time_snapshot.slice(0, 5)}<br />Cấu hình sân: Sân {booking.field_capacity}</p><p className='mt-2 text-sm'>Đã cọc: <b>{money(booking.deposit_amount)}</b><br />Còn lại: <b>{money(booking.remaining_amount)}</b></p></div></div><Link to={`/customer/bookings/${booking.id}`}><Button className='mt-6 w-full'>Xem chi tiết booking</Button></Link></div></div></div>;
}
