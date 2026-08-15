import { X } from 'lucide-react';
import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

interface Props { open: boolean; onClose: () => void; title: string; children: ReactNode; }

export function Drawer({ open, onClose, title, children }: Props) {
  const titleId = useId();
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => event.key === 'Escape' && onCloseRef.current();
    document.addEventListener('keydown', close);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', close);
      document.body.style.overflow = previous;
    };
  }, [open]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/40" onMouseDown={(event) => event.target === event.currentTarget && onCloseRef.current()}>
      <aside role="dialog" aria-modal="true" aria-labelledby={titleId} className="ml-auto h-[100dvh] w-[min(100%,24rem)] max-w-full overflow-y-auto overflow-x-hidden overscroll-contain bg-white p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-float sm:p-5">
        <div className="flex min-w-0 items-center justify-between gap-3 border-b border-slate-200 pb-4">
          <h2 id={titleId} className="min-w-0 break-words font-bold text-slate-900">{title}</h2>
          <button type="button" aria-label="Đóng" onClick={() => onCloseRef.current()} className="grid h-10 w-10 shrink-0 place-items-center rounded-lg hover:bg-slate-100"><X size={20} /></button>
        </div>
        <div className="min-w-0 py-4 sm:py-5">{children}</div>
      </aside>
    </div>,
    document.body,
  );
}
