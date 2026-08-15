import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

let bodyLockCount = 0;
let bodyOverflowBeforeLock = '';

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}

export function Modal({ open, onClose, title, description, children }: Props) {
  const titleId = useId();
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onCloseRef.current();
    document.addEventListener('keydown', onKey);
    if (bodyLockCount === 0) bodyOverflowBeforeLock = document.body.style.overflow;
    bodyLockCount += 1;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      bodyLockCount = Math.max(0, bodyLockCount - 1);
      if (bodyLockCount === 0) document.body.style.overflow = bodyOverflowBeforeLock;
    };
  }, [open]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center overflow-hidden bg-slate-950/45 p-2 sm:p-4" onMouseDown={(event) => event.target === event.currentTarget && onCloseRef.current()}>
      <section role="dialog" aria-modal="true" aria-labelledby={titleId} className="my-auto flex max-h-[calc(100dvh-1rem)] w-full min-w-0 max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-float sm:max-h-[calc(100dvh-2rem)] sm:rounded-card">
        <div className="flex min-w-0 shrink-0 items-start justify-between gap-3 px-4 pt-4 sm:gap-4 sm:px-6 sm:pt-6">
          <div className="min-w-0">
            <h2 id={titleId} className="break-words text-lg font-bold text-slate-900">{title}</h2>
            {description && <p className="mt-1 break-words text-sm text-slate-500">{description}</p>}
          </div>
          <button type="button" onClick={() => onCloseRef.current()} aria-label="Đóng" className="grid h-10 w-10 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"><X size={20} /></button>
        </div>
        <div className="modal-scrollbar mt-4 min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain px-4 pb-4 sm:mt-5 sm:px-6 sm:pb-6">{children}</div>
      </section>
    </div>,
    document.body,
  );
}
