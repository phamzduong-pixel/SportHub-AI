import { useEffect, useRef, useState, type ReactNode } from 'react';

interface Item { label: string; icon?: ReactNode; onClick: () => void; danger?: boolean; }
export function Dropdown({ trigger, items, align = 'right' }: { trigger: ReactNode; items: Item[]; align?: 'left' | 'right' }) {
  const [open, setOpen] = useState(false); const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { const close = (event: MouseEvent) => !ref.current?.contains(event.target as Node) && setOpen(false); document.addEventListener('mousedown', close); return () => document.removeEventListener('mousedown', close); }, []);
  return <div ref={ref} className="relative"><button type="button" onClick={() => setOpen((value) => !value)}>{trigger}</button>{open && <div className={`absolute top-full z-30 mt-2 min-w-44 rounded-lg border border-slate-200 bg-white p-1.5 shadow-card ${align === 'right' ? 'right-0' : 'left-0'}`}>{items.map((item) => <button key={item.label} onClick={() => { item.onClick(); setOpen(false); }} className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-slate-50 ${item.danger ? 'text-red-600' : 'text-slate-700'}`}>{item.icon}{item.label}</button>)}</div>}</div>;
}
