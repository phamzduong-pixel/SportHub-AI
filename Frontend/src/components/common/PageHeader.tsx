import type { ReactNode } from 'react';
import { Breadcrumb, type BreadcrumbItem } from './Breadcrumb';

interface Props { title: string; description?: string; breadcrumb?: BreadcrumbItem[]; actions?: ReactNode; action?: ReactNode; }

export function PageHeader({ title, description, breadcrumb, actions, action }: Props) {
  const controls = actions ?? action;
  return <header className="mb-5 flex min-w-0 flex-col justify-between gap-4 sm:mb-6 sm:flex-row sm:items-end">
    <div className="min-w-0">
      {breadcrumb && <Breadcrumb items={breadcrumb} />}
      <h1 className="break-words text-xl font-bold tracking-tight text-slate-900 min-[375px]:text-2xl sm:text-3xl">{title}</h1>
      {description && <p className="mt-1.5 max-w-2xl break-words text-sm leading-6 text-slate-500">{description}</p>}
    </div>
    {controls && <div className="flex w-full min-w-0 flex-wrap gap-2 sm:w-auto sm:shrink-0">{controls}</div>}
  </header>;
}
