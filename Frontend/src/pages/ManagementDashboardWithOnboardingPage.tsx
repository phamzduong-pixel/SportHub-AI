import { Building2, CheckCircle2, ClipboardList, MapPin, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, LoadingSkeleton, PageHeader, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';
import { ManagementDashboardPage } from './LiveManagementDataPages';

interface Facility { id: number; name: string; }

export function ManagementDashboardWithOnboardingPage() {
  const [facilities, setFacilities] = useState<Facility[]>();
  const { toast } = useToast();
  useEffect(() => { apiRequest<Facility[]>('/facilities').then(setFacilities).catch((error) => toast(error instanceof Error ? error.message : 'Không kiểm tra được trạng thái thiết lập.', 'error')); }, []);
  if (!facilities) return <LoadingSkeleton lines={8} />;
  if (facilities.length) return <ManagementDashboardPage />;
  const steps = [
    { icon: Building2, title: 'Tạo cơ sở đầu tiên', text: 'Khai báo tên, địa chỉ và hotline để khách hàng nhận diện địa điểm.' },
    { icon: MapPin, title: 'Thêm sân và môn thể thao', text: 'Thiết lập từng sân, sức chứa, giá cơ bản và tiện ích.' },
    { icon: ClipboardList, title: 'Thiết lập lịch và chính sách', text: 'Mở khung giờ, cấu hình tiền cọc và quy trình vận hành.' },
    { icon: CheckCircle2, title: 'Kiểm tra rồi bắt đầu nhận booking', text: 'Xem lại trang công khai trước khi đưa cơ sở vào hoạt động.' },
  ];
  return <><PageHeader title="Chào mừng đối tác mới" description="Hồ sơ của bạn đã được duyệt. Hoàn thành các bước sau để bắt đầu vận hành trên SportHub AI." /><section className="overflow-hidden rounded-card border border-brand-200 bg-white"><div className="bg-gradient-to-r from-brand-700 to-emerald-500 p-6 text-white"><Sparkles size={28} /><h2 className="mt-3 text-2xl font-black">Thiết lập cơ sở đầu tiên</h2><p className="mt-1 text-sm text-white/85">Dữ liệu bạn tạo sẽ thuộc đúng tài khoản OWNER hiện tại.</p></div><ol className="grid gap-4 p-6 md:grid-cols-2">{steps.map(({ icon: Icon, title, text }, index) => <li key={title} className="flex gap-4 rounded-xl bg-slate-50 p-4"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand-100 font-bold text-brand-700">{index + 1}</span><div><h3 className="flex items-center gap-2 font-bold"><Icon size={17} />{title}</h3><p className="mt-1 text-sm text-slate-600">{text}</p></div></li>)}</ol><div className="border-t p-6"><Link to="/management/venues"><Button size="lg">Tạo cơ sở đầu tiên</Button></Link></div></section></>;
}
