import { CheckCircle2, Mail } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { AuthShell } from '@/components/auth/AuthShell';
import { Button, Input, useToast } from '@/components/common';

/** Password recovery remains mocked until the mail API is available. */
export function ForgotPasswordPage() {
  const { toast } = useToast(); const [email, setEmail] = useState(''); const [error, setError] = useState(''); const [sent, setSent] = useState(false); const [loading, setLoading] = useState(false);
  const submit = (event: FormEvent) => { event.preventDefault(); if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError('Vui lòng nhập email hợp lệ.'); return; } setError(''); setLoading(true); window.setTimeout(() => { setLoading(false); setSent(true); toast('Đã gửi hướng dẫn đặt lại mật khẩu.', 'success'); }, 650); };
  return <AuthShell title="Quên mật khẩu?" description="Nhập email đăng ký để nhận hướng dẫn khôi phục.">{sent ? <div className="text-center"><span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-brand-50 text-brand-700"><CheckCircle2 size={32} /></span><h2 className="mt-4 font-bold">Kiểm tra hộp thư của bạn</h2><p className="mt-2 text-sm text-slate-500">Liên kết đặt lại mật khẩu đã được gửi tới <b>{email}</b>. Liên kết có hiệu lực trong 15 phút.</p><Link to="/login"><Button className="mt-6 w-full">Về trang đăng nhập</Button></Link></div> : <form onSubmit={submit} noValidate className="space-y-4"><Input label="Email tài khoản" type="email" autoFocus value={email} onChange={(event) => setEmail(event.target.value)} error={error} leftIcon={<Mail size={17} />} /><Button type="submit" size="lg" loading={loading} className="w-full">Gửi hướng dẫn</Button><Link to="/login" className="block text-center text-sm font-semibold text-brand-700">← Quay lại đăng nhập</Link></form>}</AuthShell>;
}
