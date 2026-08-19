import type { InputHTMLAttributes, ReactNode } from 'react';
import { cn } from '@/utils/cn';

interface Props extends InputHTMLAttributes<HTMLInputElement> { label?: string; hint?: string; error?: string; leftIcon?: ReactNode; rightIcon?: ReactNode; }
export function Input({ label, hint, error, leftIcon, rightIcon, className, id, ...props }: Props) {
  const inputId = id ?? props.name;
  return <label htmlFor={inputId} className="block min-w-0 text-sm font-medium text-slate-700">{label && <span className="mb-1.5 block">{label}</span>}<span className="relative block min-w-0">{leftIcon && <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">{leftIcon}</span>}<input id={inputId} className={cn('h-11 min-w-0 w-full rounded-xl border bg-white/90 px-3 text-base outline-none transition placeholder:text-slate-400 hover:border-slate-400 focus:border-brand-500 focus:ring-4 focus:ring-brand-50 sm:h-10 sm:text-sm', Boolean(leftIcon) && 'pl-10', Boolean(rightIcon) && 'pr-10', error ? 'border-red-400' : 'border-slate-300', className)} {...props} />{rightIcon && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">{rightIcon}</span>}</span>{(error || hint) && <span className={cn('mt-1 block text-xs', error ? 'text-red-600' : 'text-slate-500')}>{error || hint}</span>}</label>;
}
