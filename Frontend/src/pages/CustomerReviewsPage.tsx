import { Star } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button, EmptyState, LoadingSkeleton, PageHeader, useToast } from '@/components/common';
import { getMyBookings, type ApiBooking } from '@/services/customerApi';
import { createReview } from '@/services/reviewService';

export function CustomerReviewsPage() {
  const [searchParams] = useSearchParams();
  const requestedBookingId = Number(searchParams.get('booking'));
  const [items, setItems] = useState<ApiBooking[]>([]);
  const [selected, setSelected] = useState<number>();
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    setLoading(true);
    getMyBookings()
      .then((result) => {
        const reviewable = result.items.filter((item) => item.status === 'completed' && !item.reviewed);
        setItems(reviewable);
        if (Number.isInteger(requestedBookingId) && reviewable.some((item) => item.id === requestedBookingId)) {
          setSelected(requestedBookingId);
        }
      })
      .catch((error) => {
        toast(error instanceof Error ? error.message : 'Không thể tải danh sách đánh giá.', 'error');
      })
      .finally(() => setLoading(false));
  }, [requestedBookingId, toast]);

  const submit = async () => {
    if (!selected || comment.trim().length < 2) {
      toast('Vui lòng chọn booking và nhập nhận xét.', 'error');
      return;
    }
    setSaving(true);
    try {
      await createReview(selected, rating, comment.trim());
      setItems((current) => current.filter((item) => item.id !== selected));
      setSelected(undefined);
      setComment('');
      setRating(5);
      toast('Cảm ơn bạn đã đánh giá sân.', 'success');
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Không thể gửi đánh giá.', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader title="Đánh giá sân" description="Chỉ booking đã hoàn thành mới có thể gửi đánh giá." />
      {loading ? (
        <LoadingSkeleton lines={7} />
      ) : items.length ? (
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
          <section className="space-y-3">
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => setSelected(item.id)}
                className={`w-full rounded-card border bg-white p-4 text-left ${selected === item.id ? 'border-brand-600 ring-2 ring-brand-100' : 'border-slate-200'}`}
              >
                <b>{item.field_name}</b>
                <p className="mt-1 text-sm text-slate-500">
                  {item.booking_code} · {item.booking_date} · {item.start_time_snapshot.slice(0, 5)}
                </p>
              </button>
            ))}
          </section>
          <aside className="h-fit rounded-card border bg-white p-5">
            <h2 className="font-bold">Viết đánh giá</h2>
            <div className="mt-4 flex gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button key={star} onClick={() => setRating(star)} aria-label={`${star} sao`}>
                  <Star className={star <= rating ? 'fill-amber-400 text-amber-400' : 'text-slate-300'} />
                </button>
              ))}
            </div>
            <textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              maxLength={2000}
              placeholder="Chia sẻ trải nghiệm của bạn..."
              className="field mt-4 min-h-32 py-2"
            />
            <Button loading={saving} disabled={!selected} onClick={() => void submit()} className="mt-4 w-full">
              Gửi đánh giá
            </Button>
          </aside>
        </div>
      ) : (
        <EmptyState
          title="Không có booking cần đánh giá"
          description="Booking đã hoàn thành và chưa đánh giá sẽ xuất hiện tại đây."
        />
      )}
    </>
  );
}
