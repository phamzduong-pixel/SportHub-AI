import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/common';
import { apiRequest } from '@/services/apiClient';
import { ManagementCalendarPage } from './LiveManagementDataPages';

interface Maintenance { id: number; field_name: string; title: string; starts_at: string; ends_at: string; status: string; }

export function ManagementCalendarWithMaintenancePage() {
  const [items, setItems] = useState<Maintenance[]>([]);
  useEffect(() => { apiRequest<Maintenance[]>('/maintenance').then(setItems).catch(() => setItems([])); }, []);
  const active = items.filter((item) => item.status === 'SCHEDULED' || item.status === 'IN_PROGRESS');
  return <><section className="mb-5 rounded-card border border-amber-200 bg-amber-50 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold text-amber-900">Bảo trì trên lịch vận hành</h2><p className="text-xs text-amber-800">{active.length} lịch đang lên kế hoạch hoặc thực hiện; các slot tương ứng đã được khóa.</p></div><Link to="/management/maintenance"><Button size="sm" variant="outline">Quản lý bảo trì</Button></Link></div>{active.length > 0 && <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{active.slice(0, 6).map((item) => <article key={item.id} className="rounded-lg bg-white p-3 text-xs"><b>{item.field_name} · {item.title}</b><span className="block text-slate-500">{new Date(item.starts_at).toLocaleString('vi-VN')} – {new Date(item.ends_at).toLocaleString('vi-VN')}</span></article>)}</div>}</section><ManagementCalendarPage /></>;
}
