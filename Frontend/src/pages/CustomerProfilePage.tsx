import { Camera, ImagePlus, Upload, UserRound } from 'lucide-react';
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { Button, Input, Modal, PageHeader, useToast } from '@/components/common';
import { useAuth } from '@/contexts/AuthContext';
import { apiRequest } from '@/services/apiClient';
import type { AuthUser } from '@/types/auth';

const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
const maxBytes = 5 * 1024 * 1024;

export function CustomerProfilePage() {
  const { user, refreshUser } = useAuth(); const { toast } = useToast();
  const [name, setName] = useState(user?.full_name || ''); const [phone, setPhone] = useState(user?.phone || '');
  const [saving, setSaving] = useState(false); const [uploading, setUploading] = useState(false);
  const [avatarOpen, setAvatarOpen] = useState(false); const [selectedFile, setSelectedFile] = useState<File>();
  const [previewUrl, setPreviewUrl] = useState<string>(); const previewRef = useRef<string | undefined>(undefined);
  const libraryInput = useRef<HTMLInputElement>(null); const cameraInput = useRef<HTMLInputElement>(null);

  useEffect(() => { if (user) { setName(user.full_name); setPhone(user.phone || ''); } }, [user]);
  useEffect(() => () => { if (previewRef.current) URL.revokeObjectURL(previewRef.current); }, []);

  const clearSelection = () => {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = undefined; setPreviewUrl(undefined); setSelectedFile(undefined);
    if (libraryInput.current) libraryInput.current.value = '';
    if (cameraInput.current) cameraInput.current.value = '';
  };
  const closeAvatar = () => { if (uploading) return; clearSelection(); setAvatarOpen(false); };
  const chooseFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return;
    if (!allowedTypes.includes(file.type)) { event.target.value = ''; return toast('Ảnh đại diện phải là tệp JPG, PNG hoặc WEBP.', 'error'); }
    if (file.size > maxBytes) { event.target.value = ''; return toast('Ảnh đại diện không được vượt quá 5 MB.', 'error'); }
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    const url = URL.createObjectURL(file); previewRef.current = url; setPreviewUrl(url); setSelectedFile(file);
  };
  const uploadAvatar = async () => {
    if (!selectedFile) return;
    const body = new FormData(); body.append('avatar', selectedFile); setUploading(true);
    try {
      await apiRequest<AuthUser>('/auth/profile/avatar', { method: 'POST', body });
      await refreshUser(); clearSelection(); setAvatarOpen(false);
      toast('Cập nhật ảnh đại diện thành công', 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không thể cập nhật ảnh đại diện.', 'error'); }
    finally { setUploading(false); }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true);
    try {
      await apiRequest('/auth/profile', { method: 'PUT', body: JSON.stringify({ full_name: name, phone: phone || null }) });
      await refreshUser(); toast('Đã cập nhật hồ sơ.', 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không cập nhật được hồ sơ.', 'error'); }
    finally { setSaving(false); }
  };

  const currentAvatar = user?.avatar_url;
  return <><PageHeader title="Hồ sơ cá nhân" description="Quản lý thông tin và ảnh đại diện của tài khoản đang đăng nhập." />
    <form onSubmit={submit} className="rounded-card border bg-white p-5 sm:p-7">
      <div className="mb-7 flex flex-col items-center gap-4 border-b border-slate-100 pb-7 text-center sm:flex-row sm:text-left">
        <button type="button" onClick={() => setAvatarOpen(true)} className="group relative h-24 w-24 shrink-0 overflow-hidden rounded-full bg-brand-100 shadow-sm outline-none ring-4 ring-white transition focus:ring-brand-200" aria-label="Đổi ảnh đại diện">
          {currentAvatar ? <img src={currentAvatar} className="h-full w-full object-cover" alt={`Ảnh đại diện của ${user?.full_name || 'người dùng'}`} /> : <span className="grid h-full w-full place-items-center text-brand-700"><UserRound size={38} /></span>}
          <span className="absolute inset-0 flex items-center justify-center gap-1 bg-slate-950/55 text-xs font-semibold text-white opacity-100 transition sm:opacity-0 sm:group-hover:opacity-100"><Camera size={16} /> Đổi ảnh</span>
        </button>
        <div><b className="text-lg text-slate-900">{user?.full_name}</b><p className="mt-1 text-sm text-slate-500">Nhấp vào ảnh để cập nhật</p><p className="mt-1 text-xs text-slate-400">Tham gia {user && new Date(user.created_at).toLocaleDateString('vi-VN')}</p></div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2"><Input required label="Họ và tên" value={name} onChange={(event) => setName(event.target.value)} /><Input label="Email" value={user?.email || ''} disabled /><Input label="Số điện thoại" value={phone} onChange={(event) => setPhone(event.target.value)} /></div>
      <Button type="submit" loading={saving} className="mt-5 w-full sm:w-auto">Lưu thay đổi</Button>
    </form>

    <Modal open={avatarOpen} onClose={closeAvatar} title="Cập nhật ảnh đại diện" description="Chọn ảnh mới và xem trước trước khi xác nhận.">
      <input ref={libraryInput} className="sr-only" id="avatar-library" type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseFile} />
      <input ref={cameraInput} className="sr-only" id="avatar-camera" type="file" accept="image/jpeg,image/png,image/webp" capture="user" onChange={chooseFile} />
      <div className="mx-auto grid h-52 w-52 max-w-full place-items-center overflow-hidden rounded-full border-4 border-white bg-slate-100 shadow-lg">
        {previewUrl || currentAvatar ? <img src={previewUrl || currentAvatar || ''} className="h-full w-full object-cover" alt="Xem trước ảnh đại diện" /> : <UserRound size={64} className="text-slate-400" />}
      </div>
      <p className="mt-4 text-center text-xs text-slate-500">JPG, PNG hoặc WEBP · tối đa 5 MB</p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2"><label htmlFor="avatar-library" className="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:border-brand-300 hover:bg-brand-50"><ImagePlus size={18} /> Chọn từ thư viện</label><label htmlFor="avatar-camera" className="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:border-brand-300 hover:bg-brand-50"><Camera size={18} /> Chụp ảnh</label></div>
      <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button type="button" variant="outline" className="w-full sm:w-auto" disabled={uploading} onClick={closeAvatar}>Hủy</Button><Button type="button" className="w-full sm:w-auto" disabled={!selectedFile} loading={uploading} leftIcon={<Upload size={17} />} onClick={() => void uploadAvatar()}>Cập nhật ảnh</Button></div>
    </Modal>
  </>;
}
