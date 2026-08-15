import {
  BadgeDollarSign,
  Bot,
  Building2,
  CalendarClock,
  CalendarDays,
  ChartNoAxesCombined,
  ChevronLeft,
  CircleDollarSign,
  Clock3,
  LayoutDashboard,
  ListChecks,
  MessageSquareWarning,
  PackageOpen,
  Settings,
  Users,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { usePermission } from "@/contexts/PermissionContext";
import type { ManagementModule } from "@/types/permissions";
import { Logo } from "./Logo";

const nav: Array<{
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  module: ManagementModule;
  ai?: boolean;
}> = [
  {
    to: "/management/dashboard",
    label: "Tổng quan",
    icon: LayoutDashboard,
    module: "dashboard",
  },
  {
    to: "/management/calendar",
    label: "Lịch đặt sân",
    icon: CalendarDays,
    module: "calendar",
  },
  {
    to: "/management/bookings",
    label: "Danh sách booking",
    icon: ListChecks,
    module: "bookings",
  },
  {
    to: "/management/venues",
    label: "Cơ sở",
    icon: Building2,
    module: "venues",
  },
  {
    to: "/management/courts",
    label: "Sân",
    icon: CalendarClock,
    module: "courts",
  },
  {
    to: "/management/schedules",
    label: "Khung giờ",
    icon: Clock3,
    module: "schedules",
  },
  {
    to: "/management/maintenance",
    label: "Bảo trì sân",
    icon: CalendarClock,
    module: "maintenance",
  },
  {
    to: "/management/pricing",
    label: "Bảng giá",
    icon: BadgeDollarSign,
    module: "pricing",
  },
  {
    to: "/management/products",
    label: "Dịch vụ & sản phẩm",
    icon: PackageOpen,
    module: "products",
  },
  {
    to: "/management/customers",
    label: "Khách hàng",
    icon: Users,
    module: "customers",
  },
  {
    to: "/management/payments",
    label: "Thanh toán",
    icon: CircleDollarSign,
    module: "payments",
  },
  {
    to: "/management/complaints",
    label: "Khiếu nại",
    icon: MessageSquareWarning,
    module: "bookings",
  },
  {
    to: "/management/reports",
    label: "Báo cáo",
    icon: ChartNoAxesCombined,
    module: "reports",
  },
  {
    to: "/management/ai-insights",
    label: "Phân tích AI",
    icon: Bot,
    module: "ai",
    ai: true,
  },
  {
    to: "/management/settings",
    label: "Cài đặt",
    icon: Settings,
    module: "settings",
  },
];

interface Props {
  collapsed: boolean;
  mobileOpen: boolean;
  onToggle: () => void;
  onMobileClose: () => void;
}

export function ManagementSidebar({
  collapsed,
  mobileOpen,
  onToggle,
  onMobileClose,
}: Props) {
  const { can } = usePermission();
  const visible = nav.filter((item) => can(item.module));
  const content = (
    <>
      <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4 sm:px-5">
        <Logo compact={collapsed} />
        <button
          onClick={onMobileClose}
          className="grid h-10 w-10 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 lg:hidden"
          aria-label="Đóng menu"
        >
          <X size={20} />
        </button>
      </div>
      <nav className="management-scrollbar h-[calc(100dvh-7.5rem)] space-y-1 overflow-y-auto overflow-x-hidden p-3">
        {visible.map(({ to, label, icon: Icon, ai }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onMobileClose}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${isActive ? (ai ? "bg-ai-50 text-ai-600" : "bg-brand-50 text-brand-700") : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"} ${collapsed ? "justify-center" : ""}`
            }
          >
            <Icon size={19} className="shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>
      <button
        onClick={onToggle}
        className="absolute bottom-3 left-3 right-3 hidden h-9 items-center justify-center gap-2 rounded-lg border border-slate-200 text-xs font-semibold text-slate-500 hover:bg-slate-50 lg:flex"
      >
        <ChevronLeft size={17} className={collapsed ? "rotate-180" : ""} />
        {!collapsed && "Thu gọn sidebar"}
      </button>
    </>
  );

  return (
    <>
      {mobileOpen && (
        <button
          aria-label="Đóng menu"
          onClick={onMobileClose}
          className="fixed inset-0 z-40 bg-slate-950/45 lg:hidden"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 max-w-[calc(100vw-2rem)] overflow-x-hidden border-r border-slate-200 bg-white shadow-xl transition-all duration-200 lg:z-40 lg:block lg:max-w-none lg:shadow-none ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"} ${collapsed ? "lg:w-[76px]" : "lg:w-64"}`}
      >
        {content}
      </aside>
    </>
  );
}
