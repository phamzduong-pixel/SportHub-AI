import { KeyRound, UserRound } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { Button, Input, PageHeader, useToast } from '@/components/common';
import { useAuth } from '@/contexts/AuthContext';
import { apiRequest } from '@/services/apiClient';

export function ManagementSettingsPage() {
  const { user, refreshUser } = useAuth();
  const { toast } = useToast();
  const [profile, setProfile] = useState({ full_name: user?.full_name || '', phone: user?.phone || '' });
  const [password, setPassword] = useState({ current_password: '', new_password: '' });
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (user) setProfile({ full_name: user.full_name, phone: user.phone || '' }); }, [user]);
  const saveProfile = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true);
    try {
      await apiRequest('/auth/profile', { method: 'PUT', body: JSON.stringify({ ...profile, phone: profile.phone || null }) });
      await refreshUser(); toast('Đã cập nhật hồ sơ OWNER.', 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không cập nhật được hồ sơ.', 'error'); }
    finally { setSaving(false); }
  };
  const changePassword = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await apiRequest('/auth/change-password', { method: 'PUT', body: JSON.stringify(password) });
      setPassword({ current_password: '', new_password: '' }); toast('Đã đổi mật khẩu.', 'success');
    } catch (error) { toast(error instanceof Error ? error.message : 'Không đổi được mật khẩu.', 'error'); }
  };
  return <><PageHeader title="Cài đặt tài khoản" description="Dữ liệu của OWNER đang đăng nhập." /><div className="grid gap-5 lg:grid-cols-2"><form onSubmit={saveProfile} className="rounded-card border bg-white p-5"><h2 className="flex items-center gap-2 font-bold"><UserRound size={18} />Hồ sơ</h2><div className="mt-5 space-y-4"><Input required label="Họ và tên" value={profile.full_name} onChange={(event) => setProfile({ ...profile, full_name: event.target.value })} /><Input label="Email" value={user?.email || ''} disabled /><Input label="Số điện thoại" value={profile.phone} onChange={(event) => setProfile({ ...profile, phone: event.target.value })} /><Button type="submit" loading={saving}>Lưu hồ sơ</Button></div></form><form onSubmit={changePassword} className="rounded-card border bg-white p-5"><h2 className="flex items-center gap-2 font-bold"><KeyRound size={18} />Đổi mật khẩu</h2><div className="mt-5 space-y-4"><Input required type="password" label="Mật khẩu hiện tại" value={password.current_password} onChange={(event) => setPassword({ ...password, current_password: event.target.value })} /><Input required type="password" minLength={8} label="Mật khẩu mới" value={password.new_password} onChange={(event) => setPassword({ ...password, new_password: event.target.value })} /><Button type="submit">Đổi mật khẩu</Button></div></form></div></>;
}
