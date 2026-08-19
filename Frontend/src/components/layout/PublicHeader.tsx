import { AlertCircle, Bell, Bot, Building2, CalendarDays, ChevronDown, Gift, Heart, LogOut, Menu, ShieldCheck, UserRound } from 'lucide-react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Button, Drawer, Dropdown } from '@/components/common';
import { useAuth } from '@/contexts/AuthContext';
import { useDisclosure } from '@/hooks/useDisclosure';
import { Logo } from './Logo';

const links = [{ to: '/', label: 'Trang chủ' }, { to: '/venues', label: 'Tìm sân' }, { to: '/ai-assistant', label: 'Trợ lý AI', ai: true }];
const initials = (name: string) => name.split(/\s+/).slice(-2).map((part) => part[0]).join('').toUpperCase();

export function PublicHeader() {
  const drawer = useDisclosure(); const navigate = useNavigate(); const { user, loading, logout } = useAuth();
  const navClass = ({ isActive }: { isActive: boolean }) => `py-2 text-sm font-semibold transition ${isActive ? 'text-brand-700' : 'text-slate-600 hover:text-brand-700'}`;
  const signOut = () => { logout(); drawer.close(); navigate('/login', { replace: true }); };
  const accountItems = user?.role === 'CUSTOMER' ? [
    { label: 'Hồ sơ cá nhân', icon: <UserRound size={16} />, onClick: () => navigate('/customer/profile') },
    { label: 'Lịch đặt sân của tôi', icon: <CalendarDays size={16} />, onClick: () => navigate('/customer/bookings') },
    { label: 'Đánh giá sân', icon: <UserRound size={16} />, onClick: () => navigate('/customer/reviews') },
    { label: 'Khiếu nại của tôi', icon: <AlertCircle size={16} />, onClick: () => navigate('/customer/complaints') },
    { label: 'Sân yêu thích', icon: <Heart size={16} />, onClick: () => navigate('/customer/favorites') },
    { label: 'Thông báo', icon: <Bell size={16} />, onClick: () => navigate('/customer/notifications') },
    { label: 'Đăng xuất', icon: <LogOut size={16} />, danger: true, onClick: signOut },
  ] : user?.role === 'SYSTEM_ADMIN' ? [
    { label: 'Quản trị hệ thống', icon: <ShieldCheck size={16} />, onClick: () => navigate('/system-admin') },
    { label: 'Thông báo', icon: <Bell size={16} />, onClick: () => navigate('/notifications') },
    { label: 'Đăng xuất', icon: <LogOut size={16} />, danger: true, onClick: signOut },
  ] : [
    { label: 'Vào trang quản lý', icon: <Building2 size={16} />, onClick: () => navigate('/management/dashboard') },
    { label: 'Thông báo', icon: <Bell size={16} />, onClick: () => navigate('/notifications') },
    { label: 'Hồ sơ cá nhân', icon: <UserRound size={16} />, onClick: () => navigate('/customer/profile') },
    { label: 'Lịch đặt sân của tôi', icon: <CalendarDays size={16} />, onClick: () => navigate('/customer/bookings') },
    { label: 'Sân yêu thích', icon: <Heart size={16} />, onClick: () => navigate('/customer/favorites') },
    { label: 'Đăng xuất', icon: <LogOut size={16} />, danger: true, onClick: signOut },
  ];
  return <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/95 backdrop-blur"><div className="mx-auto flex h-16 max-w-7xl items-center gap-5 px-4 sm:px-6"><Logo /><nav aria-label="Điều hướng chính" className="ml-auto hidden items-center gap-6 xl:flex">{links.map((link) => <NavLink end={link.to === '/'} key={link.to} to={link.to} className={({ isActive }) => `${navClass({ isActive })} ${link.ai ? 'flex items-center gap-1.5 text-ai-600' : ''}`}>{link.ai && <Bot size={16} />}{link.label}</NavLink>)}<a href="/#sports" className="py-2 text-sm font-semibold text-slate-600">Môn thể thao</a><a href="/#offers" className="flex items-center gap-1.5 py-2 text-sm font-semibold text-slate-600"><Gift size={15} />Ưu đãi</a></nav><div className="ml-auto hidden items-center gap-2 sm:flex xl:ml-2">{!loading && (user ? <Dropdown trigger={<span className="flex items-center gap-2 rounded-xl p-1.5 hover:bg-slate-50">{user.avatar_url ? <img src={user.avatar_url} alt="" className="h-8 w-8 rounded-full object-cover" /> : <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">{initials(user.full_name)}</span>}<span className="hidden max-w-32 truncate text-sm font-semibold lg:block">{user.full_name}</span><ChevronDown size={14} /></span>} items={accountItems} /> : <><Link to="/login"><Button variant="ghost">Đăng nhập</Button></Link><Link to="/register"><Button>Đăng ký</Button></Link></>)}</div><button onClick={drawer.open} className="ml-auto rounded-lg p-2 text-slate-700 sm:ml-0 xl:hidden" aria-label="Mở menu"><Menu /></button></div><Drawer open={drawer.isOpen} onClose={drawer.close} title="Danh mục"><nav className="grid gap-1">{links.map((link) => <NavLink end={link.to === '/'} key={link.to} to={link.to} onClick={drawer.close} className={navClass}>{link.label}</NavLink>)}<hr className="my-3 border-slate-200" />{user ? <>{user.role === 'CUSTOMER' && <><Link to="/customer/profile" onClick={drawer.close} className="py-2 text-sm font-semibold">Hồ sơ cá nhân</Link><Link to="/customer/bookings" onClick={drawer.close} className="py-2 text-sm font-semibold">Lịch đặt sân của tôi</Link></>}{user.role === 'SYSTEM_ADMIN' && <Link to="/system-admin" onClick={drawer.close} className="py-2 text-sm font-semibold">Quản trị hệ thống</Link>}{user.role === 'OWNER' && <Link to="/management/dashboard" onClick={drawer.close} className="py-2 text-sm font-semibold">Vào trang quản lý</Link>}<Button variant="danger" className="mt-2 w-full" onClick={signOut}>Đăng xuất</Button></> : <><Link to="/login" onClick={drawer.close}><Button variant="outline" className="w-full">Đăng nhập</Button></Link><Link to="/register" onClick={drawer.close}><Button className="mt-2 w-full">Đăng ký miễn phí</Button></Link></>}</nav></Drawer></header>;
}
