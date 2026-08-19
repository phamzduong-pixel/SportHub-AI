import { Star } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button, EmptyState, LoadingSkeleton, PageHeader, useToast } from '@/components/common';
import { getMyBookings, type ApiBooking } from '@/services/customerApi';
import { createReview, getCustomerReviews, updateReview, type Review } from '@/services/reviewService';

export function CustomerReviewsPage() {
  const [searchParams] = useSearchParams();
  const requestedBookingId = Number(searchParams.get('booking'));
  const [pendingItems, setPendingItems] = useState<ApiBooking[]>([]);
  const [reviewedItems, setReviewedItems] = useState<ApiBooking[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  
  const [tab, setTab] = useState<'pending' | 'reviewed'>('pending');
  const [selected, setSelected] = useState<number>();
  
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    setLoading(true);
    Promise.all([getMyBookings(), getCustomerReviews()])
      .then(([bookingsResult, reviewsResult]) => {
        const completed = bookingsResult.items.filter((item) => item.status === 'completed');
        
        const pending = completed.filter((item) => !item.reviewed);
        const reviewed = completed.filter((item) => item.reviewed);
        
        setPendingItems(pending);
        setReviewedItems(reviewed);
        setReviews(reviewsResult);

        if (Number.isInteger(requestedBookingId)) {
          if (pending.some((item) => item.id === requestedBookingId)) {
            setTab('pending');
            setSelected(requestedBookingId);
          } else if (reviewed.some((item) => item.id === requestedBookingId)) {
            setTab('reviewed');
            setSelected(requestedBookingId);
          }
        }
      })
      .catch((error) => {
        toast(error instanceof Error ? error.message : 'Không thể tải danh sách đánh giá.', 'error');
      })
      .finally(() => setLoading(false));
  }, [requestedBookingId, toast]);

  useEffect(() => {
    if (tab === 'reviewed' && selected) {
      const existing = reviews.find(r => r.booking_id === selected);
      if (existing) {
        setRating(existing.rating);
        setComment(existing.comment);
        setIsEditing(false);
      }
    } else if (tab === 'pending') {
      setRating(5);
      setComment('');
    }
  }, [tab, selected, reviews]);

  const submit = async () => {
    if (!selected || comment.trim().length < 2) {
      toast('Vui lòng chọn booking và nhập nhận xét.', 'error');
      return;
    }
    setSaving(true);
    try {
      const newReview = await createReview(selected, rating, comment.trim());
      
      const movedItem = pendingItems.find((item) => item.id === selected);
      if (movedItem) {
        setPendingItems((current) => current.filter((item) => item.id !== selected));
        setReviewedItems((current) => [{ ...movedItem, reviewed: true }, ...current]);
        setReviews((current) => [newReview, ...current]);
      }
      
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

  
  const handleUpdate = async () => {
    if (!selected || comment.trim().length < 2) {
      toast('Vui lòng nhập nhận xét ít nhất 2 ký tự.', 'error');
      return;
    }
    const existing = reviews.find(r => r.booking_id === selected);
    if (!existing) return;
    
    setSaving(true);
    try {
      const updatedReview = await updateReview(existing.id, rating, comment.trim());
      setReviews(current => current.map(r => r.id === updatedReview.id ? updatedReview : r));
      setIsEditing(false);
      toast('Đã cập nhật đánh giá.', 'success');
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Không thể cập nhật đánh giá.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const currentItems = tab === 'pending' ? pendingItems : reviewedItems;

  return (
    <>
      <PageHeader title="Đánh giá sân" description="Chỉ booking đã hoàn thành mới có thể gửi đánh giá." />
      
      <div className="mb-6 flex gap-4 border-b">
        <button 
          onClick={() => { setTab('pending'); setSelected(undefined); }}
          className={`pb-2 font-medium ${tab === 'pending' ? 'border-b-2 border-brand-600 text-brand-700' : 'text-slate-500 hover:text-slate-700'}`}
        >
          Chờ đánh giá ({pendingItems.length})
        </button>
        <button 
          onClick={() => { setTab('reviewed'); setSelected(undefined); }}
          className={`pb-2 font-medium ${tab === 'reviewed' ? 'border-b-2 border-brand-600 text-brand-700' : 'text-slate-500 hover:text-slate-700'}`}
        >
          Đã đánh giá ({reviewedItems.length})
        </button>
      </div>

      {loading ? (
        <LoadingSkeleton lines={7} />
      ) : currentItems.length ? (
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
          <section className="space-y-3">
            {currentItems.map((item) => {
              const review = reviews.find(r => r.booking_id === item.id);
              return (
                <button
                  key={item.id}
                  onClick={() => setSelected(item.id)}
                  className={`w-full rounded-card border bg-white p-4 text-left ${selected === item.id ? 'border-brand-600 ring-2 ring-brand-100' : 'border-slate-200'}`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <b>{item.field_name}</b>
                      <p className="mt-1 text-sm text-slate-500">
                        {item.facility_name}
                      </p>
                    </div>
                    {tab === 'reviewed' && review && (
                      <div className="flex items-center gap-1 rounded bg-amber-50 px-2 py-1 text-sm font-bold text-amber-600">
                        {review.rating} <Star size={14} className="fill-amber-500 text-amber-500" />
                      </div>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-slate-500">
                    {item.booking_code} · {item.booking_date} · {item.start_time_snapshot.slice(0, 5)}
                  </p>
                </button>
              );
            })}
          </section>
          
          {selected && (
            <aside className="h-fit rounded-card border bg-white p-5">
              <div className="flex items-center justify-between">
                <h2 className="font-bold">{tab === 'pending' ? 'Viết đánh giá' : isEditing ? 'Chỉnh sửa đánh giá' : 'Chi tiết đánh giá'}</h2>
                {tab === 'reviewed' && !isEditing && (
                  <Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>Chỉnh sửa</Button>
                )}
              </div>
              <div className="mt-4 flex gap-1">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button 
                    key={star} 
                    onClick={() => (tab === 'pending' || isEditing) && setRating(star)} 
                    disabled={tab === 'reviewed' && !isEditing}
                    aria-label={`${star} sao`}
                  >
                    <Star className={star <= rating ? 'fill-amber-400 text-amber-400' : 'text-slate-300'} />
                  </button>
                ))}
              </div>
              <textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                maxLength={2000}
                disabled={tab === 'reviewed' && !isEditing}
                placeholder="Chia sẻ trải nghiệm của bạn..."
                className="field mt-4 min-h-32 py-2 disabled:bg-slate-50 disabled:text-slate-700"
              />
              {tab === 'pending' && (
                <Button loading={saving} disabled={!selected} onClick={() => void submit()} className="mt-4 w-full">
                  Gửi đánh giá
                </Button>
              )}
              {tab === 'reviewed' && isEditing && (
                <div className="mt-4 flex gap-2">
                  <Button variant="outline" className="flex-1" disabled={saving} onClick={() => {
                    const existing = reviews.find(r => r.booking_id === selected);
                    if (existing) {
                      setRating(existing.rating);
                      setComment(existing.comment);
                    }
                    setIsEditing(false);
                  }}>
                    Hủy
                  </Button>
                  <Button className="flex-1" loading={saving} onClick={() => void handleUpdate()}>
                    Lưu thay đổi
                  </Button>
                </div>
              )}
              {tab === 'reviewed' && selected && !isEditing && (() => {
                const review = reviews.find(r => r.booking_id === selected);
                return review?.owner_reply ? (
                  <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm">
                    <b className="mb-1 block text-brand-800">Chủ sân phản hồi:</b>
                    <p>{review.owner_reply}</p>
                  </div>
                ) : null;
              })()}
            </aside>
          )}

        </div>
      ) : (
        <EmptyState
          title={tab === 'pending' ? "Không có booking cần đánh giá" : "Chưa có đánh giá nào"}
          description={tab === 'pending' ? "Booking đã hoàn thành và chưa đánh giá sẽ xuất hiện tại đây." : "Những booking bạn đã đánh giá sẽ xuất hiện tại đây."}
        />
      )}
    </>
  );
}
