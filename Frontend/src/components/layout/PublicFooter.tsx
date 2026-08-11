import { Facebook, Instagram, Mail, MapPin, Phone } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Logo } from './Logo';

const groups = [
  { title: 'Khám phá', links: ['Tìm sân', 'Môn thể thao', 'Ưu đãi', 'Trợ lý AI'] },
  { title: 'Hỗ trợ', links: ['Trung tâm trợ giúp', 'Hướng dẫn đặt sân', 'Chính sách hủy', 'Liên hệ'] },
  { title: 'Đối tác', links: ['Đăng ký chủ sân', 'Giải pháp quản lý', 'Bảng giá', 'Điều khoản'] },
];

export function PublicFooter() {
  return <footer className="site-footer w-full overflow-hidden border-t site-footer-border">
    <div className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-8 px-4 py-10 sm:px-6 sm:py-12 md:grid-cols-2 md:gap-10 lg:grid-cols-[1.4fr_repeat(3,1fr)] lg:py-14">
      <div className="min-w-0">
        <div className="inline-flex max-w-full rounded-lg bg-white px-2 py-1 shadow-sm"><Logo /></div>
        <p className="mt-4 max-w-sm text-sm leading-6 text-emerald-50/80">Nền tảng giúp người chơi tìm sân nhanh hơn và hỗ trợ chủ sân vận hành hiệu quả bằng dữ liệu.</p>
        <div className="mt-5 space-y-2 text-sm text-emerald-50/90">
          <p className="flex min-w-0 items-start gap-2"><MapPin size={16} className="mt-0.5 shrink-0 text-emerald-200" /><span>TP. Hồ Chí Minh, Việt Nam</span></p>
          <a href="tel:19006868" className="flex w-fit items-center gap-2 transition hover:text-white"><Phone size={16} className="shrink-0 text-emerald-200" />1900 6868</a>
          <a href="mailto:hello@sporthub.ai" className="flex min-w-0 items-center gap-2 transition hover:text-white"><Mail size={16} className="shrink-0 text-emerald-200" /><span className="break-all">hello@sporthub.ai</span></a>
        </div>
      </div>
      {groups.map((group) => <div key={group.title} className="min-w-0 border-t pt-6 site-footer-border md:border-0 md:pt-0"><h3 className="font-bold text-white">{group.title}</h3><ul className="mt-3 space-y-2.5 text-sm text-emerald-50/75 sm:mt-4 sm:space-y-3">{group.links.map((item) => <li key={item}><a href="#" className="inline-block py-0.5 transition hover:text-white">{item}</a></li>)}</ul></div>)}
    </div>
    <div className="site-footer-bottom border-t site-footer-border">
      <div className="mx-auto flex w-full max-w-7xl min-w-0 flex-col gap-3 px-4 py-5 text-xs text-emerald-50/65 sm:px-6 md:flex-row md:items-center md:justify-between">
        <p className="leading-5">© 2026 SportHub AI. Bảo lưu mọi quyền.</p>
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2"><Link className="transition hover:text-white" to="/">Quyền riêng tư</Link><Link className="transition hover:text-white" to="/">Điều khoản</Link><Facebook size={16} className="shrink-0" /><Instagram size={16} className="shrink-0" /></div>
      </div>
    </div>
  </footer>;
}
