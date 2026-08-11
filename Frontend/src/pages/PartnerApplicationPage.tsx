import {
  AlertTriangle, ArrowLeft, Building2, Camera, Check, CheckCircle2, ChevronLeft, ChevronRight, ClipboardCheck,
  Clock3, Eye, FileCheck2, IdCard, Mail, MapPin, Pencil, Phone, RotateCcw, Save, ShieldCheck,
  Store, Trash2, Upload, UserRound,
} from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Button, Input, LoadingSkeleton, Modal, useToast } from '@/components/common';
import { useAuth } from '@/contexts/AuthContext';
import { ApiError, apiBlob, apiRequest } from '@/services/apiClient';

type Status = 'DRAFT' | 'PENDING_REVIEW' | 'NEED_MORE_INFO' | 'APPROVED' | 'REJECTED' | 'WITHDRAWN';
interface Application { id: number; status: Status; representative: Record<string, unknown>; venue: Record<string, unknown>; legal_confirmed: boolean; admin_note: string | null; rejection_reason: string | null; submitted_at: string | null; withdrawn_at: string | null; withdraw_reason: string | null; has_document: boolean; document_file_name: string | null; document_mime: string | null; document_size: number | null; document_uploaded_at: string | null; }
type Errors = Record<string, string>;

const sports = ['Bóng đá', 'Cầu lông', 'Tennis', 'Pickleball', 'Bóng rổ', 'Bóng chuyền'];
const labels: Record<Status, string> = { DRAFT: 'Bản nháp', PENDING_REVIEW: 'Đang chờ xét duyệt', NEED_MORE_INFO: 'Cần bổ sung thông tin', APPROVED: 'Đã trở thành đối tác', REJECTED: 'Chưa được chấp thuận', WITHDRAWN: 'Đã rút' };
const blank = { representative: { name: '', phone: '', email: '', identity_number: '' }, venue: { name: '', address: '', city: '', district: '', phone: '', sports: [] as string[], description: '' }, legal_confirmed: false };
const phonePattern = /^\+?[0-9 ]+$/;
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const identityPattern = /^[A-Za-z0-9-]+$/;

function sanitizeForm(value: typeof blank): typeof blank {
  return {
    representative: {
      name: value.representative.name.trim(), phone: value.representative.phone.trim(),
      email: value.representative.email.trim(), identity_number: value.representative.identity_number.trim(),
    },
    venue: {
      name: value.venue.name.trim(), address: value.venue.address.trim(), city: value.venue.city.trim(),
      district: value.venue.district.trim(), phone: value.venue.phone.trim(),
      sports: value.venue.sports.map((item) => item.trim()).filter(Boolean), description: value.venue.description.trim(),
    },
    legal_confirmed: value.legal_confirmed,
  };
}

function validateSteps(value: typeof blank, hasDocument: boolean, steps: number[]): Errors {
  const errors: Errors = {};
  if (steps.includes(1)) {
    if (value.representative.name.length < 2) errors.name = 'Vui lòng nhập ít nhất 2 ký tự.';
    if (value.representative.phone.length < 8) errors.phone = 'Vui lòng nhập ít nhất 8 ký tự.';
    else if (!phonePattern.test(value.representative.phone)) errors.phone = 'Chỉ nhập chữ số, khoảng trắng và dấu + ở đầu.';
    if (value.representative.email.length < 5) errors.email = 'Vui lòng nhập ít nhất 5 ký tự.';
    else if (!emailPattern.test(value.representative.email)) errors.email = 'Email không hợp lệ.';
  }
  if (steps.includes(2)) {
    if (value.venue.name.length < 2) errors.venueName = 'Vui lòng nhập ít nhất 2 ký tự.';
    if (value.venue.address.length < 5) errors.address = 'Vui lòng nhập ít nhất 5 ký tự.';
    if (!value.venue.sports.length) errors.sports = 'Chọn ít nhất một môn thể thao.';
    if (value.venue.phone && !phonePattern.test(value.venue.phone)) errors.venuePhone = 'Chỉ nhập chữ số, khoảng trắng và dấu + ở đầu.';
  }
  if (steps.includes(3)) {
    if (value.representative.identity_number.length < 6) errors.identity = 'Vui lòng nhập ít nhất 6 ký tự.';
    else if (!identityPattern.test(value.representative.identity_number)) errors.identity = 'Chỉ nhập chữ cái, chữ số và dấu gạch ngang.';
    if (!hasDocument) errors.document = 'Vui lòng tải ảnh giấy tờ xác minh.';
  }
  if (steps.includes(4) && !value.legal_confirmed) errors.legal = 'Vui lòng xác nhận tính chính xác của hồ sơ.';
  return errors;
}

function firstErrorStep(errors: Errors): number {
  if (['name', 'phone', 'email'].some((key) => errors[key])) return 1;
  if (['venueName', 'address', 'sports', 'venuePhone'].some((key) => errors[key])) return 2;
  if (['identity', 'document'].some((key) => errors[key])) return 3;
  return 4;
}

function errorsFromApi(error: unknown): Errors {
  if (!(error instanceof ApiError)) return {};
  const fieldByPath: Record<string, string> = {
    'representative.name': 'name', 'representative.phone': 'phone', 'representative.email': 'email',
    'representative.identity_number': 'identity', 'venue.name': 'venueName', 'venue.address': 'address',
    'venue.phone': 'venuePhone', 'venue.sports': 'sports', legal_confirmed: 'legal',
  };
  const result: Errors = {};
  error.validationIssues.forEach((issue) => {
    const path = issue.loc.filter((item) => item !== 'body').join('.');
    const field = fieldByPath[path];
    if (!field) return;
    const minimum = Number(issue.ctx?.min_length);
    if (field === 'address') result[field] = 'Vui lòng nhập ít nhất 5 ký tự.';
    else if (issue.type === 'string_too_short' && minimum) result[field] = `Vui lòng nhập ít nhất ${minimum} ký tự.`;
    else if (field === 'email') result[field] = 'Email không hợp lệ.';
    else if (field === 'sports') result[field] = 'Chọn ít nhất một môn thể thao.';
    else if (field === 'phone' || field === 'venuePhone') result[field] = 'Số điện thoại không hợp lệ.';
    else if (field === 'identity') result[field] = 'Số giấy tờ không hợp lệ.';
    else result[field] = 'Thông tin này chưa hợp lệ.';
  });
  return result;
}
const stepItems = [
  { title: 'Đại diện', description: 'Thông tin liên hệ', icon: UserRound },
  { title: 'Cơ sở', description: 'Địa điểm & môn chơi', icon: Building2 },
  { title: 'Xác minh', description: 'Giấy tờ xác thực', icon: ShieldCheck },
  { title: 'Xem lại', description: 'Kiểm tra & gửi', icon: ClipboardCheck },
];

export function PartnerApplicationPage() {
  const { user, refreshUser } = useAuth();
  const { toast } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const previewRef = useRef<string | undefined>(undefined);
  const [application, setApplication] = useState<Application>({ id: 0, status: 'DRAFT', representative: {}, venue: {}, legal_confirmed: false, admin_note: null, rejection_reason: null, submitted_at: null, withdrawn_at: null, withdraw_reason: null, has_document: false, document_file_name: null, document_mime: null, document_size: null, document_uploaded_at: null });
  const [form, setForm] = useState(blank);
  const [step, setStep] = useState(1);
  const [furthestStep, setFurthestStep] = useState(1);
  const [preview, setPreview] = useState<string>();
  const [errors, setErrors] = useState<Errors>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [withdrawReason, setWithdrawReason] = useState('');
  const [showStatusDetails, setShowStatusDetails] = useState(false);

  const replacePreview = (url?: string) => {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = url;
    setPreview(url);
  };

  useEffect(() => {
    apiRequest<Application>('/auth/owner-application').then((item) => {
      const nextForm = {
        representative: { ...blank.representative, ...item.representative } as typeof blank.representative,
        venue: { ...blank.venue, ...item.venue, sports: Array.isArray(item.venue.sports) ? item.venue.sports as string[] : [] } as typeof blank.venue,
        legal_confirmed: item.legal_confirmed,
      };
      setApplication(item); setForm(nextForm);
      const repComplete = Boolean(nextForm.representative.name && nextForm.representative.phone && nextForm.representative.email);
      const venueComplete = Boolean(nextForm.venue.name && nextForm.venue.address && nextForm.venue.sports.length);
      const verificationComplete = Boolean(nextForm.representative.identity_number && item.has_document);
      setFurthestStep(verificationComplete ? 4 : venueComplete ? 3 : repComplete ? 2 : 1);
      if (item.has_document) apiBlob('/auth/owner-application/document').then((blob) => replacePreview(URL.createObjectURL(blob))).catch(() => undefined);
      if (item.status === 'APPROVED' && user?.role !== 'OWNER') void refreshUser();
    }).catch(() => setForm({ ...blank, representative: { ...blank.representative, name: user?.full_name || '', phone: user?.phone || '', email: user?.email || '' } })).finally(() => setLoading(false));
    return () => { if (previewRef.current) URL.revokeObjectURL(previewRef.current); };
  }, []);

  const rep = (values: Partial<typeof form.representative>) => { setForm((current) => ({ ...current, representative: { ...current.representative, ...values } })); setErrors({}); };
  const venue = (values: Partial<typeof form.venue>) => { setForm((current) => ({ ...current, venue: { ...current.venue, ...values } })); setErrors({}); };
  const saveDraft = async () => { const sanitized = sanitizeForm(form); setForm(sanitized); setBusy(true); try { const nextApplication = await apiRequest<Application>('/auth/owner-application', { method: 'PUT', body: JSON.stringify(sanitized) }); setApplication(nextApplication); toast('Đã lưu bản nháp hồ sơ.', 'success'); return true; } catch (error) { toast(error instanceof Error ? error.message : 'Không lưu được bản nháp.', 'error'); return false; } finally { setBusy(false); } };
  const upload = async (file?: File) => { if (!file) return; if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return toast('Chỉ hỗ trợ ảnh JPG, PNG hoặc WEBP.', 'error'); if (file.size > 5 * 1024 * 1024) return toast('Ảnh giấy tờ không được vượt quá 5 MB.', 'error'); const body = new FormData(); body.append('document', file); setBusy(true); try { const nextApplication = await apiRequest<Application>('/auth/owner-application/document', { method: 'POST', body }); setApplication(nextApplication); replacePreview(URL.createObjectURL(file)); setErrors({}); toast('Đã tải ảnh giấy tờ lên an toàn.', 'success'); } catch (error) { toast(error instanceof Error ? error.message : 'Không tải được ảnh giấy tờ.', 'error'); } finally { setBusy(false); if (fileInput.current) fileInput.current.value = ''; } };
  const removeDocument = async () => { setBusy(true); try { const nextApplication = await apiRequest<Application>('/auth/owner-application/document', { method: 'DELETE' }); setApplication(nextApplication); replacePreview(); toast('Đã xóa ảnh giấy tờ.', 'success'); } catch (error) { toast(error instanceof Error ? error.message : 'Không xóa được ảnh.', 'error'); } finally { setBusy(false); } };

  const validateCurrentStep = () => {
    const sanitized = sanitizeForm(form);
    const nextErrors = validateSteps(sanitized, application.has_document, [step]);
    setForm(sanitized);
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };
  const next = async () => { if (!validateCurrentStep()) return toast('Vui lòng kiểm tra các thông tin được đánh dấu.', 'error'); if (await saveDraft()) { const target = Math.min(4, step + 1); setFurthestStep((value) => Math.max(value, target)); setStep(target); window.scrollTo({ top: 0, behavior: 'smooth' }); } };
  const goToStep = (target: number) => { if (target <= furthestStep) { setErrors({}); setStep(target); window.scrollTo({ top: 0, behavior: 'smooth' }); } };
  const submit = async (event: FormEvent) => { event.preventDefault(); if (busy) return; const sanitized = sanitizeForm(form); const nextErrors = validateSteps(sanitized, application.has_document, [1, 2, 3, 4]); setForm(sanitized); setErrors(nextErrors); if (Object.keys(nextErrors).length) { setStep(firstErrorStep(nextErrors)); return toast('Vui lòng kiểm tra các thông tin được đánh dấu.', 'error'); } setBusy(true); try { const nextApplication = await apiRequest<Application>('/auth/owner-application/submit', { method: 'POST', body: JSON.stringify(sanitized) }); setApplication(nextApplication); toast('Yêu cầu trở thành đối tác đã được gửi và đang chờ xét duyệt.', 'success'); } catch (error) { const backendErrors = errorsFromApi(error); if (Object.keys(backendErrors).length) { setErrors(backendErrors); setStep(firstErrorStep(backendErrors)); toast('Vui lòng kiểm tra các thông tin được đánh dấu.', 'error'); } else toast(error instanceof Error ? error.message : 'Không gửi được hồ sơ.', 'error'); } finally { setBusy(false); } };

  const withdraw = async () => {
    setBusy(true);
    try {
      const updated = await apiRequest<Application>(`/auth/owner-application/${application.id}/withdraw`, {
        method: 'POST', body: JSON.stringify({ reason: withdrawReason.trim() || null }),
      });
      setApplication(updated); setWithdrawOpen(false); setWithdrawReason(''); setShowStatusDetails(false);
      toast('Đã rút hồ sơ đăng ký đối tác.', 'success');
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Không thể rút hồ sơ.', 'error');
    } finally { setBusy(false); }
  };
  const reapply = async () => {
    setBusy(true);
    try {
      const created = await apiRequest<Application>('/auth/owner-application/reapply', { method: 'POST' });
      const nextForm = {
        representative: { ...blank.representative, ...created.representative } as typeof blank.representative,
        venue: { ...blank.venue, ...created.venue, sports: Array.isArray(created.venue.sports) ? created.venue.sports as string[] : [] } as typeof blank.venue,
        legal_confirmed: false,
      };
      replacePreview(); setApplication(created); setForm(nextForm); setStep(1); setFurthestStep(1); setErrors({});
      toast('Đã tạo hồ sơ đăng ký mới. Thông tin cũ được giữ trong lịch sử.', 'success');
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Không thể tạo hồ sơ đăng ký mới.', 'error');
    } finally { setBusy(false); }
  };

  if (loading) return <div className="mx-auto max-w-5xl"><LoadingSkeleton lines={9} /></div>;
  if (application.status === 'PENDING_REVIEW' || application.status === 'APPROVED') return <><PageShell subtitle="Theo dõi tiến trình xét duyệt hồ sơ chủ sân."><ApplicationStatusCard application={application} detailsOpen={showStatusDetails} onToggleDetails={() => setShowStatusDetails((value) => !value)} onWithdraw={application.status === 'PENDING_REVIEW' ? () => setWithdrawOpen(true) : undefined} /></PageShell><WithdrawDialog open={withdrawOpen} reason={withdrawReason} busy={busy} onReasonChange={setWithdrawReason} onClose={() => setWithdrawOpen(false)} onConfirm={() => void withdraw()} /></>;
  if (application.status === 'WITHDRAWN') return <PageShell subtitle="Hồ sơ đã được lưu lại trong lịch sử và không còn nằm trong hàng chờ xét duyệt."><WithdrawnCard application={application} busy={busy} onReapply={() => void reapply()} /></PageShell>;
  const notice = application.status === 'NEED_MORE_INFO' ? application.admin_note : application.status === 'REJECTED' ? application.rejection_reason || application.admin_note : null;

  return <><PageShell subtitle="Hoàn thiện từng bước, kiểm tra thông tin và gửi hồ sơ để bắt đầu kinh doanh cùng SportHub AI." progress={`Bước ${step} / 4`}>
    {notice && <div className={`mx-4 mt-5 rounded-2xl border p-4 sm:mx-8 lg:mx-10 ${application.status === 'REJECTED' ? 'border-red-200 bg-red-50 text-red-800' : 'border-amber-200 bg-amber-50 text-amber-900'}`}><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><b>{labels[application.status]}</b><p className="mt-1 text-sm">Phản hồi từ quản trị viên: {notice}</p></div>{application.status === 'NEED_MORE_INFO' && <Button type="button" variant="outline" className="w-full shrink-0 sm:w-auto" onClick={() => setWithdrawOpen(true)}>Rút hồ sơ</Button>}</div></div>}
    <Steps current={step} furthest={furthestStep} onSelect={goToStep} />
    <form noValidate onSubmit={submit}>
      <div className="mx-auto max-w-4xl px-4 py-6 sm:px-8 sm:py-8 lg:px-10">
        {step === 1 && <StepSection icon={<UserRound />} title="Thông tin người đại diện" description="Thông tin được dùng để SportHub liên hệ và xác minh hồ sơ của bạn.">
          <div className="grid gap-5 sm:grid-cols-2">
            <Input required className="h-11" label="Họ và tên" placeholder="Nguyễn Văn An" leftIcon={<UserRound size={18} />} value={form.representative.name} error={errors.name} onChange={(event) => rep({ name: event.target.value })} />
            <Input required className="h-11" label="Số điện thoại" placeholder="09xx xxx xxx" leftIcon={<Phone size={18} />} value={form.representative.phone} error={errors.phone} onChange={(event) => rep({ phone: event.target.value })} />
            <Input required className="h-11 sm:col-span-2" type="email" label="Email" hint="Đã điền từ hồ sơ tài khoản, bạn vẫn có thể chỉnh sửa." placeholder="ban@example.com" leftIcon={<Mail size={18} />} value={form.representative.email} error={errors.email} onChange={(event) => rep({ email: event.target.value })} />
          </div>
        </StepSection>}

        {step === 2 && <StepSection icon={<Building2 />} title="Thông tin cơ sở dự kiến" description="Cho chúng tôi biết địa điểm và loại hình thể thao bạn muốn vận hành.">
          <div className="grid gap-5 sm:grid-cols-2">
            <Input required className="h-11" label="Tên cơ sở" placeholder="Ví dụ: Sport Center Quận 7" leftIcon={<Building2 size={18} />} value={form.venue.name} error={errors.venueName} onChange={(event) => venue({ name: event.target.value })} />
            <Input required className="h-11" label="Địa chỉ" placeholder="Số nhà, tên đường" leftIcon={<MapPin size={18} />} value={form.venue.address} error={errors.address} onChange={(event) => venue({ address: event.target.value })} />
            <Input className="h-11" label="Tỉnh / thành phố" placeholder="TP. Hồ Chí Minh" value={form.venue.city} onChange={(event) => venue({ city: event.target.value })} />
            <Input className="h-11" label="Quận / huyện" placeholder="Quận 7" value={form.venue.district} onChange={(event) => venue({ district: event.target.value })} />
            <Input className="h-11" label="Số điện thoại cơ sở" placeholder="Số hotline (nếu có)" leftIcon={<Phone size={18} />} value={form.venue.phone} onChange={(event) => venue({ phone: event.target.value })} />
            <label className="text-sm font-medium text-slate-700">Môn thể thao dự kiến <span className="text-red-500">*</span><select multiple required className={`mt-1.5 min-h-32 w-full rounded-xl border bg-white px-3 py-2 outline-none transition focus:border-brand-500 focus:ring-4 focus:ring-brand-50 ${errors.sports ? 'border-red-400' : 'border-slate-300'}`} value={form.venue.sports} onChange={(event) => venue({ sports: Array.from(event.target.selectedOptions, (option) => option.value) })}>{sports.map((sport) => <option className="rounded-md px-2 py-1" key={sport}>{sport}</option>)}</select><span className={`mt-1 block text-xs ${errors.sports ? 'text-red-600' : 'text-slate-500'}`}>{errors.sports || 'Giữ Ctrl/Cmd để chọn nhiều môn.'}</span></label>
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">Mô tả ngắn<textarea className="mt-1.5 min-h-28 w-full resize-y rounded-xl border border-slate-300 bg-white px-3 py-3 outline-none transition placeholder:text-slate-400 focus:border-brand-500 focus:ring-4 focus:ring-brand-50" placeholder="Quy mô, tiện ích hoặc điểm nổi bật của cơ sở..." value={form.venue.description} onChange={(event) => venue({ description: event.target.value })} /></label>
          </div>
        </StepSection>}

        {step === 3 && <StepSection icon={<ShieldCheck />} title="Xác minh hồ sơ" description="Giấy tờ chỉ được dùng để quản trị viên xác minh đăng ký đối tác và được lưu trữ riêng tư.">
          <Input required className="h-11" label="Số giấy tờ / CCCD" placeholder="Nhập số trên giấy tờ" leftIcon={<IdCard size={18} />} value={form.representative.identity_number} error={errors.identity} onChange={(event) => rep({ identity_number: event.target.value })} />
          <div className={`mt-5 rounded-2xl border-2 border-dashed p-4 text-center transition sm:p-6 ${errors.document ? 'border-red-300 bg-red-50/40' : 'border-slate-300 bg-slate-50/60 hover:border-brand-300'}`}>
            <input ref={fileInput} className="sr-only" id="partner-document" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void upload(event.target.files?.[0])} />
            <input className="sr-only" id="partner-camera" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(event) => void upload(event.target.files?.[0])} />
            {preview ? <div><img src={preview} alt="Ảnh giấy tờ đã chọn" className="mx-auto max-h-80 max-w-full rounded-xl border bg-white object-contain shadow-sm" /><p className="mt-3 truncate text-sm font-semibold text-slate-700">{application.document_file_name}</p><div className="mt-4 flex flex-wrap justify-center gap-2"><UploadLabel htmlFor="partner-document" icon={<Upload size={17} />}>Thay từ thư viện</UploadLabel><UploadLabel htmlFor="partner-camera" icon={<Camera size={17} />}>Chụp lại</UploadLabel><Button type="button" variant="danger" leftIcon={<Trash2 size={17} />} onClick={() => void removeDocument()}>Xóa ảnh</Button></div></div> : <div><span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-700"><Upload size={25} /></span><b className="mt-3 block text-slate-800">Tải ảnh giấy tờ xác minh</b><span className="mt-1 block text-xs text-slate-500">JPG, PNG, WEBP · tối đa 5 MB</span><div className="mt-4 flex flex-col justify-center gap-2 sm:flex-row"><UploadLabel primary htmlFor="partner-document" icon={<Upload size={17} />}>Chọn từ thư viện</UploadLabel><UploadLabel htmlFor="partner-camera" icon={<Camera size={17} />}>Chụp ảnh</UploadLabel></div></div>}
            {errors.document && <p className="mt-2 text-xs font-medium text-red-600">{errors.document}</p>}
          </div>
        </StepSection>}

        {step === 4 && <div className="space-y-5">
          <StepSection icon={<FileCheck2 />} title="Xem lại hồ sơ" description="Kiểm tra lần cuối. Bạn có thể quay lại từng mục để chỉnh sửa trước khi gửi.">
            <div className="grid gap-4 lg:grid-cols-2">
              <Summary title="Người đại diện" icon={<UserRound size={18} />} onEdit={() => goToStep(1)} rows={[['Họ tên', form.representative.name], ['Email', form.representative.email], ['Điện thoại', form.representative.phone], ['Số giấy tờ', form.representative.identity_number]]} />
              <Summary title="Cơ sở" icon={<Building2 size={18} />} onEdit={() => goToStep(2)} rows={[['Tên cơ sở', form.venue.name], ['Địa chỉ', [form.venue.address, form.venue.district, form.venue.city].filter(Boolean).join(', ')], ['Môn thể thao', form.venue.sports.join(', ')], ['Mô tả', form.venue.description]]} />
            </div>
            <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4"><div className="flex items-center justify-between gap-3"><h3 className="flex items-center gap-2 font-bold text-slate-800"><ShieldCheck size={18} className="text-brand-600" />Giấy tờ xác minh</h3><button type="button" onClick={() => goToStep(3)} className="inline-flex items-center gap-1 text-sm font-semibold text-brand-700 hover:text-brand-800"><Pencil size={15} /> Sửa</button></div>{preview ? <img src={preview} alt="Ảnh giấy tờ" className="mt-4 max-h-64 max-w-full rounded-xl border bg-slate-50 object-contain" /> : <p className="mt-3 text-sm text-slate-500">Chưa có ảnh giấy tờ.</p>}</div>
          </StepSection>
          <label className={`flex cursor-pointer items-start gap-3 rounded-2xl border p-4 text-sm transition sm:p-5 ${form.legal_confirmed ? 'border-brand-300 bg-brand-50/60' : 'border-slate-200 bg-white hover:border-slate-300'}`}><input className="mt-0.5 h-5 w-5 shrink-0 accent-emerald-600" type="checkbox" checked={form.legal_confirmed} onChange={(event) => setForm((current) => ({ ...current, legal_confirmed: event.target.checked }))} /><span><b className="block text-slate-800">Xác nhận thông tin hồ sơ</b><span className="mt-1 block leading-6 text-slate-600">Tôi xác nhận thông tin cung cấp là chính xác và đồng ý để SportHub AI sử dụng cho mục đích xét duyệt đối tác.</span></span></label>
        </div>}
      </div>

      <div className="sticky bottom-[calc(4rem+env(safe-area-inset-bottom))] z-20 border-t border-slate-200 bg-white/95 px-4 py-3 shadow-[0_-8px_24px_rgba(15,23,42,0.06)] backdrop-blur sm:px-8 lg:bottom-0 lg:px-10">
        <div className="mx-auto flex max-w-4xl flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
          {step > 1 && <Button className="w-full sm:w-auto" type="button" variant="ghost" leftIcon={<ChevronLeft size={18} />} onClick={() => goToStep(step - 1)}>Quay lại</Button>}
          <Button className="w-full sm:w-auto" type="button" variant="outline" loading={busy} leftIcon={<Save size={17} />} onClick={() => void saveDraft()}>Lưu nháp</Button>
          {step < 4 ? <Button className="w-full sm:w-auto" type="button" size="lg" loading={busy} onClick={() => void next()}>Tiếp tục <ChevronRight size={18} /></Button> : <Button className="w-full sm:w-auto" type="submit" size="lg" loading={busy} leftIcon={<FileCheck2 size={18} />}>Gửi hồ sơ xét duyệt</Button>}
        </div>
      </div>
    </form>
  </PageShell><WithdrawDialog open={withdrawOpen} reason={withdrawReason} busy={busy} onReasonChange={setWithdrawReason} onClose={() => setWithdrawOpen(false)} onConfirm={() => void withdraw()} /></>;
}

function PageShell({ children, subtitle, progress }: { children: ReactNode; subtitle: string; progress?: string }) { return <div className="mx-auto w-full max-w-5xl pb-8"><div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm sm:rounded-[28px] sm:shadow-xl sm:shadow-slate-200/40"><header className="relative overflow-hidden border-b border-slate-100 bg-gradient-to-br from-brand-50 via-white to-sportblue-50 px-5 py-7 sm:px-8 sm:py-9 lg:px-10"><div className="absolute -right-16 -top-20 h-52 w-52 rounded-full bg-brand-100/50 blur-3xl" /><div className="relative"><Link to="/customer/dashboard" className="mb-5 inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-sm font-semibold text-slate-600 shadow-sm transition hover:border-brand-300 hover:bg-white hover:text-brand-700 focus:outline-none focus:ring-4 focus:ring-brand-100"><ArrowLeft size={17} /> Quay lại hệ thống</Link><div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div className="max-w-2xl"><span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white/80 px-3 py-1 text-xs font-bold uppercase tracking-wide text-brand-700"><Store size={14} /> Đăng ký đối tác SportHub</span><h1 className="mt-3 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">Trở thành đối tác</h1><p className="mt-2 max-w-xl text-sm leading-6 text-slate-600 sm:text-base">{subtitle}</p></div>{progress && <span className="w-fit rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white">{progress}</span>}</div></div></header>{children}</div></div>; }

function Steps({ current, furthest, onSelect }: { current: number; furthest: number; onSelect: (step: number) => void }) { return <nav aria-label="Tiến trình đăng ký" className="border-b border-slate-100 px-3 py-4 sm:px-8 sm:py-5 lg:px-10"><ol className="mx-auto grid max-w-4xl grid-cols-4">{stepItems.map(({ title, description, icon: Icon }, index) => { const number = index + 1; const completed = number < current || (number < furthest && number !== current); const active = number === current; const accessible = number <= furthest; return <li key={title} className="relative"><div className={`absolute left-1/2 right-[-50%] top-5 h-0.5 ${index === stepItems.length - 1 ? 'hidden' : ''} ${number < furthest ? 'bg-brand-400' : 'bg-slate-200'}`} /><button type="button" disabled={!accessible} aria-current={active ? 'step' : undefined} onClick={() => onSelect(number)} className="group relative z-10 flex w-full flex-col items-center px-1 text-center disabled:cursor-default"><span className={`grid h-10 w-10 place-items-center rounded-full border-2 transition sm:h-11 sm:w-11 ${active ? 'border-brand-600 bg-brand-600 text-white shadow-lg shadow-brand-200' : completed ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 bg-white text-slate-400'} ${accessible && !active ? 'group-hover:border-brand-400 group-hover:bg-brand-50' : ''}`}>{completed ? <Check size={19} strokeWidth={3} /> : <Icon size={18} />}</span><span className={`mt-2 text-[11px] font-bold sm:text-sm ${active ? 'text-brand-700' : completed ? 'text-slate-700' : 'text-slate-400'}`}>{title}</span><span className="mt-0.5 hidden text-xs text-slate-500 md:block">{description}</span></button></li>; })}</ol></nav>; }

function StepSection({ icon, title, description, children }: { icon: ReactNode; title: string; description: string; children: ReactNode }) { return <section><div className="mb-6 flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700 [&>svg]:h-5 [&>svg]:w-5">{icon}</span><div><h2 className="text-lg font-bold text-slate-900 sm:text-xl">{title}</h2><p className="mt-1 text-sm leading-5 text-slate-500">{description}</p></div></div><div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4 sm:p-6">{children}</div></section>; }
function UploadLabel({ htmlFor, icon, children, primary }: { htmlFor: string; icon: ReactNode; children: ReactNode; primary?: boolean }) { return <label htmlFor={htmlFor}><span className={`inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition sm:w-auto ${primary ? 'bg-brand-600 text-white shadow-sm hover:bg-brand-700' : 'border border-slate-300 bg-white text-slate-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700'}`}>{icon}{children}</span></label>; }
function Summary({ title, icon, rows, onEdit }: { title: string; icon: ReactNode; rows: [string, string][]; onEdit: () => void }) { return <section className="rounded-2xl border border-slate-200 bg-white p-4"><div className="flex items-center justify-between gap-3"><h3 className="flex items-center gap-2 font-bold text-slate-800"><span className="text-brand-600">{icon}</span>{title}</h3><button type="button" onClick={onEdit} className="inline-flex items-center gap-1 text-sm font-semibold text-brand-700 hover:text-brand-800"><Pencil size={15} /> Sửa</button></div><dl className="mt-4 space-y-3 text-sm">{rows.map(([label, value]) => <div key={label} className="grid grid-cols-[7rem_1fr] gap-2 border-t border-slate-100 pt-3 first:border-0 first:pt-0"><dt className="text-slate-500">{label}</dt><dd className="break-words font-medium text-slate-800">{value || '—'}</dd></div>)}</dl></section>; }
function ApplicationStatusCard({ application, detailsOpen, onToggleDetails, onWithdraw }: { application: Application; detailsOpen: boolean; onToggleDetails: () => void; onWithdraw?: () => void }) {
  const approved = application.status === 'APPROVED'; const Icon = approved ? CheckCircle2 : Clock3;
  return <section className="px-5 py-8 sm:px-8 sm:py-12"><div className="mx-auto max-w-3xl text-center"><span className={`mx-auto grid h-20 w-20 place-items-center rounded-full ${approved ? 'bg-brand-50 text-brand-700' : 'bg-amber-50 text-amber-700'}`}><Icon size={40} /></span><Badge className="mt-4" variant={approved ? 'success' : 'warning'}>{labels[application.status]}</Badge><h2 className="mt-3 text-xl font-bold text-slate-900">{approved ? 'Hồ sơ đã được phê duyệt' : 'Hồ sơ đang chờ xét duyệt'}</h2><p className="mt-2 text-sm text-slate-500">{application.submitted_at ? `Gửi lúc ${new Date(application.submitted_at).toLocaleString('vi-VN')}` : 'Hồ sơ đã được lưu.'}</p>
    {!approved && <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row"><Button variant="outline" leftIcon={<Eye size={17} />} onClick={onToggleDetails}>{detailsOpen ? 'Ẩn hồ sơ' : 'Xem hồ sơ'}</Button>{onWithdraw && <Button variant="ghost" className="text-red-600 hover:bg-red-50 hover:text-red-700" leftIcon={<AlertTriangle size={17} />} onClick={onWithdraw}>Rút hồ sơ</Button>}</div>}
    {approved && <div className="mx-auto mt-6 grid max-w-sm gap-2"><Link to="/management/dashboard"><Button className="w-full" leftIcon={<Store size={17} />}>Chuyển sang trang quản lý sân</Button></Link><Link to="/customer/dashboard"><Button className="w-full" variant="outline">Tiếp tục chế độ khách hàng</Button></Link></div>}
  </div>{detailsOpen && <div className="mx-auto mt-7 grid max-w-3xl gap-4 border-t border-slate-200 pt-6 md:grid-cols-2"><ReadOnlySummary title="Người đại diện" rows={[['Họ tên', application.representative.name], ['Email', application.representative.email], ['Điện thoại', application.representative.phone], ['Số giấy tờ', application.representative.identity_number]]} /><ReadOnlySummary title="Cơ sở đăng ký" rows={[['Tên cơ sở', application.venue.name], ['Địa chỉ', application.venue.address], ['Môn thể thao', application.venue.sports], ['Mô tả', application.venue.description]]} /></div>}</section>;
}

function WithdrawnCard({ application, busy, onReapply }: { application: Application; busy: boolean; onReapply: () => void }) { return <section className="px-5 py-10 sm:px-8 sm:py-14"><div className="mx-auto max-w-2xl text-center"><span className="mx-auto grid h-20 w-20 place-items-center rounded-full bg-slate-100 text-slate-600"><AlertTriangle size={36} /></span><Badge className="mt-4" variant="neutral">Đã rút</Badge><h2 className="mt-3 text-xl font-bold text-slate-900">Hồ sơ đã được rút</h2><p className="mt-2 text-sm leading-6 text-slate-500">Hồ sơ này không còn được quản trị viên xét duyệt nhưng vẫn được lưu trong lịch sử.</p><dl className="mx-auto mt-6 max-w-lg rounded-2xl border border-slate-200 bg-slate-50 p-4 text-left text-sm"><InfoRow label="Ngày gửi" value={application.submitted_at ? new Date(application.submitted_at).toLocaleString('vi-VN') : '—'} /><InfoRow label="Ngày rút" value={application.withdrawn_at ? new Date(application.withdrawn_at).toLocaleString('vi-VN') : '—'} />{application.withdraw_reason && <InfoRow label="Lý do" value={application.withdraw_reason} />}</dl><Button className="mt-6 w-full sm:w-auto" loading={busy} leftIcon={<RotateCcw size={17} />} onClick={onReapply}>Đăng ký lại</Button><p className="mt-3 text-xs text-slate-500">Một hồ sơ mới sẽ được tạo; hồ sơ đã rút vẫn được giữ nguyên.</p></div></section>; }

function WithdrawDialog({ open, reason, busy, onReasonChange, onClose, onConfirm }: { open: boolean; reason: string; busy: boolean; onReasonChange: (value: string) => void; onClose: () => void; onConfirm: () => void }) { return <Modal open={open} onClose={busy ? () => undefined : onClose} title="Rút hồ sơ đăng ký đối tác" description="Bạn có chắc muốn rút hồ sơ đăng ký đối tác? Sau khi rút, hồ sơ này sẽ không còn được quản trị viên xét duyệt."><label className="block text-sm font-medium text-slate-700">Lý do rút hồ sơ <span className="font-normal text-slate-400">(không bắt buộc)</span><textarea autoFocus maxLength={1000} className="mt-2 min-h-28 w-full resize-y rounded-xl border border-slate-300 px-3 py-3 outline-none transition placeholder:text-slate-400 focus:border-brand-500 focus:ring-4 focus:ring-brand-50" placeholder="Chia sẻ lý do để SportHub cải thiện trải nghiệm..." value={reason} onChange={(event) => onReasonChange(event.target.value)} /></label><div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button className="w-full sm:w-auto" type="button" variant="outline" disabled={busy} onClick={onClose}>Giữ hồ sơ</Button><Button className="w-full sm:w-auto" type="button" variant="danger" loading={busy} leftIcon={<AlertTriangle size={17} />} onClick={onConfirm}>Xác nhận rút hồ sơ</Button></div></Modal>; }
function ReadOnlySummary({ title, rows }: { title: string; rows: [string, unknown][] }) { return <section className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-left"><h3 className="font-bold text-slate-800">{title}</h3><dl className="mt-3 space-y-2 text-sm">{rows.map(([label, value]) => <InfoRow key={label} label={label} value={Array.isArray(value) ? value.join(', ') : value ? String(value) : '—'} />)}</dl></section>; }
function InfoRow({ label, value }: { label: string; value: string }) { return <div className="grid grid-cols-[7rem_1fr] gap-2 border-t border-slate-200/70 pt-2 first:border-0 first:pt-0"><dt className="text-slate-500">{label}</dt><dd className="break-words font-medium text-slate-800">{value}</dd></div>; }
