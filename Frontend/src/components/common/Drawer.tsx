import { X } from 'lucide-react';
import { useEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

interface Props { open: boolean; onClose: () => void; title: string; children: ReactNode; }

export function Drawer({ open, onClose, title, children }: Props) {
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => event.key === 'Escape' && onClose();
    document.addEventListener('keydown', close);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', close);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/40" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside role="dialog" aria-modal="true" aria-labelledby="drawer-title" className="ml-auto h-full w-[min(100%,24rem)] max-w-full overflow-y-auto overflow-x-hidden bg-white p-4 shadow-float sm:p-5">
        <div className="flex min-w-0 items-center justify-between gap-3 border-b border-slate-200 pb-4">
          <h2 id="drawer-title" className="min-w-0 break-words font-bold text-slate-900">{title}</h2>
          <button aria-label="Đóng" onClick={onClose} className="grid h-10 w-10 shrink-0 place-items-center rounded-lg hover:bg-slate-100"><X size={20} /></button>
        </div>
        <div className="min-w-0 py-4 sm:py-5">{children}</div>
      </aside>
    </div>,
    document.body,
  );
}
