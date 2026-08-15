import { Bell } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getUnreadCount } from '@/services/notificationService';

export function NotificationBell() {
  const navigate = useNavigate(); const [count, setCount] = useState(0);
  useEffect(() => {
    let active = true;
    const load = () => getUnreadCount().then((result) => { if (active) setCount(result.unread_count); }).catch(() => undefined);
    void load(); const timer = window.setInterval(load, 60_000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  return <button type="button" onClick={() => navigate('/notifications')} className="relative grid h-10 w-10 place-items-center rounded-lg text-slate-600 hover:bg-slate-100" aria-label={count ? `${count} thông báo chưa đọc` : 'Thông báo'}><Bell size={19} />{count > 0 && <span className="absolute right-0 top-0 min-w-4 rounded-full bg-red-500 px-1 text-center text-[10px] font-bold leading-4 text-white">{count > 99 ? '99+' : count}</span>}</button>;
}
