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
  return <ToastContext.Provider value={value}>{children}<div aria-live="polite" className="fixed bottom-4 right-4 z-[60] grid w-[calc(100%-2rem)] max-w-sm gap-2">{items.map((item) => { const Icon = icons[item.type]; return <div key={item.id} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-float"><Icon size={19} className={item.type === 'success' ? 'text-brand-600' : item.type === 'error' ? 'text-red-600' : 'text-sportblue-500'} /><p className="flex-1 text-sm font-medium text-slate-700">{item.message}</p><button aria-label="Đóng" onClick={() => remove(item.id)}><X size={16} /></button></div>; })}</div></ToastContext.Provider>;
}
export function useToast() { const context = useContext(ToastContext); if (!context) throw new Error('useToast phải nằm trong ToastProvider'); return context; }
