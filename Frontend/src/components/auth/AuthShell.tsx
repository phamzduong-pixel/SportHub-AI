import type { ReactNode } from 'react';
import { CalendarCheck2, ShieldCheck, Sparkles, Zap } from 'lucide-react';
import { Logo } from '@/components/layout/Logo';

interface AuthShellProps {
  title: string;
  description: string;
  children: ReactNode;
}

const benefits = [
  { icon: CalendarCheck2, label: 'Đặt sân nhanh chóng', detail: 'Lịch sân cập nhật theo thời gian thực' },
  { icon: ShieldCheck, label: 'Thanh toán an toàn', detail: 'Thông tin của bạn luôn được bảo mật' },
  { icon: Sparkles, label: 'Gợi ý thông minh', detail: 'Tìm sân phù hợp với nhu cầu của bạn' },
];

export function AuthShell({ title, description, children }: AuthShellProps) {
  return (
    <div className="relative grid h-dvh min-h-0 place-items-center overflow-hidden bg-slate-50 px-4 py-4 sm:px-6 sm:py-6">
      <div aria-hidden="true" className="absolute inset-0">
        <div className="absolute -left-36 -top-32 h-96 w-96 rounded-full bg-brand-100/70 blur-3xl" />
        <div className="absolute -bottom-40 -right-32 h-[28rem] w-[28rem] rounded-full bg-sportblue-50 blur-3xl" />
        <div className="absolute inset-0 opacity-[0.035] [background-image:linear-gradient(#0f172a_1px,transparent_1px),linear-gradient(90deg,#0f172a_1px,transparent_1px)] [background-size:32px_32px]" />
      </div>

      <div className="relative mx-auto grid h-full max-h-[680px] min-h-0 w-full max-w-[1080px] overflow-hidden rounded-[28px] border border-white/80 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.12)] lg:grid-cols-[1.02fr_.98fr]">
        <aside className="relative hidden overflow-hidden bg-brand-900 px-12 py-10 text-white lg:flex lg:flex-col">
          <div aria-hidden="true" className="absolute inset-0">
            <div className="absolute -right-28 -top-24 h-72 w-72 rounded-full border-[42px] border-white/[0.04]" />
            <div className="absolute -bottom-36 -left-20 h-96 w-96 rounded-full bg-brand-600/30 blur-2xl" />
            <svg className="absolute bottom-0 right-0 w-[72%] text-white/[0.045]" viewBox="0 0 420 300" fill="none">
              <path d="M20 300C20 174.1 122.1 72 248 72h172v228H20Z" stroke="currentColor" strokeWidth="2" />
              <circle cx="248" cy="186" r="72" stroke="currentColor" strokeWidth="2" />
              <path d="M248 72v228M20 186h400" stroke="currentColor" strokeWidth="2" />
            </svg>
          </div>

          <div className="relative"><Logo inverted /></div>

          <div className="relative my-auto py-14">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-xs font-semibold text-emerald-100 backdrop-blur">
              <Zap size={14} fill="currentColor" /> Nền tảng thể thao thông minh
            </span>
            <h2 className="mt-6 max-w-md text-[40px] font-extrabold leading-[1.16] tracking-[-0.035em]">
              Mọi trận đấu hay đều bắt đầu từ đây.
            </h2>
            <p className="mt-4 max-w-md text-[15px] leading-7 text-emerald-50/75">
              Tìm sân, đặt lịch và kết nối cộng đồng thể thao trong một trải nghiệm liền mạch.
            </p>

            <div className="mt-9 space-y-5">
              {benefits.map(({ icon: Icon, label, detail }) => (
                <div key={label} className="flex items-center gap-3.5">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/10 text-emerald-200">
                    <Icon size={19} />
                  </span>
                  <span>
                    <strong className="block text-sm font-semibold text-white">{label}</strong>
                    <span className="mt-0.5 block text-xs text-emerald-100/60">{detail}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>

          <p className="relative text-xs text-emerald-100/45">© 2026 SportHub AI · Thể thao theo cách thông minh hơn</p>
        </aside>

        <main className="auth-scrollbar flex min-h-0 flex-col overflow-y-auto px-6 py-7 sm:px-12 sm:py-10 lg:justify-center lg:px-16">
          <div className="mb-10 flex items-center justify-between lg:hidden">
            <Logo />
            <span className="rounded-full bg-brand-50 px-3 py-1 text-[11px] font-semibold text-brand-700">An toàn & bảo mật</span>
          </div>

          <div className="mx-auto w-full max-w-[390px]">
            <div className="mb-8">
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-brand-600">SportHub AI</p>
              <h1 className="text-[28px] font-extrabold tracking-[-0.025em] text-slate-950 sm:text-[32px]">{title}</h1>
              <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
            </div>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
