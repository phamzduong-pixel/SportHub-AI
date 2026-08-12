import { AlertTriangle, ArrowLeft, Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Button, EmptyState, Input, LoadingSkeleton, Modal, PageHeader, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';
import type { OwnerApplicationStatus } from '@/types/auth';

interface PartnerApplication { id: number; customer_id: number; customer_name: string; customer_email: string; customer_phone: string | null; status: OwnerApplicationStatus; representative: Record<string, unknown>; venue: Record<string, unknown>; legal_confirmed: boolean; admin_note: string | null; rejection_reason: string | null; withdraw_reason: string | null; withdrawn_at: string | null; reviewed_by: number | null; reviewer_name: string | null; submitted_at: string | null; reviewed_at: string | null; created_at: string; updated_at: string; }
const labels: Record<OwnerApplicationStatus, string> = { DRAFT: 'Bản nháp', PENDING: 'Chờ xét duyệt', APPROVED: 'Đã duyệt', REJECTED: 'Từ chối', WITHDRAWN: 'Đã rút' };
const variant = (status: OwnerApplicationStatus) => status === 'APPROVED' ? 'success' : status === 'REJECTED' ? 'danger' : status === 'PENDING' ? 'warning' : 'neutral';
const show = (value: unknown) => Array.isArray(value) ? value.join(', ') : value ? String(value) : '—';

export function SystemAdminPartnerApplicationsPage() {
  const [items, setItems] = useState<PartnerApplication[]>([]);
  const [selected, setSelected] = useState<PartnerApplication>();
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [rejectionError, setRejectionError] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const { toast } = useToast();

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set('search', query.trim());
      if (status) params.set('status', status);
      if (from) params.set('submitted_from', from + 'T00:00:00');
      if (to) params.set('submitted_to', to + 'T23:59:59');
      setItems(await apiRequest<PartnerApplication[]>('/admin/owner-applications?' + params));
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Không tải được yêu cầu đối tác.', 'error');
    } finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, []);

  const review = async (action: 'APPROVE' | 'REJECT', note?: string) => {
    if (!selected) return false;
    setWorking(true);
    try {
      const updated = await apiRequest<PartnerApplication>('/admin/owner-applications/' + selected.id + '/review', {
        method: 'PATCH',
        body: JSON.stringify({ action, admin_note: note?.trim() || null }),
      });
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setSelected(updated);
      toast(action === 'APPROVE' ? 'Đã cấp quyền OWNER.' : 'Đã từ chối yêu cầu.', 'success');
      return true;
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Không thể xử lý yêu cầu.', 'error');
      return false;
    } finally { setWorking(false); }
  };

  const openRejectModal = () => {
    setRejectionReason('');
    setRejectionError('');
    setRejectOpen(true);
  };
  const closeRejectModal = () => {
    if (working) return;
    setRejectOpen(false);
    setRejectionError('');
  };
  const confirmReject = async () => {
    const reason = rejectionReason.trim();
    if (!reason) { setRejectionError('Vui lòng nhập lý do từ chối.'); return; }
    if (reason.length < 3) { setRejectionError('Lý do từ chối phải có ít nhất 3 ký tự.'); return; }
    setRejectionError('');
    if (await review('REJECT', reason)) {
      setRejectOpen(false);
      setRejectionReason('');
    }
  };

  return <div className="min-h-screen bg-slate-50">
    <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6">
      <Link to="/system-admin" className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-brand-700"><ArrowLeft size={16} />Dashboard hệ thống</Link>
      <PageHeader title="Yêu cầu trở thành OWNER" description="Xét duyệt thông tin cơ bản. Giấy phép và tài liệu xác minh được xử lý ở module Đăng ký cơ sở sau khi tài khoản thành OWNER." />
      <form onSubmit={(event) => { event.preventDefault(); void load(); }} className="mb-5 grid gap-3 rounded-card border bg-white p-4 md:grid-cols-[2fr_1fr_1fr_1fr_auto]">
        <Input value={query} onChange={(event) => setQuery(event.target.value)} leftIcon={<Search size={16} />} placeholder="Tên, email hoặc số điện thoại" />
        <select value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-lg border border-slate-300 px-3 text-sm"><option value="">Mọi trạng thái</option>{Object.entries(labels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
        <Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} title="Từ ngày" />
        <Input type="date" value={to} onChange={(event) => setTo(event.target.value)} title="Đến ngày" />
        <Button type="submit">Lọc</Button>
      </form>
      {loading ? <LoadingSkeleton lines={8} /> : items.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{items.map((item) => <article key={item.id} className="rounded-card border bg-white p-5"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><h2 className="truncate font-bold">{item.customer_name}</h2><p className="truncate text-sm text-slate-500">{item.customer_email}</p><p className="text-sm text-slate-500">{item.customer_phone || 'Chưa có SĐT'}</p></div><Badge variant={variant(item.status)}>{labels[item.status]}</Badge></div><div className="mt-4 border-t pt-4 text-sm"><b>{show(item.venue.name)}</b><p className="mt-1 line-clamp-2 text-slate-500">{show(item.venue.address)}</p><p className="mt-3 text-xs text-slate-400">{item.submitted_at ? 'Gửi ' + new Date(item.submitted_at).toLocaleString('vi-VN') : 'Chưa gửi xét duyệt'}</p></div><Button className="mt-4 w-full" variant="outline" onClick={() => setSelected(item)}>Xem chi tiết</Button></article>)}</div> : <EmptyState title="Không có yêu cầu phù hợp" description="Hãy thay đổi bộ lọc hoặc chờ CUSTOMER gửi yêu cầu." />}
    </main>

    {selected && <div className="fixed inset-0 z-40 flex justify-end bg-slate-950/50" onMouseDown={() => !rejectOpen && setSelected(undefined)}>
      <aside className="h-full w-full max-w-2xl overflow-y-auto bg-white p-4 pb-28 shadow-2xl sm:p-6" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between"><div><p className="text-xs font-bold uppercase text-brand-700">Yêu cầu #{selected.id}</p><h2 className="text-xl font-black">{selected.customer_name}</h2></div><button onClick={() => setSelected(undefined)} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Đóng"><X /></button></div>
        <Badge className="mt-3" variant={variant(selected.status)}>{labels[selected.status]}</Badge>
        <Detail title="Người đại diện" rows={[['Họ tên', selected.representative.name], ['Email đăng ký', selected.representative.email], ['Điện thoại', selected.representative.phone]]} />
        <Detail title="Cơ sở dự kiến" rows={[['Tên cơ sở', selected.venue.name], ['Địa chỉ sơ bộ', selected.venue.address], ['Tỉnh/thành', selected.venue.city], ['Quận/huyện/khu vực', selected.venue.district], ['Mô tả / lý do', selected.venue.description]]} />
        <Detail title="Tiến trình xét duyệt" rows={[['Ngày gửi', selected.submitted_at ? new Date(selected.submitted_at).toLocaleString('vi-VN') : null], ['Ngày xét duyệt', selected.reviewed_at ? new Date(selected.reviewed_at).toLocaleString('vi-VN') : null], ['Người xét duyệt', selected.reviewer_name]]} />
        {(selected.admin_note || selected.rejection_reason) && <div className="mt-5 rounded-xl bg-amber-50 p-4"><b>Phản hồi xét duyệt</b><p className="mt-1 text-sm">{selected.rejection_reason || selected.admin_note}</p></div>}
        {selected.status === 'PENDING' && <div className="fixed bottom-0 right-0 flex w-full max-w-2xl gap-2 border-t bg-white p-4 shadow-lg"><Button loading={working} onClick={() => void review('APPROVE')}>Duyệt và cấp OWNER</Button><Button disabled={working} variant="danger" onClick={openRejectModal}>Từ chối</Button></div>}
      </aside>
    </div>}

    <RejectOwnerApplicationModal open={rejectOpen} customerName={selected?.customer_name || ''} reason={rejectionReason} error={rejectionError} loading={working} onReasonChange={(value) => { setRejectionReason(value); if (rejectionError) setRejectionError(''); }} onClose={closeRejectModal} onConfirm={() => void confirmReject()} />
  </div>;
}

function Detail({ title, rows }: { title: string; rows: [string, unknown][] }) {
  return <section className="mt-6"><h3 className="border-b pb-2 font-bold">{title}</h3><dl className="mt-3 grid gap-2 text-sm sm:grid-cols-[150px_1fr]">{rows.map(([label, value]) => <div className="contents" key={label}><dt className="text-slate-500">{label}</dt><dd className="break-words font-medium">{show(value)}</dd></div>)}</dl></section>;
}

function RejectOwnerApplicationModal({ open, customerName, reason, error, loading, onReasonChange, onClose, onConfirm }: { open: boolean; customerName: string; reason: string; error: string; loading: boolean; onReasonChange: (value: string) => void; onClose: () => void; onConfirm: () => void }) {
  return <Modal open={open} onClose={onClose} title="Từ chối yêu cầu trở thành đối tác" description={'CUSTOMER đang được xét duyệt: ' + customerName}>
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 sm:p-4"><div className="flex items-start gap-2"><AlertTriangle className="mt-0.5 shrink-0" size={18} /><p>Lý do này sẽ được hiển thị cho CUSTOMER để họ chỉnh sửa và gửi lại yêu cầu.</p></div></div>
    <label className="mt-4 block text-sm font-semibold text-slate-700" htmlFor="owner-rejection-reason">Lý do từ chối <span className="text-red-600">*</span></label>
    <textarea id="owner-rejection-reason" autoFocus required maxLength={1000} aria-invalid={Boolean(error)} aria-describedby={error ? 'owner-rejection-error' : undefined} value={reason} onChange={(event) => onReasonChange(event.target.value)} placeholder="Ví dụ: Thông tin liên hệ chưa đầy đủ hoặc tên cơ sở dự kiến chưa rõ ràng..." className={'mt-2 min-h-32 w-full resize-y rounded-xl border bg-white px-3 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-brand-500 focus:ring-4 focus:ring-brand-50 ' + (error ? 'border-red-400' : 'border-slate-300')} />
    <div className="mt-1 flex items-start justify-between gap-3 text-xs"><span id="owner-rejection-error" className={error ? 'font-medium text-red-600' : 'text-slate-500'}>{error || 'Bắt buộc, tối thiểu 3 ký tự.'}</span><span className="shrink-0 text-slate-400">{reason.length}/1000</span></div>
    <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button className="w-full sm:w-auto" type="button" variant="outline" disabled={loading} onClick={onClose}>Hủy</Button><Button className="w-full sm:w-auto" type="button" variant="danger" loading={loading} leftIcon={<AlertTriangle size={17} />} onClick={onConfirm}>Xác nhận từ chối</Button></div>
  </Modal>;
}