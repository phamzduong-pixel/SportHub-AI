import { LoaderCircle } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from '@/utils/cn';

type Variant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'ai';
interface Props extends ButtonHTMLAttributes<HTMLButtonElement> { variant?: Variant; size?: 'sm' | 'md' | 'lg'; loading?: boolean; leftIcon?: ReactNode; }
const variants: Record<Variant, string> = {
  primary: 'bg-brand-600 text-white shadow-sm shadow-emerald-200/70 hover:-translate-y-0.5 hover:bg-brand-700 hover:shadow-md hover:shadow-emerald-200/70', secondary: 'bg-sportblue-500 text-white shadow-sm hover:-translate-y-0.5 hover:bg-sportblue-600',
  outline: 'border border-slate-300 bg-white/90 text-slate-700 shadow-sm hover:-translate-y-0.5 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700', ghost: 'text-slate-600 hover:bg-brand-50 hover:text-brand-700',
  danger: 'bg-red-600 text-white shadow-sm hover:-translate-y-0.5 hover:bg-red-700', ai: 'bg-ai-500 text-white shadow-sm shadow-teal-100 hover:-translate-y-0.5 hover:bg-ai-600',
};
export function Button({ className, variant = 'primary', size = 'md', loading, leftIcon, children, disabled, ...props }: Props) {
  return <button className={cn('inline-flex max-w-full items-center justify-center gap-2 rounded-xl font-semibold transition duration-200 focus:outline-none focus:ring-4 focus:ring-brand-100 disabled:pointer-events-none disabled:opacity-50', variants[variant], size === 'sm' ? 'h-10 px-3 text-sm sm:h-9' : size === 'lg' ? 'h-12 px-5' : 'h-11 px-4 text-sm sm:h-10', className)} disabled={disabled || loading} {...props}>{loading ? <LoaderCircle size={16} className="animate-spin" /> : leftIcon}{children}</button>;
}
