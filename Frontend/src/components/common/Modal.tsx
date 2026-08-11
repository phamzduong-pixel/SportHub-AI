import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { createPortal } from 'react-dom';

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}

export function Modal({ open, onClose, title, description, children }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/45 p-2 sm:p-4" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section role="dialog" aria-modal="true" aria-labelledby="modal-title" className="my-auto max-h-[calc(100dvh-1rem)] w-full min-w-0 max-w-lg overflow-y-auto overflow-x-hidden rounded-2xl bg-white p-4 shadow-float sm:max-h-[calc(100dvh-2rem)] sm:rounded-card sm:p-6">
        <div className="flex min-w-0 items-start justify-between gap-3 sm:gap-4">
          <div className="min-w-0">
            <h2 id="modal-title" className="break-words text-lg font-bold text-slate-900">{title}</h2>
            {description && <p className="mt-1 break-words text-sm text-slate-500">{description}</p>}
          </div>
          <button onClick={onClose} aria-label="Đóng" className="grid h-10 w-10 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"><X size={20} /></button>
        </div>
        <div className="mt-4 min-w-0 sm:mt-5">{children}</div>
      </section>
    </div>,
    document.body,
  );
}
