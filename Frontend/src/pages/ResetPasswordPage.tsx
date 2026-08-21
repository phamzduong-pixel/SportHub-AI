import { ArrowLeft, CheckCircle2, Eye, EyeOff, Lock, ShieldCheck } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AuthShell } from '@/components/auth/AuthShell';
import { Button, Input, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';

export function ResetPasswordPage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  if (!token) {
    return (
      <AuthShell title="Liên kết không hợp lệ" description="">
        <div className="text-center">
          <p className="text-sm text-slate-500">
            Liên kết hoặc mã xác thực đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.
          </p>
          <Link to="/forgot-password">
            <Button className="mt-6 w-full rounded-xl" variant="outline">
              Yêu cầu gửi lại mã OTP
            </Button>
          </Link>
          <Link
            to="/login"
            className="mt-4 flex items-center justify-center gap-1.5 text-center text-sm font-semibold text-brand-700 hover:text-brand-800"
          >
            <ArrowLeft size={15} />
            <span>Quay lại đăng nhập</span>
          </Link>
        </div>
      </AuthShell>
    );
  }

  const hasMinLength = newPassword.length >= 8;
  const hasNumber = /[0-9]/.test(newPassword);
  const hasLetter = /[a-zA-Z]/.test(newPassword);
  const isMatch = newPassword && confirmPassword && newPassword === confirmPassword;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (newPassword.length < 8) {
      setError('Mật khẩu mới phải có ít nhất 8 ký tự.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await apiRequest<{ message: string }>('/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({
          token,
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });
      setSuccess(true);
      toast('Đặt lại mật khẩu thành công!', 'success');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Không thể đặt lại mật khẩu.';
      setError(msg);
      toast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <AuthShell title="Đặt lại mật khẩu thành công" description="">
        <div className="text-center py-2">
          <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-emerald-50 text-emerald-600 shadow-inner">
            <CheckCircle2 size={36} />
          </span>
          <h2 className="mt-4 text-lg font-bold text-slate-900">Mật khẩu đã được cập nhật!</h2>
          <p className="mt-2 text-sm text-slate-500">
            Tài khoản của bạn đã được cập nhật mật khẩu mới. Bạn có thể đăng nhập ngay bây giờ.
          </p>
          <Link to="/login">
            <Button size="lg" className="mt-6 w-full rounded-xl shadow-[0_8px_20px_rgba(13,135,76,0.2)]">
              Đăng nhập ngay
            </Button>
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Tạo mật khẩu mới"
      description="Nhập mật khẩu mới an toàn cho tài khoản SportHub AI của bạn."
    >
      <form onSubmit={submit} noValidate className="space-y-4">
        <Input
          label="Mật khẩu mới"
          type={showPassword ? 'text' : 'password'}
          autoFocus
          value={newPassword}
          onChange={(e) => {
            setNewPassword(e.target.value);
            if (error) setError('');
          }}
          leftIcon={<Lock size={17} />}
          rightIcon={
            <button
              type="button"
              tabIndex={-1}
              className="text-slate-400 hover:text-slate-600 transition"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          }
          placeholder="Tối thiểu 8 ký tự"
        />

        <Input
          label="Xác nhận mật khẩu mới"
          type={showConfirm ? 'text' : 'password'}
          value={confirmPassword}
          onChange={(e) => {
            setConfirmPassword(e.target.value);
            if (error) setError('');
          }}
          error={error}
          leftIcon={<Lock size={17} />}
          rightIcon={
            <button
              type="button"
              tabIndex={-1}
              className="text-slate-400 hover:text-slate-600 transition"
              onClick={() => setShowConfirm(!showConfirm)}
            >
              {showConfirm ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          }
          placeholder="Nhập lại mật khẩu mới"
        />

        {newPassword && (
          <div className="rounded-lg bg-slate-50 p-3 text-xs space-y-1.5 border border-slate-200">
            <p className="font-semibold text-slate-700">Yêu cầu bảo mật:</p>
            <div className="flex items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${hasMinLength ? 'bg-emerald-500' : 'bg-slate-300'}`} />
              <span className={hasMinLength ? 'text-emerald-700 font-medium' : 'text-slate-500'}>
                Ít nhất 8 ký tự
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${hasLetter && hasNumber ? 'bg-emerald-500' : 'bg-slate-300'}`} />
              <span className={hasLetter && hasNumber ? 'text-emerald-700 font-medium' : 'text-slate-500'}>
                Bao gồm cả chữ cái và chữ số
              </span>
            </div>
            {confirmPassword && (
              <div className="flex items-center gap-2">
                <span className={`h-1.5 w-1.5 rounded-full ${isMatch ? 'bg-emerald-500' : 'bg-red-400'}`} />
                <span className={isMatch ? 'text-emerald-700 font-medium' : 'text-red-600'}>
                  {isMatch ? 'Mật khẩu xác nhận khớp' : 'Mật khẩu xác nhận chưa khớp'}
                </span>
              </div>
            )}
          </div>
        )}

        <Button
          type="submit"
          size="lg"
          loading={loading}
          disabled={!hasMinLength || newPassword !== confirmPassword}
          className="w-full rounded-xl shadow-[0_8px_20px_rgba(13,135,76,0.2)]"
        >
          Cập nhật mật khẩu mới
        </Button>

        <Link
          to="/login"
          className="mt-4 flex items-center justify-center gap-1.5 text-center text-sm font-semibold text-brand-700 hover:text-brand-800 transition"
        >
          <ArrowLeft size={15} />
          <span>Quay lại đăng nhập</span>
        </Link>
      </form>
    </AuthShell>
  );
}

