import { ChevronDown } from 'lucide-react';
import type { SelectHTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

interface Option { label: string; value: string; }
interface Props extends SelectHTMLAttributes<HTMLSelectElement> { label?: string; options: Option[]; placeholder?: string; }
export function Select({ label, options, placeholder, className, id, ...props }: Props) {
  return <label htmlFor={id} className="block min-w-0 text-sm font-medium text-slate-700">{label && <span className="mb-1.5 block">{label}</span>}<span className="relative block min-w-0"><select id={id} className={cn('h-11 min-w-0 w-full appearance-none rounded-lg border border-slate-300 bg-white px-3 pr-9 text-base outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-50 sm:h-10 sm:text-sm', className)} {...props}>{placeholder && <option value="">{placeholder}</option>}{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select><ChevronDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" /></span></label>;
}
