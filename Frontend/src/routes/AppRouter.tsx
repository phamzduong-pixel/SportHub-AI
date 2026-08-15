import { lazy, Suspense, type ReactNode } from "react";
import {
  createBrowserRouter,
  Navigate,
  RouterProvider,
  useParams,
} from "react-router-dom";
import { LoadingSkeleton } from "@/components/common";
import { CustomerLayout } from "@/layouts/CustomerLayout";
import { ManagementLayout } from "@/layouts/ManagementLayout";
import { PublicLayout } from "@/layouts/PublicLayout";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import {
  AuthGuard,
  OwnerVerificationGuard,
  RoleGuard,
} from "@/components/auth/Guards";

const HomePage = lazy(() =>
  import("@/pages/HomePage").then((m) => ({ default: m.HomePage })),
);
const VenuesPage = lazy(() =>
  import("@/pages/VenuesPage").then((m) => ({ default: m.VenuesPage })),
);
const VenueDetailPage = lazy(() =>
  import("@/pages/VenueDetailPage").then((m) => ({
    default: m.VenueDetailPage,
  })),
);
const BookingPage = lazy(() =>
  import("@/pages/BookingPage").then((m) => ({ default: m.BookingPage })),
);
const BookingSuccessPage = lazy(() =>
  import("@/pages/DepositSuccessPage").then((m) => ({
    default: m.DepositSuccessPage,
  })),
);
const BankDepositPaymentPage = lazy(() =>
  import("@/pages/BankDepositPaymentPage").then((m) => ({
    default: m.BankDepositPaymentPage,
  })),
);
const CustomerDashboardPage = lazy(() =>
  import("@/pages/CustomerDashboardPage").then((m) => ({
    default: m.CustomerDashboardPage,
  })),
);
const CustomerBookingsPage = lazy(() =>
  import("@/pages/CustomerPages").then((m) => ({
    default: m.CustomerBookingsPage,
  })),
);
const BookingDetailPage = lazy(() =>
  import("@/pages/CustomerBookingDetailPage").then((m) => ({
    default: m.CustomerBookingDetailPage,
  })),
);
const CustomerFavoritesPage = lazy(() =>
  import("@/pages/CustomerPages").then((m) => ({
    default: m.CustomerFavoritesPage,
  })),
);
const CustomerTransactionsPage = lazy(() =>
  import("@/pages/CustomerPages").then((m) => ({
    default: m.CustomerTransactionsPage,
  })),
);
const CustomerProfilePage = lazy(() =>
  import("@/pages/CustomerProfilePage").then((m) => ({
    default: m.CustomerProfilePage,
  })),
);
const CustomerSettingsPage = lazy(() =>
  import("@/pages/CustomerPages").then((m) => ({
    default: m.CustomerSettingsPage,
  })),
);
const NotificationsPage = lazy(() =>
  import("@/pages/NotificationsPage").then((m) => ({
    default: m.NotificationsPage,
  })),
);
const CustomerReviewsPage = lazy(() =>
  import("@/pages/CustomerReviewsPage").then((m) => ({
    default: m.CustomerReviewsPage,
  })),
);
const ManagementDashboardPage = lazy(() =>
  import("@/pages/ManagementDashboardWithOnboardingPage").then((m) => ({
    default: m.ManagementDashboardWithOnboardingPage,
  })),
);
const ManagementCalendarPage = lazy(() =>
  import("@/pages/ManagementCalendarWithMaintenancePage").then((m) => ({
    default: m.ManagementCalendarWithMaintenancePage,
  })),
);
const ManagementBookingsPage = lazy(() =>
  import("@/pages/ManagementBookingsPage").then((m) => ({
    default: m.ManagementBookingsPage,
  })),
);
const ManagementBookingDetailPage = lazy(() =>
  import("@/pages/ManagementBookingsPage").then((m) => ({
    default: m.ManagementBookingDetailPage,
  })),
);
const ManagementComplaintsPage = lazy(() =>
  import("@/pages/ManagementComplaintsPage").then((m) => ({
    default: m.ManagementComplaintsPage,
  })),
);
const ManagementMaintenancePage = lazy(() =>
  import("@/pages/ManagementMaintenancePage").then((m) => ({
    default: m.ManagementMaintenancePage,
  })),
);
const ManagementVenuesPage = lazy(() =>
  import("@/pages/ManagementVenuesPage").then((m) => ({
    default: m.ManagementVenuesPage,
  })),
);
const ManagementCourtsPage = lazy(() =>
  import("@/pages/LiveManagementDataPages").then((m) => ({
    default: m.ManagementCourtsPage,
  })),
);
const ManagementSchedulesPage = lazy(() =>
  import("@/pages/ManagementSchedulesPage").then((m) => ({
    default: m.ManagementSchedulesPage,
  })),
);
const ManagementPricingPage = lazy(() =>
  import("@/pages/ManagementDepositSettingsPage").then((m) => ({
    default: m.ManagementDepositSettingsPage,
  })),
);
const ManagementProductsPage = lazy(() =>
  import("@/pages/ManagementProductsPage").then((m) => ({
    default: m.ManagementProductsPage,
  })),
);
const ManagementCustomersPage = lazy(() =>
  import("@/pages/ManagementCustomersPage").then((m) => ({
    default: m.ManagementCustomersPage,
  })),
);
const ManagementPaymentsPage = lazy(() =>
  import("@/pages/ManagementPaymentsPage").then((m) => ({
    default: m.ManagementPaymentsPage,
  })),
);
const ManagementSettingsPage = lazy(() =>
  import("@/pages/ManagementSettingsPage").then((m) => ({
    default: m.ManagementSettingsPage,
  })),
);
const LoginPage = lazy(() =>
  import("@/pages/RegistrationPages").then((m) => ({ default: m.LoginPage })),
);
const RegisterPage = lazy(() =>
  import("@/pages/RegistrationPages").then((m) => ({
    default: m.RegisterPage,
  })),
);
const ForgotPasswordPage = lazy(() =>
  import("@/pages/ForgotPasswordPage").then((m) => ({
    default: m.ForgotPasswordPage,
  })),
);
const OwnerApplicationPage = lazy(() =>
  import("@/pages/PartnerApplicationPage").then((m) => ({
    default: m.PartnerApplicationPage,
  })),
);
const OwnerApplicationStatusPage = OwnerApplicationPage;
const AIAssistantPage = lazy(() =>
  import("@/pages/AIAssistantPage").then((m) => ({
    default: m.AIAssistantPage,
  })),
);
const ManagementAIInsightsPage = lazy(() =>
  import("@/pages/LiveManagementDataPages").then((m) => ({
    default: m.ManagementAIInsightsPage,
  })),
);
const ManagementReportsPage = lazy(() =>
  import("@/pages/ManagementRevenuePage").then((m) => ({
    default: m.ManagementRevenuePage,
  })),
);
const ManagementReviewsPage = lazy(() =>
  import("@/pages/ManagementReviewsPage").then((m) => ({
    default: m.ManagementReviewsPage,
  })),
);
const SystemAdminPage = lazy(() =>
  import("@/pages/SystemAdminPage").then((m) => ({
    default: m.SystemAdminPage,
  })),
);
const SystemAdminPartnerApplicationsPage = lazy(() =>
  import("@/pages/SystemAdminPartnerApplicationsPage").then((m) => ({
    default: m.SystemAdminPartnerApplicationsPage,
  })),
);
const SystemAdminFacilityApplicationsPage = lazy(() =>
  import("@/pages/SystemAdminFacilityApplicationsPage").then((m) => ({
    default: m.SystemAdminFacilityApplicationsPage,
  })),
);
const pending = (
  <div className="mx-auto max-w-7xl p-8">
    <LoadingSkeleton lines={5} />
  </div>
);
const load = (page: ReactNode) => (
  <Suspense fallback={pending}>{page}</Suspense>
);
const placeholder = (title: string) => (
  <div className="mx-auto max-w-7xl px-4 py-10">
    <PlaceholderPage title={title} />
  </div>
);
function LegacyVenueDetailRedirect() {
  const { venueId } = useParams();
  return <Navigate to={venueId ? `/courts/${venueId}` : "/venues"} replace />;
}

const router = createBrowserRouter([
  { path: "/login", element: load(<LoginPage />) },
  { path: "/register", element: load(<RegisterPage />) },
  { path: "/forgot-password", element: load(<ForgotPasswordPage />) },
  {
    path: "/owner-application",
    element: <AuthGuard>{load(<OwnerApplicationPage />)}</AuthGuard>,
  },
  {
    path: "/owner-application/status",
    element: <AuthGuard>{load(<OwnerApplicationStatusPage />)}</AuthGuard>,
  },
  {
    path: "/notifications",
    element: <AuthGuard>{load(<NotificationsPage />)}</AuthGuard>,
  },
  {
    element: <PublicLayout />,
    children: [
      { path: "/", element: load(<HomePage />) },
      { path: "/venues", element: load(<VenuesPage />) },
      { path: "/courts/:courtId", element: load(<VenueDetailPage />) },
      { path: "/venues/:venueId", element: <LegacyVenueDetailRedirect /> },
      {
        path: "/booking/:venueId",
        element: (
          <AuthGuard>
            <RoleGuard roles={["CUSTOMER"]}>{load(<BookingPage />)}</RoleGuard>
          </AuthGuard>
        ),
      },
      {
        path: "/booking/success",
        element: (
          <AuthGuard>
            <RoleGuard roles={["CUSTOMER"]}>
              {load(<BookingSuccessPage />)}
            </RoleGuard>
          </AuthGuard>
        ),
      },
      {
        path: "/booking/payment/:paymentId",
        element: (
          <AuthGuard>
            <RoleGuard roles={["CUSTOMER"]}>
              {load(<BankDepositPaymentPage />)}
            </RoleGuard>
          </AuthGuard>
        ),
      },
      { path: "/ai-assistant", element: load(<AIAssistantPage />) },
      { path: "/san-the-thao", element: <Navigate to="/venues" replace /> },
      {
        path: "/san-the-thao/:venueId",
        element: <LegacyVenueDetailRedirect />,
      },
      { path: "/dang-nhap", element: <Navigate to="/login" replace /> },
      { path: "/dang-ky", element: <Navigate to="/register" replace /> },
      { path: "/bang-gia", element: placeholder("Bảng giá") },
      { path: "/ve-chung-toi", element: placeholder("Về SportHub AI") },
    ],
  },
  {
    path: "/customer",
    element: (
      <AuthGuard>
        <RoleGuard roles={["CUSTOMER"]}>
          <CustomerLayout />
        </RoleGuard>
      </AuthGuard>
    ),
    children: [
      { index: true, element: <Navigate to="dashboard" replace /> },
      { path: "dashboard", element: load(<CustomerDashboardPage />) },
      { path: "bookings", element: load(<CustomerBookingsPage />) },
      { path: "bookings/:bookingId", element: load(<BookingDetailPage />) },
      { path: "favorites", element: load(<CustomerFavoritesPage />) },
      { path: "transactions", element: load(<CustomerTransactionsPage />) },
      { path: "profile", element: load(<CustomerProfilePage />) },
      { path: "settings", element: load(<CustomerSettingsPage />) },
      {
        path: "notifications",
        element: <Navigate to="/notifications" replace />,
      },
      { path: "reviews", element: load(<CustomerReviewsPage />) },
    ],
  },
  {
    path: "/system-admin",
    element: (
      <AuthGuard>
        <RoleGuard roles={["SYSTEM_ADMIN"]}>
          {load(<SystemAdminPage />)}
        </RoleGuard>
      </AuthGuard>
    ),
  },
  {
    path: "/system-admin/partner-applications",
    element: (
      <AuthGuard>
        <RoleGuard roles={["SYSTEM_ADMIN"]}>
          {load(<SystemAdminPartnerApplicationsPage />)}
        </RoleGuard>
      </AuthGuard>
    ),
  },
  {
    path: "/system-admin/facility-applications",
    element: (
      <AuthGuard>
        <RoleGuard roles={["SYSTEM_ADMIN"]}>
          {load(<SystemAdminFacilityApplicationsPage />)}
        </RoleGuard>
      </AuthGuard>
    ),
  },
  {
    path: "/tai-khoan",
    element: <Navigate to="/customer/dashboard" replace />,
  },
  {
    path: "/tai-khoan/lich-dat",
    element: <Navigate to="/customer/bookings" replace />,
  },
  {
    path: "/tai-khoan/yeu-thich",
    element: <Navigate to="/customer/favorites" replace />,
  },
  {
    path: "/tai-khoan/ho-so",
    element: <Navigate to="/customer/profile" replace />,
  },
  {
    path: "/management",
    element: (
      <AuthGuard>
        <RoleGuard roles={["OWNER"]}>
          <OwnerVerificationGuard>
            <ManagementLayout />
          </OwnerVerificationGuard>
        </RoleGuard>
      </AuthGuard>
    ),
    children: [
      { index: true, element: <Navigate to="dashboard" replace /> },
      { path: "dashboard", element: load(<ManagementDashboardPage />) },
      { path: "calendar", element: load(<ManagementCalendarPage />) },
      { path: "bookings", element: load(<ManagementBookingsPage />) },
      {
        path: "bookings/:bookingId",
        element: load(<ManagementBookingDetailPage />),
      },
      { path: "complaints", element: load(<ManagementComplaintsPage />) },
      { path: "maintenance", element: load(<ManagementMaintenancePage />) },
      {
        path: "field-blocks",
        element: <Navigate to="/management/maintenance" replace />,
      },
      { path: "venues", element: load(<ManagementVenuesPage />) },
      { path: "courts", element: load(<ManagementCourtsPage />) },
      { path: "schedules", element: load(<ManagementSchedulesPage />) },
      { path: "pricing", element: load(<ManagementPricingPage />) },
      { path: "products", element: load(<ManagementProductsPage />) },
      { path: "customers", element: load(<ManagementCustomersPage />) },
      { path: "payments", element: load(<ManagementPaymentsPage />) },
      { path: "reports", element: load(<ManagementReportsPage />) },
      { path: "ai-insights", element: load(<ManagementAIInsightsPage />) },
      {
        path: "reviews",
        element: (
          <RoleGuard roles={["OWNER"]}>
            {load(<ManagementReviewsPage />)}
          </RoleGuard>
        ),
      },
      {
        path: "ai",
        element: <Navigate to="/management/ai-insights" replace />,
      },
      { path: "settings", element: load(<ManagementSettingsPage />) },
      {
        path: "facilities",
        element: <Navigate to="/management/venues" replace />,
      },
      {
        path: "time-slots",
        element: <Navigate to="/management/schedules" replace />,
      },
    ],
  },
  {
    path: "/quan-ly",
    element: <Navigate to="/management/dashboard" replace />,
  },
  {
    path: "/quan-ly/lich-dat",
    element: <Navigate to="/management/calendar" replace />,
  },
  {
    path: "/quan-ly/san",
    element: <Navigate to="/management/courts" replace />,
  },
  {
    path: "/quan-ly/khach-hang",
    element: <Navigate to="/management/customers" replace />,
  },
  {
    path: "/quan-ly/bao-cao",
    element: <Navigate to="/management/reports" replace />,
  },
  { path: "/quan-ly/ai", element: <Navigate to="/management/ai" replace /> },
  {
    path: "/quan-ly/cai-dat",
    element: <Navigate to="/management/settings" replace />,
  },
  { path: "*", element: <NotFoundPage /> },
]);
export function AppRouter() {
  return <RouterProvider router={router} />;
}
