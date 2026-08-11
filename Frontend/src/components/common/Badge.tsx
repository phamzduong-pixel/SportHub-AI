import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/utils/cn';

export type BadgeVariant = 'success' | 'warning' | 'info' | 'neutral' | 'danger' | 'ai';
interface Props extends HTMLAttributes<HTMLSpanElement> { children: ReactNode; variant?: BadgeVariant; dot?: boolean; }

const styles: Record<BadgeVariant, string> = {
  success: 'border-emerald-200 bg-[rgb(var(--success-soft))] text-emerald-700',
  warning: 'border-amber-200 bg-[rgb(var(--warning-soft))] text-amber-700',
  info: 'border-cyan-200 bg-[rgb(var(--info-soft))] text-cyan-800',
  neutral: 'border-slate-200 bg-slate-100 text-slate-600',
  danger: 'border-red-200 bg-[rgb(var(--danger-soft))] text-red-700',
  ai: 'border-teal-200 bg-[rgb(var(--ai-soft))] text-teal-700',
};

export function Badge({ children, variant = 'neutral', dot, className, ...props }: Props) {
  const label = typeof children === 'string' ? children.toLocaleLowerCase('vi') : '';
  const inferred: BadgeVariant = /hủy|thất bại|từ chối|quá hạn|không thành công|no.?show|failed|cancelled|rejected|overdue/.test(label)
    ? 'danger'
    : /khiếu nại|đang sử dụng|đang diễn ra|in.progress|disputed/.test(label)
      ? 'info'
      : /đã xác nhận|hoàn thành|đã thanh toán|đã hoàn tiền|hoạt động|available|confirmed|completed|paid|refunded/.test(label)
        ? 'success'
        : /chờ|đang xử lý|đặt cọc|pending|partial|unpaid/.test(label)
          ? 'warning'
          : variant;
  const effectiveVariant = variant === 'neutral' ? inferred : variant;
  return <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold', styles[effectiveVariant], className)} {...props}>{dot && <i className="h-1.5 w-1.5 rounded-full bg-current" />}{children}</span>;
}
