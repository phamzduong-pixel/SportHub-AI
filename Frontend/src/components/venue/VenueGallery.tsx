import { Images } from 'lucide-react';
import { useState } from 'react';
import { Modal } from '@/components/common';

export function VenueGallery({ images, name }: { images: string[]; name: string }) {
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const gallery = images.length ? images : [''];

  return <>
    <div className="grid h-[220px] w-full min-w-0 gap-2 overflow-hidden rounded-xl sm:h-[340px] sm:rounded-card md:h-[420px] md:grid-cols-[1.6fr_1fr]">
      <button type="button" onClick={() => setOpen(true)} className="min-w-0 overflow-hidden bg-slate-200">
        <img src={gallery[active]} alt={`${name} - ảnh chính`} className="h-full w-full object-cover transition duration-300 hover:scale-[1.02]" />
      </button>
      <div className="hidden min-w-0 grid-cols-2 gap-2 md:grid">
        {gallery.slice(1, 5).map((image, index) => <button type="button" key={`thumb-${index + 1}-${image}`} onClick={() => setActive(index + 1)} className="relative min-w-0 overflow-hidden bg-slate-200"><img src={image} alt={`${name} - ảnh ${index + 2}`} className="h-full w-full object-cover transition hover:scale-105" />{index === 3 && <span className="absolute inset-0 grid place-items-center bg-slate-950/45 text-sm font-bold text-white"><span className="flex items-center gap-2"><Images size={18} />Xem tất cả ảnh</span></span>}</button>)}
      </div>
    </div>
    {gallery.length > 1 && <div className="mt-2 flex w-full snap-x gap-2 overflow-x-auto overscroll-x-contain pb-1 md:hidden">
      {gallery.map((image, index) => <button type="button" key={`strip-${index}-${image}`} onClick={() => setActive(index)} aria-label={`Xem ảnh ${index + 1}`} className={`h-12 w-[72px] shrink-0 snap-start overflow-hidden rounded-lg border-2 sm:h-16 sm:w-24 ${active === index ? 'border-brand-500' : 'border-transparent'}`}><img src={image} alt="" className="h-full w-full object-cover" /></button>)}
    </div>}
    <Modal open={open} onClose={() => setOpen(false)} title={`Ảnh ${name}`}>
      <div className="grid max-h-[65vh] grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">{gallery.map((image, index) => <button key={`modal-${index}-${image}`} onClick={() => { setActive(index); setOpen(false); }} className="min-w-0"><img src={image} alt={`${name} - ảnh ${index + 1}`} className="h-36 w-full rounded-lg object-cover sm:h-40" /></button>)}</div>
    </Modal>
  </>;
}
