import { ArrowRight, Mail } from 'lucide-react';
import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Input, useToast } from '@/components/common';
import { AuthShell as AuthFrame } from '@/components/auth/AuthShell';
import { PasswordField } from '@/components/auth/PasswordField';
import { useAuth } from '@/contexts/AuthContext';
import { homeForRole } from '@/components/auth/Guards';

const empty = { name: '', phone: '', email: '', password: '', confirm: '', accepted: false };

export function LoginPage() {
  const navigate = useNavigate(); const { toast } = useToast();
  const { login } = useAuth();
  const rememberedEmail = localStorage.getItem('sporthub_remembered_email') || '';
  const [email, setEmail] = useState(rememberedEmail); const [password, setPassword] = useState(''); const [remember, setRemember] = useState(Boolean(rememberedEmail)); const [show, setShow] = useState(false); const [errors, setErrors] = useState<Record<string, string>>({}); const [loading, setLoading] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); const next: Record<string, string> = {}; if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) next.email = 'Vui lòng nhập email hợp lệ.'; if (!password) next.password = 'Vui lòng nhập mật khẩu.'; setErrors(next); if (Object.keys(next).length) return; setLoading(true); try { const user = await login(email, password); if (remember) localStorage.setItem('sporthub_remembered_email', email); else localStorage.removeItem('sporthub_remembered_email'); toast(`Chào mừng ${user.full_name}!`, 'success'); navigate(homeForRole(user.role), { replace: true }); } catch (error) { setErrors({ password: error instanceof Error ? error.message : 'Đăng nhập thất bại.' }); toast('Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.', 'error'); } finally { setLoading(false); } };
  return (
    <AuthFrame title="Chào mừng trở lại" description="Đăng nhập để tiếp tục hành trình thể thao cùng SportHub AI.">
      <form onSubmit={submit} noValidate className="space-y-5">
        <Input
          label="Địa chỉ email"
          type="email"
          autoComplete="email"
          autoFocus
          placeholder="ban@example.com"
          value={email}
          onChange={(event) => { setEmail(event.target.value); if (errors.email) setErrors({ ...errors, email: '' }); }}
          error={errors.email}
          leftIcon={<Mail size={18} />}
          className="h-12 rounded-xl pl-11 text-sm"
        />
        <PasswordField
          label="Mật khẩu"
          value={password}
          show={show}
          onShow={setShow}
          onChange={(value) => { setPassword(value); if (errors.password) setErrors({ ...errors, password: '' }); }}
          error={errors.password}
          autoComplete="current-password"
        />
        <div className="flex items-center justify-between gap-4 text-sm">
          <label className="flex cursor-pointer items-center gap-2.5 text-slate-600">
            <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} className="h-4 w-4 rounded border-slate-300 accent-emerald-600" />
            Ghi nhớ đăng nhập
          </label>
          <Link to="/forgot-password" className="shrink-0 font-semibold text-brand-700 transition hover:text-brand-600 hover:underline">Quên mật khẩu?</Link>
        </div>
        <Button type="submit" size="lg" loading={loading} className="w-full rounded-xl shadow-[0_8px_20px_rgba(13,135,76,0.2)]">
          Đăng nhập <ArrowRight size={18} />
        </Button>
      </form>
      <div className="mt-7 border-t border-slate-200 pt-6 text-center">
        <p className="text-sm text-slate-500">Chưa có tài khoản? <Link to="/register" className="font-semibold text-brand-700 transition hover:text-brand-600 hover:underline">Đăng ký miễn phí</Link></p>
        <p className="mt-4 text-[11px] leading-5 text-slate-400">Bằng việc đăng nhập, bạn đồng ý với Điều khoản sử dụng và Chính sách bảo mật.</p>
      </div>
    </AuthFrame>
  );
}

export function RegisterPage() {
  const navigate = useNavigate(); const { toast } = useToast(); const [form, setForm] = useState(empty); const [show, setShow] = useState(false); const [errors, setErrors] = useState<Record<string, string>>({}); const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const phoneValid = /^0[0-9]{9}$/.test(form.phone.trim());
  const formValid = form.name.trim().length >= 2 && phoneValid && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()) && form.password.length >= 8 && form.confirm === form.password && form.accepted;
  const dirty = Object.values(form).some(Boolean);
  useEffect(() => { const warn = (event: BeforeUnloadEvent) => { if (dirty && !loading) event.preventDefault(); }; window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn); }, [dirty, loading]);
  const submit = async (event: FormEvent) => { event.preventDefault(); const next: Record<string, string> = {}; if (form.name.trim().length < 2) next.name = 'Vui lòng nhập họ tên đầy đủ.'; if (!phoneValid) next.phone = 'Số điện thoại phải gồm đúng 10 chữ số và bắt đầu bằng 0.'; if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) next.email = 'Email chưa hợp lệ.'; if (form.password.length < 8) next.password = 'Mật khẩu cần ít nhất 8 ký tự.'; if (form.confirm !== form.password) next.confirm = 'Mật khẩu xác nhận không khớp.'; if (!form.accepted) next.accepted = 'Bạn cần đồng ý điều khoản sử dụng.'; setErrors(next); if (Object.keys(next).length) { toast('Vui lòng kiểm tra các trường bắt buộc.', 'error'); return; } setLoading(true); try { await register({ full_name: form.name.trim(), phone: form.phone.trim(), email: form.email.trim(), password: form.password }); toast('Đăng ký CUSTOMER thành công! Bạn có thể đăng nhập ngay.', 'success'); navigate('/login', { replace: true }); } catch (error) { const message = error instanceof Error ? error.message : 'Không thể tạo tài khoản.'; setErrors(message.includes('Số điện thoại') ? { phone: message } : { email: message }); toast('Không thể hoàn tất đăng ký.', 'error'); } finally { setLoading(false); } };
  return <AuthFrame title="Tạo tài khoản khách hàng" description="Đăng ký công khai luôn tạo tài khoản CUSTOMER."><form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2"><Input label="Họ và tên" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} error={errors.name} /><Input label="Số điện thoại" type="tel" inputMode="numeric" maxLength={10} value={form.phone} onChange={(e) => { const phone = e.target.value.replace(/\D/g, '').slice(0, 10); setForm({ ...form, phone }); setErrors({ ...errors, phone: phone && !/^0[0-9]{9}$/.test(phone) ? 'Số điện thoại phải gồm đúng 10 chữ số và bắt đầu bằng 0.' : '' }); }} error={errors.phone} /><Input className="sm:col-span-2" label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} error={errors.email} /><PasswordField label="Mật khẩu" value={form.password} show={show} onShow={setShow} onChange={(value) => setForm({ ...form, password: value })} error={errors.password} /><PasswordField label="Xác nhận mật khẩu" value={form.confirm} show={show} onShow={setShow} onChange={(value) => setForm({ ...form, confirm: value })} error={errors.confirm} /><Check value={form.accepted} onChange={(value) => setForm({ ...form, accepted: value })} error={errors.accepted}>Tôi đồng ý với Điều khoản sử dụng và Chính sách quyền riêng tư.</Check><Button type="submit" disabled={!formValid} loading={loading} size="lg" className="sm:col-span-2">Tạo tài khoản CUSTOMER</Button></form><div className="mt-5 space-y-2 text-center text-sm text-slate-500"><p>Đã có tài khoản? <Link to="/login" className="font-semibold text-brand-700">Đăng nhập</Link></p><p>Muốn trở thành chủ sân? Hãy đăng nhập CUSTOMER và gửi hồ sơ tại <Link to="/owner-application" className="font-semibold text-brand-700">Đăng ký đối tác</Link>.</p></div></AuthFrame>;
}

function Check({ value, onChange, error, children }: { value: boolean; onChange: (value: boolean) => void; error?: string; children: ReactNode }) { return <label className="sm:col-span-2 text-xs text-slate-600"><span className="flex items-start gap-2"><input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 h-4 w-4 accent-emerald-600" />{children}</span>{error && <span className="mt-1 block text-xs text-red-600">{error}</span>}</label>; }
