import { MapPin, Navigation } from 'lucide-react';
import type { Venue } from '@/types/index';

export function MapMock({ venues, selectedId, onSelect, className = '' }: { venues: Venue[]; selectedId?: number; onSelect?: (id: number) => void; className?: string }) {
  return <div className={`relative min-h-[360px] overflow-hidden rounded-card border border-slate-200 bg-[#e9efe8] ${className}`}>
    <div className="absolute inset-0 opacity-60" style={{ backgroundImage: 'linear-gradient(35deg, transparent 45%, #cbd9c8 46%, #cbd9c8 49%, transparent 50%), linear-gradient(120deg, transparent 44%, #d3dfd1 45%, #d3dfd1 48%, transparent 49%)', backgroundSize: '90px 90px, 130px 130px' }} />
    <div className="absolute left-[12%] top-[18%] h-2/3 w-3/4 rotate-6 rounded-[45%] border-[18px] border-blue-200/70" />
    {venues.slice(0, 7).map((venue, index) => <button key={venue.id} type="button" onClick={() => onSelect?.(venue.id)} className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 rounded-full px-2.5 py-1.5 text-xs font-bold shadow-md transition hover:scale-110 ${selectedId === venue.id ? 'bg-sportblue-600 text-white ring-4 ring-blue-200' : 'bg-white text-brand-700'}`} style={{ left: `${18 + (index * 29) % 68}%`, top: `${20 + (index * 23) % 62}%` }}>{(venue.price / 1000).toFixed(0)}K</button>)}
    <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 rounded-lg bg-white/95 px-3 py-2 text-xs font-medium text-slate-600 shadow"><Navigation size={15} className="text-sportblue-600" />Bản đồ mô phỏng khu vực</div>
    <div className="absolute right-4 top-4 z-10 grid h-9 w-9 place-items-center rounded-lg bg-white text-brand-700 shadow"><MapPin size={18} /></div>
  </div>;
}
