import { Inbox } from 'lucide-react';
import type { ReactNode } from 'react';

export function EmptyState({ title = 'Chưa có dữ liệu', description, action, icon }: { title?: string; description?: string; action?: ReactNode; icon?: ReactNode }) {
  return <div className="rounded-card border border-dashed border-brand-100 bg-brand-50/60 px-6 py-12 text-center"><div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full bg-white text-brand-600 shadow-sm">{icon ?? <Inbox size={21} />}</div><h3 className="font-semibold text-slate-900">{title}</h3>{description && <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">{description}</p>}{action && <div className="mt-4">{action}</div>}</div>;
}
