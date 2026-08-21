import { ArrowLeft, CheckCircle2, Clock, KeyRound, Mail, Phone, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react';
import { useEffect, useRef, useState, type ClipboardEvent, type FormEvent, type KeyboardEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthShell } from '@/components/auth/AuthShell';
import { Button, Input, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';

type Method = 'email' | 'phone';
type Step = 'form' | 'otp';

const COUNTDOWN_SECONDS = 60;
const OTP_LENGTH = 6;

export function ForgotPasswordPage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [method, setMethod] = useState<Method>('email');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [digits, setDigits] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [error, setError] = useState('');
  const [step, setStep] = useState<Step>('form');
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [countdown, setCountdown] = useState(0);

  const inputRefs = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setInterval(() => {
      setCountdown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  useEffect(() => {
    if (step === 'otp') {
      setTimeout(() => {
        inputRefs.current[0]?.focus();
      }, 100);
    }
  }, [step]);

  const validateInput = (): string | null => {
    const identifier = method === 'email' ? email.trim() : phone.trim();
    if (!identifier) {
      return method === 'email' ? 'Vui lòng nhập địa chỉ email.' : 'Vui lòng nhập số điện thoại.';
    }
    if (method === 'email') {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(identifier)) {
        return 'Địa chỉ email không đúng định dạng.';
      }
    } else {
      const phoneRegex = /^0[0-9]{9}$/;
      if (!phoneRegex.test(identifier)) {
        return 'Số điện thoại phải gồm đúng 10 chữ số và bắt đầu bằng số 0.';
      }
    }
    return null;
  };

  const requestOtp = async (event?: FormEvent) => {
    if (event) event.preventDefault();
    const validationError = validateInput();
    if (validationError) {
      setError(validationError);
      return;
    }

    const identifier = method === 'email' ? email.trim() : phone.trim();
    setError('');
    setLoading(true);

    try {
      await apiRequest<{ message: string }>(`/auth/forgot-password/${method}`, {
        method: 'POST',
        body: JSON.stringify({ [method]: identifier }),
      });
      setStep('otp');
      setDigits(Array(OTP_LENGTH).fill(''));
      setCountdown(COUNTDOWN_SECONDS);
      toast(
        method === 'email'
          ? 'Mã xác thực OTP đã được gửi đến email của bạn!'
          : 'Mã xác thực OTP đã được gửi qua tin nhắn SMS!',
        'success'
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Không thể gửi mã xác thực.';
      setError(message);
      toast(message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (countdown > 0 || resending) return;
    const identifier = method === 'email' ? email.trim() : phone.trim();
    setError('');
    setResending(true);

    try {
      await apiRequest<{ message: string }>(`/auth/forgot-password/${method}`, {
        method: 'POST',
        body: JSON.stringify({ [method]: identifier }),
      });
      setCountdown(COUNTDOWN_SECONDS);
      setDigits(Array(OTP_LENGTH).fill(''));
      toast('Đã gửi lại mã xác thực thành công!', 'success');
      setTimeout(() => inputRefs.current[0]?.focus(), 100);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Không thể gửi lại mã xác thực.';
      setError(message);
      toast(message, 'error');
    } finally {
      setResending(false);
    }
  };

  const handleDigitChange = (index: number, val: string) => {
    const clean = val.replace(/\D/g, '');
    if (error) setError('');

    if (!clean) {
      const updated = [...digits];
      updated[index] = '';
      setDigits(updated);
      return;
    }

    // Single digit input
    const char = clean.slice(-1);
    const updated = [...digits];
    updated[index] = char;
    setDigits(updated);

    if (index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasteData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, OTP_LENGTH);
    if (!pasteData) return;

    const updated = [...digits];
    for (let i = 0; i < pasteData.length; i++) {
      updated[i] = pasteData[i];
    }
    setDigits(updated);

    const focusIndex = Math.min(pasteData.length, OTP_LENGTH - 1);
    inputRefs.current[focusIndex]?.focus();
  };

  const submitOtp = async (event?: FormEvent) => {
    if (event) event.preventDefault();
    const otpCode = digits.join('').trim();
    if (otpCode.length !== OTP_LENGTH) {
      setError('Vui lòng nhập đủ 6 chữ số mã OTP.');
      return;
    }

    setError('');
    setLoading(true);

    try {
      const identifier = method === 'email' ? email.trim() : phone.trim();
      const result = await apiRequest<{ token: string; message: string }>('/auth/verify-otp', {
        method: 'POST',
        body: JSON.stringify({
          channel: method,
          identifier,
          otp: otpCode,
        }),
      });
      toast('Xác thực OTP thành công!', 'success');
      navigate(`/reset-password?token=${encodeURIComponent(result.token)}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Mã OTP không hợp lệ hoặc đã hết hạn.';
      setError(message);
      toast(message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const destination = method === 'email' ? email.trim() : phone.trim();
  const isOtpComplete = digits.every((d) => d.length === 1);

  if (step === 'otp') {
    return (
      <AuthShell
        title="Nhập mã xác thực OTP"
        description={`Mã xác thực gồm 6 chữ số đã được gửi đến ${method === 'email' ? 'email' : 'số điện thoại'}:`}
      >
        <div className="mb-5 flex items-center justify-between rounded-xl bg-slate-50 p-3.5 border border-slate-200">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700">
              {method === 'email' ? <Mail size={16} /> : <Phone size={16} />}
            </span>
            <span className="truncate text-sm font-semibold text-slate-800">{destination}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              setStep('form');
              setError('');
            }}
            className="shrink-0 text-xs font-semibold text-brand-700 hover:text-brand-800 transition underline ml-2"
          >
            Đổi thông tin
          </button>
        </div>

        <form onSubmit={submitOtp} noValidate className="space-y-5">
          <div>
            <label className="mb-2 block text-center text-xs font-semibold text-slate-600">
              MÃ XÁC THỰC (6 CHỮ SỐ)
            </label>
            <div className="flex justify-between gap-2 sm:gap-3" onPaste={handlePaste}>
              {digits.map((digit, idx) => (
                <input
                  key={idx}
                  ref={(el) => {
                    inputRefs.current[idx] = el;
                  }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleDigitChange(idx, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(idx, e)}
                  className={`h-13 w-11 sm:w-12 rounded-xl border text-center text-xl font-bold transition focus:outline-none focus:ring-2 ${
                    error
                      ? 'border-red-400 bg-red-50/40 text-red-700 focus:border-red-500 focus:ring-red-200'
                      : digit
                      ? 'border-brand-600 bg-brand-50/20 text-brand-900 focus:border-brand-600 focus:ring-brand-200'
                      : 'border-slate-300 bg-white text-slate-900 focus:border-brand-600 focus:ring-brand-200'
                  }`}
                />
              ))}
            </div>
            {error && (
              <p className="mt-2 text-center text-xs font-medium text-red-600 animate-fade-in">
                {error}
              </p>
            )}
          </div>

          <Button
            type="submit"
            size="lg"
            disabled={!isOtpComplete || loading}
            loading={loading}
            className="w-full rounded-xl shadow-[0_8px_20px_rgba(13,135,76,0.2)]"
          >
            Xác nhận mã OTP
          </Button>

          <div className="flex items-center justify-between pt-1 text-sm">
            <button
              type="button"
              onClick={handleResendOtp}
              disabled={countdown > 0 || resending}
              className={`flex items-center gap-1.5 font-medium transition ${
                countdown > 0
                  ? 'cursor-not-allowed text-slate-400'
                  : 'text-brand-700 hover:text-brand-800 underline'
              }`}
            >
              {countdown > 0 ? (
                <>
                  <Clock size={15} />
                  <span>Gửi lại mã sau ({countdown}s)</span>
                </>
              ) : (
                <>
                  <RefreshCw size={15} className={resending ? 'animate-spin' : ''} />
                  <span>Gửi lại mã OTP</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => {
                setStep('form');
                setError('');
              }}
              className="flex items-center gap-1 font-semibold text-slate-500 hover:text-slate-700 transition"
            >
              <ArrowLeft size={15} />
              <span>Quay lại</span>
            </button>
          </div>
        </form>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Quên mật khẩu?"
      description="Chọn phương thức xác thực để nhận mã khôi phục tài khoản."
    >
      <div className="mb-5 flex rounded-xl border bg-slate-100/80 p-1">
        <button
          type="button"
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-sm font-semibold transition ${
            method === 'email'
              ? 'bg-white text-brand-700 shadow-sm'
              : 'text-slate-500 hover:text-slate-800'
          }`}
          onClick={() => {
            setMethod('email');
            setError('');
          }}
        >
          <Mail size={16} /> Email
        </button>
        <button
          type="button"
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-sm font-semibold transition ${
            method === 'phone'
              ? 'bg-white text-brand-700 shadow-sm'
              : 'text-slate-500 hover:text-slate-800'
          }`}
          onClick={() => {
            setMethod('phone');
            setError('');
          }}
        >
          <Phone size={16} /> Số điện thoại
        </button>
      </div>

      <form onSubmit={requestOtp} noValidate className="space-y-4">
        {method === 'email' ? (
          <Input
            label="Email tài khoản"
            type="email"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              if (error) setError('');
            }}
            error={error}
            leftIcon={<Mail size={17} />}
            placeholder="example@gmail.com"
          />
        ) : (
          <Input
            label="Số điện thoại đã đăng ký"
            type="tel"
            inputMode="numeric"
            autoFocus
            maxLength={10}
            value={phone}
            onChange={(event) => {
              setPhone(event.target.value.replace(/\D/g, '').slice(0, 10));
              if (error) setError('');
            }}
            error={error}
            leftIcon={<Phone size={17} />}
            placeholder="0912345678"
          />
        )}

        <Button
          type="submit"
          size="lg"
          loading={loading}
          className="w-full rounded-xl shadow-[0_8px_20px_rgba(13,135,76,0.2)]"
        >
          Gửi mã OTP
        </Button>
      </form>

      <Link
        to="/login"
        className="mt-6 flex items-center justify-center gap-1.5 text-center text-sm font-semibold text-brand-700 hover:text-brand-800 transition"
      >
        <ArrowLeft size={15} />
        <span>Quay lại đăng nhập</span>
      </Link>
    </AuthShell>
  );
}