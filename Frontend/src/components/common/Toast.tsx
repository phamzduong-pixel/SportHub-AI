import { CheckCircle2, Info, X, XCircle } from 'lucide-react';
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

type ToastType = 'success' | 'error' | 'info';
interface ToastItem { id: number; message: string; type: ToastType; }
const ToastContext = createContext<{ toast: (message: string, type?: ToastType) => void } | null>(null);
const icons = { success: CheckCircle2, error: XCircle, info: Info };
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const remove = useCallback((id: number) => setItems((current) => current.filter((item) => item.id !== id)), []);
  const toast = useCallback((message: string, type: ToastType = 'success') => { const id = Date.now(); setItems((current) => [...current, { id, message, type }]); window.setTimeout(() => remove(id), 3500); }, [remove]);
  const value = useMemo(() => ({ toast }), [toast]);
  return <ToastContext.Provider value={value}>{children}<div aria-live="polite" className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-[60] grid max-w-sm gap-2 sm:left-auto sm:right-4 sm:w-[calc(100%-2rem)]">{items.map((item) => { const Icon = icons[item.type]; return <div key={item.id} className="flex min-w-0 items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-float"><Icon size={19} className={item.type === 'success' ? 'text-brand-600' : item.type === 'error' ? 'text-red-600' : 'text-sportblue-500'} /><p className="min-w-0 flex-1 break-words text-sm font-medium text-slate-700">{item.message}</p><button aria-label="Đóng" onClick={() => remove(item.id)}><X size={16} /></button></div>; })}</div></ToastContext.Provider>;
}
export function useToast() { const context = useContext(ToastContext); if (!context) throw new Error('useToast phải nằm trong ToastProvider'); return context; }
