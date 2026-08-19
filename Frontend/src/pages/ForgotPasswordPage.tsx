import { CheckCircle2, Mail, Phone, ShieldCheck } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthShell } from '@/components/auth/AuthShell';
import { Button, Input, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';

type Method = 'email' | 'phone';
type Step = 'form' | 'otp' | 'sent';

export function ForgotPasswordPage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [method, setMethod] = useState<Method>('email');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [step, setStep] = useState<Step>('form');
  const [loading, setLoading] = useState(false);

  const submitEmail = async (event: FormEvent) => {
    event.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Vui lòng nhập email hợp lệ.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await apiRequest<{ message: string }>('/auth/forgot-password/email', {
        method: 'POST',
        body: JSON.stringify({ email }),
      });
      setStep('sent');
      toast('Đã gửi hướng dẫn đặt lại mật khẩu.', 'success');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Không thể gửi yêu cầu.';
      setError(msg);
      toast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const submitPhone = async (event: FormEvent) => {
    event.preventDefault();
    if (!/^0[0-9]{9}$/.test(phone)) {
      setError('Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await apiRequest<{ message: string }>('/auth/forgot-password/phone', {
        method: 'POST',
        body: JSON.stringify({ phone }),
      });
      setStep('otp');
      toast('Mã OTP đã được gửi đến số điện thoại.', 'success');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Không thể gửi OTP.';
      setError(msg);
      toast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const submitOtp = async (event: FormEvent) => {
    event.preventDefault();
    if (!/^[0-9]{6}$/.test(otp)) {
      setError('Mã OTP phải gồm 6 chữ số.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const result = await apiRequest<{ message: string; token: string }>('/auth/verify-otp', {
        method: 'POST',
        body: JSON.stringify({ phone, otp }),
      });
      toast('Xác thực OTP thành công.', 'success');
      navigate(`/reset-password?token=${encodeURIComponent(result.token)}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Mã OTP không hợp lệ.';
      setError(msg);
      toast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ─── Success screen (email sent) ──────────────────────────────────────────
  if (step === 'sent') {
    return (
      <AuthShell title="Quên mật khẩu?" description="">
        <div className="text-center">
          <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-brand-50 text-brand-700">
            <CheckCircle2 size={32} />
          </span>
          <h2 className="mt-4 font-bold">Kiểm tra hộp thư của bạn</h2>
          <p className="mt-2 text-sm text-slate-500">
            Nếu email <b>{email}</b> tồn tại trong hệ thống, liên kết đặt lại mật khẩu đã được gửi. Liên kết có hiệu lực trong 15 phút.
          </p>
          <Link to="/login">
            <Button className="mt-6 w-full">Về trang đăng nhập</Button>
          </Link>
        </div>
      </AuthShell>
    );
  }

  // ─── OTP input screen (phone flow) ────────────────────────────────────────
  if (step === 'otp') {
    return (
      <AuthShell title="Nhập mã OTP" description={`Mã OTP 6 số đã được gửi đến ${phone}.`}>
        <form onSubmit={submitOtp} noValidate className="space-y-4">
          <Input
            label="Mã OTP"
            type="text"
            inputMode="numeric"
            autoFocus
            maxLength={6}
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
            error={error}
            leftIcon={<ShieldCheck size={17} />}
            placeholder="000000"
          />
          <Button type="submit" size="lg" loading={loading} className="w-full">
            Xác nhận OTP
          </Button>
          <button
            type="button"
            onClick={() => { setStep('form'); setOtp(''); setError(''); }}
            className="block w-full text-center text-sm font-semibold text-brand-700"
          >
            ← Quay lại
          </button>
        </form>
      </AuthShell>
    );
  }

  // ─── Main form: choose email or phone ─────────────────────────────────────
  return (
    <AuthShell title="Quên mật khẩu?" description="Chọn phương thức khôi phục tài khoản.">
      <div className="mb-5 flex rounded-lg border bg-slate-50 p-1">
        <button
          type="button"
          className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition ${method === 'email' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
          onClick={() => { setMethod('email'); setError(''); }}
        >
          <Mail size={16} /> Email
        </button>
        <button
          type="button"
          className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition ${method === 'phone' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
          onClick={() => { setMethod('phone'); setError(''); }}
        >
          <Phone size={16} /> Số điện thoại
        </button>
      </div>

      {method === 'email' ? (
        <form onSubmit={submitEmail} noValidate className="space-y-4">
          <Input
            label="Email tài khoản"
            type="email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={error}
            leftIcon={<Mail size={17} />}
          />
          <Button type="submit" size="lg" loading={loading} className="w-full">
            Gửi liên kết đặt lại
          </Button>
        </form>
      ) : (
        <form onSubmit={submitPhone} noValidate className="space-y-4">
          <Input
            label="Số điện thoại đã đăng ký"
            type="tel"
            autoFocus
            maxLength={10}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            error={error}
            leftIcon={<Phone size={17} />}
            placeholder="0912345678"
          />
          <Button type="submit" size="lg" loading={loading} className="w-full">
            Gửi mã OTP
          </Button>
        </form>
      )}

      <Link to="/login" className="mt-4 block text-center text-sm font-semibold text-brand-700">
        ← Quay lại đăng nhập
      </Link>
    </AuthShell>
  );
}
