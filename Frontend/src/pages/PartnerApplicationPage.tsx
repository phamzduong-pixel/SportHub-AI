import { AlertTriangle, ArrowLeft, Building2, CheckCircle2, Clock3, RotateCcw, Save, Send, Store, UserRound } from 'lucide-react';
import { type FormEvent, type ReactNode, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Button, Input, LoadingSkeleton, Modal, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';

type Status = 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'WITHDRAWN';
interface Application { id: number; status: Status; representative: Record<string, unknown>; venue: Record<string, unknown>; legal_confirmed: boolean; rejection_reason: string | null; admin_note: string | null; submitted_at: string | null; withdrawn_at: string | null; withdraw_reason: string | null; }
const blank = { representative: { name: '', phone: '', email: '' }, venue: { name: '', address: '', city: '', district: '', description: '' }, legal_confirmed: false };
type Form = typeof blank;
type Errors = Partial<Record<'name' | 'phone' | 'email' | 'venueName' | 'address' | 'description' | 'legal', string>>;
const labels: Record<Status, string> = { DRAFT: 'Bản nháp', PENDING: 'Đang chờ xét duyệt', APPROVED: 'Đã trở thành OWNER', REJECTED: 'Đã bị từ chối', WITHDRAWN: 'Đã rút yêu cầu' };

function clean(value: Form): Form { return { representative: { name: value.representative.name.trim(), phone: value.representative.phone.trim(), email: value.representative.email.trim().toLowerCase() }, venue: { name: value.venue.name.trim(), address: value.venue.address.trim(), city: value.venue.city.trim(), district: value.venue.district.trim(), description: value.venue.description.trim() }, legal_confirmed: value.legal_confirmed }; }
function validate(value: Form, submit = false): Errors {
  const errors: Errors = {};
  if (value.representative.name.length < 2) errors.name = 'Vui lòng nhập họ tên/người đại diện.';
  if (!/^\+?[0-9 ]{8,20}$/.test(value.representative.phone)) errors.phone = 'Số điện thoại chưa hợp lệ.';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.representative.email)) errors.email = 'Email chưa hợp lệ.';
  if (value.venue.name.length < 2) errors.venueName = 'Vui lòng nhập tên cơ sở dự kiến.';
  if (value.venue.address.length < 5) errors.address = 'Vui lòng nhập khu vực hoặc địa chỉ sơ bộ.';
  if (value.venue.description.length < 5) errors.description = 'Vui lòng mô tả ngắn hoặc nêu lý do đăng ký.';
  if (submit && !value.legal_confirmed) errors.legal = 'Vui lòng xác nhận thông tin trước khi gửi.';
  return errors;
}

export function PartnerApplicationPage() {
  const [application, setApplication] = useState<Application>();
  const [form, setForm] = useState<Form>(blank); const [errors, setErrors] = useState<Errors>({});
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false);
  const [withdrawOpen, setWithdrawOpen] = useState(false); const [withdrawReason, setWithdrawReason] = useState('');
  const { toast } = useToast();
  const useApplication = (item: Application) => { setApplication(item); setForm({ representative: { ...blank.representative, ...item.representative } as Form['representative'], venue: { ...blank.venue, ...item.venue } as Form['venue'], legal_confirmed: item.status === 'REJECTED' ? false : item.legal_confirmed }); };
  useEffect(() => { apiRequest<Application>('/auth/owner-application').then(useApplication).catch(() => undefined).finally(() => setLoading(false)); }, []);

  const saveOrSubmit = async (submitting: boolean) => {
    const next = clean(form); const nextErrors = validate(next, submitting); setForm(next); setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return toast('Vui lòng kiểm tra thông tin được đánh dấu.', 'error');
    setBusy(true);
    try {
      const item = await apiRequest<Application>(submitting ? '/auth/owner-application/submit' : '/auth/owner-application', { method: submitting ? 'POST' : 'PUT', body: JSON.stringify(next) });
      useApplication(item); toast(submitting ? 'Yêu cầu đã được gửi và đang chờ xét duyệt.' : 'Đã lưu bản nháp.', 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không xử lý được yêu cầu.', 'error'); } finally { setBusy(false); }
  };
  const withdraw = async () => {
    if (!application) return; setBusy(true);
    try { const item = await apiRequest<Application>('/auth/owner-application/' + application.id + '/withdraw', { method: 'POST', body: JSON.stringify({ reason: withdrawReason.trim() || null }) }); useApplication(item); setWithdrawOpen(false); toast('Đã rút yêu cầu.', 'success'); }
    catch (error) { toast(error instanceof Error ? error.message : 'Không rút được yêu cầu.', 'error'); } finally { setBusy(false); }
  };
  const reapply = async () => { setBusy(true); try { useApplication(await apiRequest<Application>('/auth/owner-application/reapply', { method: 'POST' })); toast('Đã tạo yêu cầu mới.', 'success'); } catch (error) { toast(error instanceof Error ? error.message : 'Không thể đăng ký lại.', 'error'); } finally { setBusy(false); } };

  if (loading) return <Shell><LoadingSkeleton lines={8} /></Shell>;
  if (application?.status === 'PENDING' || application?.status === 'APPROVED') {
    const approved = application.status === 'APPROVED';
    return <Shell><section className="px-5 py-12 text-center sm:px-10"><span className={'mx-auto grid h-20 w-20 place-items-center rounded-full ' + (approved ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700')}>{approved ? <CheckCircle2 size={40} /> : <Clock3 size={40} />}</span><Badge className="mt-4" variant={approved ? 'success' : 'warning'}>{labels[application.status]}</Badge><h2 className="mt-3 text-2xl font-black">{approved ? 'Tài khoản đã được cấp quyền OWNER' : 'Yêu cầu đang chờ System Admin xử lý'}</h2><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">{approved ? 'Bạn có thể vào trang quản lý để đăng ký cơ sở. Giấy phép, ảnh và tài liệu xác minh thuộc luồng đăng ký cơ sở.' : 'Đây chỉ là yêu cầu cấp quyền OWNER và không yêu cầu CCCD, giấy phép hay ảnh cơ sở.'}</p><div className="mt-6">{approved ? <Link to="/management/dashboard"><Button leftIcon={<Store size={17} />}>Vào trang quản lý</Button></Link> : <Button variant="outline" onClick={() => setWithdrawOpen(true)}>Rút yêu cầu</Button>}</div><Details application={application} /></section><Withdraw open={withdrawOpen} busy={busy} reason={withdrawReason} onReason={setWithdrawReason} onClose={() => setWithdrawOpen(false)} onConfirm={withdraw} /></Shell>;
  }
  if (application?.status === 'WITHDRAWN') return <Shell><section className="px-5 py-12 text-center"><AlertTriangle className="mx-auto text-slate-500" size={44} /><h2 className="mt-4 text-2xl font-black">Yêu cầu đã được rút</h2><p className="mt-2 text-sm text-slate-600">Bạn có thể tạo yêu cầu mới từ thông tin cơ bản trước đó.</p><Button className="mt-6" loading={busy} leftIcon={<RotateCcw size={17} />} onClick={reapply}>Đăng ký lại</Button></section></Shell>;

  const rep = (value: Partial<Form['representative']>) => setForm((current) => ({ ...current, representative: { ...current.representative, ...value } }));
  const venue = (value: Partial<Form['venue']>) => setForm((current) => ({ ...current, venue: { ...current.venue, ...value } }));
  return <Shell>{application?.status === 'REJECTED' && <div className="mx-5 mt-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-800 sm:mx-10"><b>Yêu cầu đã bị từ chối</b><p className="mt-1 text-sm">Lý do: {application.rejection_reason || application.admin_note || 'Không có lý do.'}</p><p className="mt-2 text-xs">Bạn có thể chỉnh sửa thông tin và gửi lại.</p></div>}
    <form onSubmit={(event: FormEvent) => { event.preventDefault(); void saveOrSubmit(true); }} className="space-y-6 px-5 py-7 sm:px-10 sm:py-9">
      <Section icon={<UserRound />} title="Thông tin người đại diện"><div className="grid gap-4 sm:grid-cols-2"><Input required label="Họ tên / người đại diện" value={form.representative.name} error={errors.name} onChange={(event) => rep({ name: event.target.value })} /><Input required label="Số điện thoại" value={form.representative.phone} error={errors.phone} onChange={(event) => rep({ phone: event.target.value })} /><Input required className="sm:col-span-2" type="email" label="Email" value={form.representative.email} error={errors.email} onChange={(event) => rep({ email: event.target.value })} /></div></Section>
      <Section icon={<Building2 />} title="Thông tin cơ sở dự kiến"><div className="grid gap-4 sm:grid-cols-2"><Input required className="sm:col-span-2" label="Tên cơ sở dự kiến" value={form.venue.name} error={errors.venueName} onChange={(event) => venue({ name: event.target.value })} /><Input label="Tỉnh / thành phố" value={form.venue.city} onChange={(event) => venue({ city: event.target.value })} /><Input label="Quận / huyện / khu vực" value={form.venue.district} onChange={(event) => venue({ district: event.target.value })} /><Input required className="sm:col-span-2" label="Địa chỉ sơ bộ" value={form.venue.address} error={errors.address} onChange={(event) => venue({ address: event.target.value })} /><label className="text-sm font-medium text-slate-700 sm:col-span-2">Mô tả ngắn / lý do đăng ký <span className="text-red-500">*</span><textarea className={'mt-1.5 min-h-28 w-full rounded-xl border px-3 py-3 outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-50 ' + (errors.description ? 'border-red-400' : 'border-slate-300')} value={form.venue.description} onChange={(event) => venue({ description: event.target.value })} />{errors.description && <span className="mt-1 block text-xs text-red-600">{errors.description}</span>}</label></div></Section>
      <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-900"><b>Không cần giấy tờ ở bước này.</b><br />Giấy phép, ảnh cơ sở và tài liệu xác minh sẽ được xử lý trong module Đăng ký cơ sở sau khi tài khoản trở thành OWNER.</div>
      <label className="flex items-start gap-3 rounded-2xl border p-4 text-sm"><input type="checkbox" className="mt-1 h-4 w-4 accent-emerald-600" checked={form.legal_confirmed} onChange={(event) => setForm((current) => ({ ...current, legal_confirmed: event.target.checked }))} /><span>Tôi xác nhận các thông tin cơ bản trên là chính xác.{errors.legal && <small className="mt-1 block text-red-600">{errors.legal}</small>}</span></label>
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button type="button" variant="outline" loading={busy} leftIcon={<Save size={17} />} onClick={() => void saveOrSubmit(false)}>Lưu nháp</Button><Button type="submit" loading={busy} leftIcon={<Send size={17} />}>Gửi yêu cầu</Button></div>
    </form></Shell>;
}
function Shell({ children }: { children: ReactNode }) { return <div className="mx-auto w-full max-w-4xl pb-8"><div className="overflow-hidden rounded-2xl border bg-white shadow-sm sm:rounded-[28px]"><header className="border-b bg-gradient-to-br from-brand-50 via-white to-sportblue-50 px-5 py-7 sm:px-10"><Link to="/customer/dashboard" className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-brand-700"><ArrowLeft size={17} />Quay lại hệ thống</Link><span className="block text-xs font-bold uppercase tracking-wide text-brand-700">Đăng ký đối tác SportHub AI</span><h1 className="mt-2 text-3xl font-black">Trở thành đối tác</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Gửi thông tin cơ bản để System Admin xem xét cấp quyền OWNER. Đây chưa phải bước xác minh cơ sở.</p></header>{children}</div></div>; }
function Section({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) { return <section><h2 className="mb-4 flex items-center gap-2 text-lg font-bold"><span className="text-brand-700 [&>svg]:h-5 [&>svg]:w-5">{icon}</span>{title}</h2><div className="rounded-2xl border bg-slate-50/60 p-4 sm:p-6">{children}</div></section>; }
function Details({ application }: { application: Application }) { return <dl className="mx-auto mt-8 grid max-w-2xl gap-3 rounded-2xl border bg-slate-50 p-5 text-left text-sm sm:grid-cols-2"><Info label="Người đại diện" value={application.representative.name} /><Info label="Điện thoại" value={application.representative.phone} /><Info label="Email" value={application.representative.email} /><Info label="Cơ sở dự kiến" value={application.venue.name} /><Info label="Khu vực / địa chỉ" value={[application.venue.address, application.venue.district, application.venue.city].filter(Boolean).join(', ')} /><Info label="Mô tả / lý do" value={application.venue.description} /></dl>; }
function Info({ label, value }: { label: string; value: unknown }) { return <div><dt className="text-slate-500">{label}</dt><dd className="mt-1 font-semibold">{value ? String(value) : '—'}</dd></div>; }
function Withdraw({ open, busy, reason, onReason, onClose, onConfirm }: { open: boolean; busy: boolean; reason: string; onReason: (value: string) => void; onClose: () => void; onConfirm: () => void }) { return <Modal open={open} onClose={onClose} title="Rút yêu cầu trở thành OWNER"><label className="text-sm font-medium">Lý do (không bắt buộc)<textarea className="mt-2 min-h-24 w-full rounded-xl border p-3" value={reason} onChange={(event) => onReason(event.target.value)} /></label><div className="mt-5 flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Đóng</Button><Button variant="danger" loading={busy} onClick={onConfirm}>Xác nhận rút</Button></div></Modal>; }