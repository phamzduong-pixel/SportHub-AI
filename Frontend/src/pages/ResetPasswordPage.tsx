import { CheckCircle2, Eye, EyeOff, Lock } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AuthShell } from '@/components/auth/AuthShell';
import { Button, Input, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';

export function ResetPasswordPage() {
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  if (!token) {
    return (
      <AuthShell title="Liên kết không hợp lệ" description="">
        <div className="text-center">
          <p className="text-sm text-slate-500">
            Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.
          </p>
          <Link to="/forgot-password">
            <Button className="mt-6 w-full" variant="outline">Gửi lại liên kết</Button>
          </Link>
          <Link to="/login" className="mt-3 block text-center text-sm font-semibold text-brand-700">
            ← Quay lại đăng nhập
          </Link>
        </div>
      </AuthShell>
    );
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (newPassword.length < 8) {
      setError('Mật khẩu phải có ít nhất 8 ký tự.');
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
        <div className="text-center">
          <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-emerald-50 text-emerald-600">
            <CheckCircle2 size={32} />
          </span>
          <h2 className="mt-4 font-bold text-emerald-700">Mật khẩu đã được cập nhật</h2>
          <p className="mt-2 text-sm text-slate-500">
            Bạn có thể đăng nhập bằng mật khẩu mới ngay bây giờ.
          </p>
          <Link to="/login">
            <Button className="mt-6 w-full">Đăng nhập ngay</Button>
          </Link>
        </div>
      </AuthShell>
    );
  }

  const toggleIcon = showPassword
    ? <EyeOff size={17} className="cursor-pointer text-slate-400" onClick={() => setShowPassword(false)} />
    : <Eye size={17} className="cursor-pointer text-slate-400" onClick={() => setShowPassword(true)} />;

  return (
    <AuthShell title="Đặt lại mật khẩu" description="Nhập mật khẩu mới cho tài khoản của bạn.">
      <form onSubmit={submit} noValidate className="space-y-4">
        <Input
          label="Mật khẩu mới"
          type={showPassword ? 'text' : 'password'}
          autoFocus
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          leftIcon={<Lock size={17} />}
          rightIcon={toggleIcon}
          placeholder="Tối thiểu 8 ký tự"
        />
        <Input
          label="Xác nhận mật khẩu"
          type={showPassword ? 'text' : 'password'}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          error={error}
          leftIcon={<Lock size={17} />}
          placeholder="Nhập lại mật khẩu mới"
        />
        <Button type="submit" size="lg" loading={loading} className="w-full">
          Đặt lại mật khẩu
        </Button>
        <Link to="/login" className="block text-center text-sm font-semibold text-brand-700">
          ← Quay lại đăng nhập
        </Link>
      </form>
    </AuthShell>
  );
}
