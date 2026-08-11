import { Outlet } from 'react-router-dom';
import { PublicFooter } from '@/components/layout/PublicFooter';
import { PublicHeader } from '@/components/layout/PublicHeader';
import { ScrollToTop } from '@/components/layout/ScrollToTop';

export function PublicLayout() {
  return <div className="app-canvas min-h-screen"><ScrollToTop /><PublicHeader /><main><Outlet /></main><PublicFooter /></div>;
}
