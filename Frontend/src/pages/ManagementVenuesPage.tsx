import { Building2, Eye, FileText, ImagePlus, MapPin, Pencil, Phone, Plus, Send, ShieldCheck, Trash2, UploadCloud } from 'lucide-react';
import { type DragEvent, type FormEvent, useEffect, useState } from 'react';
import { Badge, Button, EmptyState, Input, LoadingSkeleton, Modal, PageHeader, SecureApiImage, useToast } from '@/components/common';
import { apiBlob, apiRequest } from '@/services/apiClient';

type Status = 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'SUSPENDED';
interface Media {
  id: number; category?: string; document_name?: string; document_type?: string;
  document_number?: string; issued_date?: string; issued_by?: string; original_name: string;
  mime_type: string; file_size: number; url?: string;
}
interface Facility {
  id: number; name: string; location: string; description: string | null;
  contact_phone: string | null; contact_email: string | null; city: string | null;
  district: string | null; opening_time: string | null; closing_time: string | null;
  sports: string[]; status: Status; submitted_at: string | null; rejection_reason: string | null;
  field_count: number; images: Media[]; documents: Media[];
}

const sports = ['Bóng đá', 'Cầu lông', 'Pickleball', 'Tennis', 'Bóng rổ', 'Bóng chuyền'];
const labels: Record<Status, string> = { DRAFT: 'Bản nháp', PENDING_APPROVAL: 'Chờ xét duyệt', APPROVED: 'Đã duyệt', REJECTED: 'Cần bổ sung', SUSPENDED: 'Tạm ngừng' };
const badge = (status: Status) => status === 'APPROVED' ? 'success' : status === 'REJECTED' || status === 'SUSPENDED' ? 'danger' : status === 'PENDING_APPROVAL' ? 'warning' : 'neutral';
const blank = { name: '', location: '', description: '', contact_phone: '', contact_email: '', city: '', district: '', opening_time: '06:00', closing_time: '22:00', sports: [] as string[] };
const allowedDocumentTypes = new Set(['image/jpeg', 'image/png', 'application/pdf']);
const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024;
const formatBytes = (size: number) => size < 1024 * 1024 ? `${(size / 1024).toFixed(1)} KB` : `${(size / 1024 / 1024).toFixed(1)} MB`;

export function ManagementVenuesPage() {
  const [items, setItems] = useState<Facility[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Facility>();
  const [open, setOpen] = useState(false);
  const [draftToDelete, setDraftToDelete] = useState<Facility>();
  const [deletingDraft, setDeletingDraft] = useState(false);
  const [form, setForm] = useState(blank);
  const [saving, setSaving] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number; name: string }>();
  const [dragging, setDragging] = useState(false);
  const [imageCategory, setImageCategory] = useState('COVER');
  const [documentType, setDocumentType] = useState('BUSINESS_REGISTRATION');
  const [documentName, setDocumentName] = useState('Giấy tờ xác minh cơ sở');
  const [documentNumber, setDocumentNumber] = useState('');
  const [issuedDate, setIssuedDate] = useState('');
  const [issuedBy, setIssuedBy] = useState('');
  const { toast } = useToast();

  const mergeFacility = (updated: Facility) => {
    setEditing(updated);
    setItems((current) => current.some((item) => item.id === updated.id)
      ? current.map((item) => item.id === updated.id ? updated : item)
      : [updated, ...current]);
  };
  const load = async () => {
    setLoading(true);
    try { setItems(await apiRequest<Facility[]>('/facilities')); }
    catch (error) { toast(error instanceof Error ? error.message : 'Không tải được cơ sở.', 'error'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const startCreate = () => {
    setEditing(undefined); setForm(blank); setImageCategory('COVER');
    setDocumentType('BUSINESS_REGISTRATION'); setDocumentName('Giấy tờ xác minh cơ sở');
    setDocumentNumber(''); setIssuedDate(''); setIssuedBy(''); setOpen(true);
  };
  const startEdit = (item: Facility) => {
    setEditing(item);
    setForm({ name: item.name, location: item.location, description: item.description || '', contact_phone: item.contact_phone || '', contact_email: item.contact_email || '', city: item.city || '', district: item.district || '', opening_time: item.opening_time?.slice(0, 5) || '06:00', closing_time: item.closing_time?.slice(0, 5) || '22:00', sports: item.sports || [] });
    const document = item.documents[0];
    setDocumentType(document?.document_type || 'BUSINESS_REGISTRATION');
    setDocumentName(document?.document_name || 'Giấy tờ xác minh cơ sở');
    setDocumentNumber(document?.document_number || '');
    setIssuedDate(document?.issued_date || ''); setIssuedBy(document?.issued_by || '');
    setOpen(true);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (form.opening_time && form.closing_time && form.opening_time >= form.closing_time) return toast('Giờ mở cửa phải trước giờ đóng cửa.', 'error');
    setSaving(true);
    try {
      const updated = await apiRequest<Facility>(editing ? `/facilities/${editing.id}` : '/facilities', { method: editing ? 'PUT' : 'POST', body: JSON.stringify({ ...form, free_cancellation_minutes: 360, amenities: [], image_urls: [] }) });
      mergeFacility(updated);
      toast(updated.status === 'DRAFT' ? 'Đã lưu bản nháp.' : 'Đã cập nhật hồ sơ cơ sở.', 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không lưu được hồ sơ.', 'error'); }
    finally { setSaving(false); }
  };

  const uploadImage = async (file?: File) => {
    if (!editing || !file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
      return toast('Ảnh phải là JPG, PNG hoặc WEBP và không vượt quá 5 MB.', 'error');
    }
    const body = new FormData(); body.append('category', imageCategory); body.append('image', file);
    setSaving(true);
    try { mergeFacility(await apiRequest<Facility>(`/facilities/${editing.id}/images`, { method: 'POST', body })); toast('Đã tải ảnh cơ sở.', 'success'); }
    catch (error) { toast(error instanceof Error ? error.message : 'Không tải được ảnh.', 'error'); }
    finally { setSaving(false); }
  };

  const uploadDocuments = async (fileList?: FileList | File[]) => {
    if (!editing || !fileList?.length) return;
    if (documentName.trim().length < 2 || documentNumber.trim().length < 2) {
      return toast('Vui lòng nhập tên và số giấy tờ trước khi chọn file.', 'error');
    }
    const unique = Array.from(fileList).filter((file, index, files) =>
      files.findIndex((candidate) => candidate.name === file.name && candidate.size === file.size) === index
      && !editing.documents.some((document) => document.original_name === file.name && document.file_size === file.size));
    if (unique.length !== fileList.length) toast('Đã bỏ qua file trùng tên và dung lượng.', 'info');
    const invalid = unique.find((file) => !allowedDocumentTypes.has(file.type) || file.size > MAX_DOCUMENT_BYTES);
    if (invalid) return toast(`${invalid.name}: chỉ hỗ trợ JPG, JPEG, PNG, PDF tối đa 10 MB/file.`, 'error');
    if (editing.documents.length + unique.length > 10) return toast('Mỗi hồ sơ được tải tối đa 10 file giấy tờ.', 'error');
    setSaving(true);
    try {
      for (let index = 0; index < unique.length; index += 1) {
        const file = unique[index];
        setUploadProgress({ current: index + 1, total: unique.length, name: file.name });
        const body = new FormData();
        body.append('document_type', documentType); body.append('document_name', documentName.trim());
        body.append('document_number', documentNumber.trim());
        if (issuedDate) body.append('issued_date', issuedDate);
        if (issuedBy.trim()) body.append('issued_by', issuedBy.trim());
        body.append('document', file);
        const updated = await apiRequest<Facility>(`/facilities/${editing.id}/documents`, { method: 'POST', body });
        mergeFacility(updated);
      }
      toast(`Đã tải ${unique.length} file giấy tờ xác minh.`, 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không tải được giấy tờ.', 'error'); }
    finally { setSaving(false); setUploadProgress(undefined); }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault(); setDragging(false); void uploadDocuments(event.dataTransfer.files);
  };
  const openDocument = async (documentId: number) => {
    if (!editing) return;
    try {
      const blob = await apiBlob(`/facilities/${editing.id}/documents/${documentId}/content`);
      const url = URL.createObjectURL(blob); window.open(url, '_blank', 'noopener,noreferrer');
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) { toast(error instanceof Error ? error.message : 'Không mở được giấy tờ.', 'error'); }
  };
  const removeMedia = async (kind: 'images' | 'documents', mediaId: number) => {
    if (!editing || !window.confirm(kind === 'images' ? 'Xóa ảnh này khỏi hồ sơ?' : 'Xóa giấy tờ này khỏi hồ sơ?')) return;
    setSaving(true);
    try { mergeFacility(await apiRequest<Facility>(`/facilities/${editing.id}/${kind}/${mediaId}`, { method: 'DELETE' })); toast('Đã xóa file khỏi hồ sơ.', 'success'); }
    catch (error) { toast(error instanceof Error ? error.message : 'Không thể xóa file.', 'error'); }
    finally { setSaving(false); }
  };
  const action = async (item: Facility, endpoint: string) => {
    setSaving(true);
    try {
      const updated = await apiRequest<Facility>(`/facilities/${item.id}/${endpoint}`, { method: 'POST' });
      mergeFacility(updated);
      toast(endpoint === 'submit' ? 'Hồ sơ cơ sở đã được gửi và đang chờ xét duyệt.' : 'Đã hủy yêu cầu xét duyệt.', 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không xử lý được hồ sơ.', 'error'); }
    finally { setSaving(false); }
  };
  const deleteDraft = async () => {
    if (!draftToDelete) return;
    setDeletingDraft(true);
    try {
      await apiRequest<void>(`/facilities/${draftToDelete.id}/draft`, { method: 'DELETE' });
      setItems((current) => current.filter((item) => item.id !== draftToDelete.id));
      if (editing?.id === draftToDelete.id) { setEditing(undefined); setOpen(false); }
      setDraftToDelete(undefined);
      toast('Đã xóa bản nháp cơ sở.', 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không thể xóa bản nháp.', 'error'); }
    finally { setDeletingDraft(false); }
  };

  return <>
    <PageHeader title="Cơ sở" description="Đăng ký, theo dõi xét duyệt và quản lý các cơ sở thuộc tài khoản OWNER." actions={<Button leftIcon={<Plus size={17} />} onClick={startCreate}>Đăng ký cơ sở mới</Button>} />
    {loading ? <LoadingSkeleton lines={8} /> : items.length ? <div className="grid gap-5 lg:grid-cols-2">
      {items.map((item) => <article key={item.id} className="overflow-hidden rounded-card border bg-white shadow-sm">
        {item.images[0]?.url ? <SecureApiImage src={item.images[0].url} alt={item.name} className="h-44 w-full object-cover" /> : <div className="grid h-32 place-items-center bg-gradient-to-br from-brand-50 to-sportblue-50 text-brand-700"><Building2 size={40} /></div>}
        <div className="p-5">
          <div className="flex items-start justify-between gap-3"><div><h2 className="text-lg font-black">{item.name || 'Bản nháp chưa đặt tên'}</h2><p className="mt-1 flex gap-2 text-sm text-slate-500"><MapPin size={16} />{item.location || 'Chưa nhập địa chỉ'}</p></div><Badge variant={badge(item.status)}>{labels[item.status]}</Badge></div>
          <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-slate-50 p-3 text-sm"><span><Phone size={15} className="mr-1 inline" />{item.contact_phone || 'Chưa có hotline'}</span><span>{item.field_count} sân/court</span><span className="col-span-2">{item.sports.join(' · ') || 'Chưa chọn môn'}</span></div>
          {item.rejection_reason && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700"><b>Cơ sở bị từ chối:</b> {item.rejection_reason}</p>}
          {item.submitted_at && <p className="mt-3 text-xs text-slate-500">Ngày gửi: {new Date(item.submitted_at).toLocaleString('vi-VN')}</p>}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button size="sm" variant={item.status === 'DRAFT' || item.status === 'REJECTED' ? 'primary' : 'outline'} leftIcon={<Pencil size={15} />} onClick={() => startEdit(item)}>{item.status === 'DRAFT' ? 'Tiếp tục chỉnh sửa' : item.status === 'PENDING_APPROVAL' ? 'Xem hồ sơ' : item.status === 'REJECTED' ? 'Bổ sung hồ sơ' : 'Chỉnh sửa'}</Button>
            {item.status === 'DRAFT' && <Button size="sm" variant="danger" leftIcon={<Trash2 size={15} />} onClick={() => setDraftToDelete(item)}>Xóa bản nháp</Button>}
            {item.status === 'REJECTED' && <Button size="sm" leftIcon={<Send size={15} />} loading={saving} onClick={() => void action(item, 'submit')}>Gửi lại hồ sơ</Button>}
            {item.status === 'PENDING_APPROVAL' && <Button size="sm" variant="danger" onClick={() => void action(item, 'cancel-review')}>Hủy yêu cầu</Button>}
            {item.status === 'APPROVED' && <Button size="sm" onClick={() => location.assign('/management/courts')}>Quản lý sân</Button>}
          </div>
        </div>
      </article>)}
    </div> : <EmptyState icon={<Building2 />} title="Chưa có cơ sở" description="Tạo hồ sơ cơ sở đầu tiên và gửi giấy tờ để System Admin xét duyệt." />}

    <Modal open={open} onClose={() => !saving && setOpen(false)} title={editing ? 'Hồ sơ cơ sở' : 'Đăng ký cơ sở mới'} description="Thông tin xác minh chỉ hiển thị cho OWNER sở hữu và System Admin.">
      <form onSubmit={save} className="space-y-4">
        <Input label="Tên cơ sở" value={form.name} disabled={editing?.status === 'PENDING_APPROVAL'} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <Input label="Địa chỉ đầy đủ" value={form.location} disabled={editing?.status === 'PENDING_APPROVAL'} onChange={(event) => setForm({ ...form, location: event.target.value })} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label="Tỉnh/thành phố" value={form.city} disabled={editing?.status === 'PENDING_APPROVAL'} onChange={(event) => setForm({ ...form, city: event.target.value })} />
          <Input label="Quận/huyện/khu vực" value={form.district} disabled={editing?.status === 'PENDING_APPROVAL'} onChange={(event) => setForm({ ...form, district: event.target.value })} />
          <Input label="Số điện thoại" value={form.contact_phone} disabled={editing?.status === 'PENDING_APPROVAL'} onChange={(event) => setForm({ ...form, contact_phone: event.target.value })} />
          <Input type="email" label="Email liên hệ" value={form.contact_email} disabled={editing?.status === 'PENDING_APPROVAL'} onChange={(event) => setForm({ ...form, contact_email: event.target.value })} />
          <Input type="time" label="Giờ mở cửa" value={form.opening_time} disabled={editing?.status === 'PENDING_APPROVAL'} onChange={(event) => setForm({ ...form, opening_time: event.target.value })} />
          <Input type="time" label="Giờ đóng cửa" value={form.closing_time} disabled={editing?.status === 'PENDING_APPROVAL'} onChange={(event) => setForm({ ...form, closing_time: event.target.value })} />
        </div>
        <label className="block text-sm font-medium">Mô tả<textarea className="field mt-2 min-h-24" value={form.description} disabled={editing?.status === 'PENDING_APPROVAL'} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
        <fieldset disabled={editing?.status === 'PENDING_APPROVAL'}><legend className="text-sm font-semibold">Loại hình / môn thể thao hỗ trợ</legend><div className="mt-2 grid grid-cols-2 gap-2">{sports.map((sport) => <label key={sport} className="flex items-center gap-2 rounded-lg border p-2 text-sm"><input type="checkbox" checked={form.sports.includes(sport)} onChange={(event) => setForm({ ...form, sports: event.target.checked ? [...form.sports, sport] : form.sports.filter((value) => value !== sport) })} />{sport}</label>)}</div></fieldset>
        {editing?.status !== 'PENDING_APPROVAL' && <Button type="submit" loading={saving} className="w-full">{!editing || editing.status === 'DRAFT' ? 'Lưu bản nháp' : 'Lưu thay đổi'}</Button>}
      </form>
      {editing && <div className="mt-6 space-y-6 border-t pt-5">
        <section>
          <h3 className="flex items-center gap-2 font-bold"><ImagePlus size={18} />Ảnh đại diện cơ sở</h3>
          <p className="mt-1 text-xs text-slate-500">JPG, PNG hoặc WEBP, tối đa 5 MB/ảnh. Hồ sơ cần ít nhất một ảnh.</p>
          {editing.status !== 'PENDING_APPROVAL' && <div className="mt-3 flex flex-col gap-2 sm:flex-row"><select className="field" value={imageCategory} onChange={(event) => setImageCategory(event.target.value)}><option value="COVER">Ảnh đại diện</option><option value="FRONT">Ảnh mặt tiền</option><option value="COURT_AREA">Khu vực sân</option><option value="ADDITIONAL">Ảnh bổ sung</option></select><label className="inline-flex h-11 cursor-pointer items-center justify-center rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white">Chọn ảnh<input className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { void uploadImage(event.target.files?.[0]); event.target.value = ''; }} /></label></div>}
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">{editing.images.map((image) => <div key={image.id} className="relative"><SecureApiImage src={image.url || ''} alt={image.original_name} className="h-24 w-full rounded-lg border object-cover" /><small className="mt-1 block truncate">{image.original_name} · {formatBytes(image.file_size)}</small>{editing.status !== 'PENDING_APPROVAL' && <button type="button" aria-label="Xóa ảnh" className="absolute right-1 top-1 rounded-full bg-white/90 p-1.5 text-red-600 shadow" onClick={() => void removeMedia('images', image.id)}><Trash2 size={14} /></button>}</div>)}</div>
        </section>

        <section>
          <h3 className="flex items-center gap-2 text-lg font-black"><ShieldCheck size={20} className="text-brand-700" />Giấy tờ xác minh cơ sở</h3>
          <p className="mt-1 text-sm text-slate-600">Hỗ trợ JPG, PNG, PDF. Vui lòng cung cấp ảnh/file rõ ràng để Admin xét duyệt.</p>
          {editing.status !== 'PENDING_APPROVAL' && <div className="mt-4 grid gap-3 rounded-xl border bg-slate-50 p-4">
            <label className="text-sm font-semibold">Loại giấy tờ<select className="field mt-1" value={documentType} onChange={(event) => setDocumentType(event.target.value)}><option value="BUSINESS_REGISTRATION">Đăng ký kinh doanh</option><option value="HOUSEHOLD_BUSINESS_LICENSE">Giấy phép hộ kinh doanh</option><option value="OTHER">Giấy tờ xác minh khác</option></select></label>
            <div className="grid gap-3 sm:grid-cols-2"><Input required label="Tên giấy tờ" value={documentName} onChange={(event) => setDocumentName(event.target.value)} /><Input required label="Số giấy tờ / mã đăng ký" value={documentNumber} onChange={(event) => setDocumentNumber(event.target.value)} /><Input type="date" label="Ngày cấp (nếu có)" value={issuedDate} onChange={(event) => setIssuedDate(event.target.value)} /><Input label="Nơi cấp (nếu có)" value={issuedBy} onChange={(event) => setIssuedBy(event.target.value)} /></div>
            <div onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={handleDrop} className={`rounded-xl border-2 border-dashed p-5 text-center transition ${dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-white'}`}>
              <UploadCloud className="mx-auto text-brand-700" />
              <p className="mt-2 text-sm font-semibold">Kéo và thả nhiều trang vào đây</p>
              <p className="mb-3 text-xs text-slate-500">Tối đa 10 MB/file, tối đa 10 file/hồ sơ</p>
              <label className="inline-flex h-10 cursor-pointer items-center rounded-xl border border-brand-300 bg-brand-50 px-4 text-sm font-semibold text-brand-700">Chọn ảnh / Chọn file giấy tờ<input className="sr-only" type="file" multiple accept="application/pdf,image/jpeg,image/png,.jpg,.jpeg,.png,.pdf" onChange={(event) => { void uploadDocuments(event.target.files || undefined); event.target.value = ''; }} /></label>
            </div>
            {uploadProgress && <div className="rounded-lg bg-brand-50 p-3 text-sm text-brand-800"><div className="flex justify-between gap-3"><span className="truncate">Đang tải {uploadProgress.name}</span><b>{uploadProgress.current}/{uploadProgress.total}</b></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-brand-100"><div className="h-full bg-brand-600 transition-all" style={{ width: `${uploadProgress.current / uploadProgress.total * 100}%` }} /></div></div>}
          </div>}

          <div className="mt-3 space-y-3">{editing.documents.map((document) => <article key={document.id} className="flex flex-col gap-3 rounded-xl border p-3 sm:flex-row sm:items-center">
            {document.mime_type.startsWith('image/') ? <SecureApiImage src={document.url || ''} alt={document.original_name} className="h-20 w-24 shrink-0 rounded-lg border object-cover" /> : <div className="grid h-20 w-24 shrink-0 place-items-center rounded-lg bg-red-50 text-red-700"><FileText size={30} /><span className="sr-only">PDF</span></div>}
            <div className="min-w-0 flex-1"><p className="truncate font-bold">{document.original_name}</p><p className="text-xs text-slate-500">{formatBytes(document.file_size)} · Số {document.document_number}</p><p className="text-xs text-slate-500">{document.document_name}{document.issued_by ? ` · ${document.issued_by}` : ''}</p></div>
            <div className="flex gap-2"><Button type="button" size="sm" variant="outline" leftIcon={<Eye size={14} />} onClick={() => void openDocument(document.id)}>Xem</Button>{editing.status !== 'PENDING_APPROVAL' && <Button type="button" size="sm" variant="danger" aria-label="Xóa giấy tờ" onClick={() => void removeMedia('documents', document.id)}><Trash2 size={14} /></Button>}</div>
          </article>)}</div>
          {!editing.documents.length && <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">Chưa có giấy tờ. Bạn chưa thể gửi đăng ký cơ sở.</p>}
        </section>
        {['DRAFT', 'REJECTED'].includes(editing.status) && <Button className="w-full" loading={saving} leftIcon={<Send size={17} />} onClick={() => void action(editing, 'submit')}>Gửi đăng ký cơ sở</Button>}
      </div>}
    </Modal>
    <Modal open={Boolean(draftToDelete)} onClose={() => !deletingDraft && setDraftToDelete(undefined)} title="Xóa bản nháp đăng ký cơ sở">
      <p className="rounded-xl bg-red-50 p-4 text-sm leading-6 text-red-800">Bạn có chắc muốn xóa bản nháp đăng ký cơ sở này? Thông tin và các file giấy tờ đã tải lên trong bản nháp sẽ bị xóa và không thể khôi phục.</p>
      <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="outline" disabled={deletingDraft} onClick={() => setDraftToDelete(undefined)}>Hủy</Button>
        <Button variant="danger" loading={deletingDraft} leftIcon={<Trash2 size={16} />} onClick={() => void deleteDraft()}>Xóa bản nháp</Button>
      </div>
    </Modal>
  </>;
}
