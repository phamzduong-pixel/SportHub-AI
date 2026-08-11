import { ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export interface BreadcrumbItem { label: string; href?: string; }
export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) { return <nav aria-label="Breadcrumb" className="mb-2 flex flex-wrap items-center gap-1 text-sm text-slate-500">{items.map((item, index) => <span key={`${item.label}-${index}`} className="flex items-center gap-1">{index > 0 && <ChevronRight size={14} />}{item.href ? <Link className="hover:text-brand-700" to={item.href}>{item.label}</Link> : <span className="text-slate-700">{item.label}</span>}</span>)}</nav>; }
