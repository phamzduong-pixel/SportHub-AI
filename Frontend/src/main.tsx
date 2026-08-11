import { StrictMode } from 'react'; import { createRoot } from 'react-dom/client';
import { ToastProvider } from '@/components/common'; import { AppRouter } from '@/routes/AppRouter'; import '@/styles/globals.css';
import { AuthProvider } from '@/contexts/AuthContext';

createRoot(document.getElementById('root')!).render(<StrictMode><ToastProvider><AuthProvider><AppRouter /></AuthProvider></ToastProvider></StrictMode>);
