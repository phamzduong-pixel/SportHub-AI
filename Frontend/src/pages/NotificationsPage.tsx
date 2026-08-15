import { Bell, CheckCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, EmptyState, LoadingSkeleton, PageHeader, useToast } from '@/components/common';
import { useAuth } from '@/contexts/AuthContext';
import { getNotifications, markAllNotificationsRead, markNotificationRead, type AppNotification } from '@/services/notificationService';

export function NotificationsPage() {
  const [items, setItems] = useState<AppNotification[]>([]); const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false);
  const { user } = useAuth(); const navigate = useNavigate(); const { toast } = useToast();
  useEffect(() => { getNotifications().then((result) => setItems(result.items)).catch((error) => toast(error instanceof Error ? error.message : 'Không tải được thông báo.', 'error')).finally(() => setLoading(false)); }, []);
  const open = async (item: AppNotification) => {
    if (!item.is_read) try { const updated = await markNotificationRead(item.id); setItems((current) => current.map((value) => value.id === item.id ? updated : value)); } catch { toast('Không thể đánh dấu thông báo đã đọc.', 'error'); }
    if (item.reference_type === 'booking' && item.reference_id) navigate(user?.role === 'OWNER' ? `/management/bookings/${item.reference_id}` : `/customer/bookings/${item.reference_id}`);
    else if (item.reference_type === 'partner_application') navigate(user?.role === 'SYSTEM_ADMIN' ? '/system-admin/partner-applications' : '/owner-application');
  };
  const readAll = async () => { setBusy(true); try { await markAllNotificationsRead(); setItems((current) => current.map((item) => ({ ...item, is_read: true, read_at: new Date().toISOString() }))); } catch { toast('Không thể đánh dấu tất cả đã đọc.', 'error'); } finally { setBusy(false); } };
  const unread = items.filter((item) => !item.is_read).length;
  return <main className="mx-auto w-full max-w-4xl px-3 py-6 sm:px-6"><PageHeader title="Thông báo" description="Các cập nhật nghiệp vụ dành riêng cho tài khoản của bạn." actions={unread > 0 ? <Button variant="outline" loading={busy} leftIcon={<CheckCheck size={16} />} onClick={() => void readAll()}>Đánh dấu tất cả đã đọc</Button> : undefined} />{loading ? <LoadingSkeleton lines={7} /> : items.length ? <div className="overflow-hidden rounded-card border bg-white">{items.map((item) => <button key={item.id} onClick={() => void open(item)} className={`block w-full border-b p-4 text-left transition last:border-b-0 hover:bg-slate-50 sm:p-5 ${item.is_read ? 'bg-white' : 'bg-brand-50/70'}`}><div className="flex gap-3"><span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${item.is_read ? 'bg-slate-200' : 'bg-brand-600'}`} /><div className="min-w-0"><div className="flex flex-wrap items-start justify-between gap-2"><h2 className="font-bold text-slate-900">{item.title}</h2><time className="text-xs text-slate-500">{new Date(item.created_at).toLocaleString('vi-VN')}</time></div><p className="mt-1 text-sm leading-6 text-slate-600">{item.message}</p></div></div></button>)}</div> : <EmptyState icon={<Bell />} title="Chưa có thông báo" description="Thông báo về booking, thanh toán và hồ sơ đối tác sẽ xuất hiện tại đây." />}</main>;
}
