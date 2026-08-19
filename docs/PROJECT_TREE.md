# Cây thư mục SportHub AI

> Cập nhật ngày 16/08/2026. Cây chỉ liệt kê cấu trúc nghiệp vụ chính; bỏ qua `.venv`, `node_modules`, `dist`, cache, file runtime và model binary.

```text
SportHub AI/
├── README.md
├── docs/
│   ├── Chucnang.md
│   ├── FUNCTIONAL_HIERARCHY.md
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── PROJECT_TREE.md
│   ├── DEMO_SCRIPT.md
│   └── các báo cáo/bàn giao lịch sử
├── Backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── routes/
│   │   │       ├── auth.py, admin.py
│   │   │       ├── facilities.py, fields.py, time_slots.py
│   │   │       ├── bookings.py, products.py, payments.py
│   │   │       ├── notifications.py, operations.py
│   │   │       └── dashboard.py, ai.py
│   │   ├── models/
│   │   │   ├── user.py, facility.py, field.py, time_slot.py
│   │   │   ├── product.py, payment.py, invoice.py
│   │   │   └── notification.py và model nghiệp vụ liên quan
│   │   ├── schemas/
│   │   │   ├── facility.py, booking.py, product.py
│   │   │   ├── payment.py, notification.py
│   │   │   └── user.py, dashboard.py, ai.py
│   │   ├── services/
│   │   │   ├── booking_service.py, availability_service.py
│   │   │   ├── product_service.py, inventory_service.py
│   │   │   ├── payment_service.py, refund_service.py
│   │   │   ├── facility_file_service.py, notification_service.py
│   │   │   └── analytics/AI/domain services
│   │   ├── repositories/
│   │   │   └── booking, payment, dashboard, AI, time-slot repositories
│   │   ├── database/
│   │   │   ├── base.py, session.py, migrations.py
│   │   │   └── demo_seed.py
│   │   ├── core/
│   │   │   └── config, security và permission helpers
│   │   └── ai/
│   │       └── intent/inference/training/evaluation/saved_models
│   ├── tests/
│   │   ├── test_facility_approval.py, test_partner_application.py
│   │   ├── test_bookings.py, test_multi_slot_booking.py
│   │   ├── test_facility_products.py, test_demo_seed.py
│   │   ├── test_notifications.py, test_owner_isolation.py
│   │   └── test AI/payment/maintenance/analytics liên quan
│   ├── migrations/
│   ├── database/datasets/
│   ├── requirements.txt
│   └── .env.example
└── Frontend/
    ├── src/
    │   ├── main.tsx
    │   ├── routes/AppRouter.tsx
    │   ├── contexts/AuthContext.tsx
    │   ├── layouts/
    │   ├── components/
    │   │   ├── common/                 # Design system
    │   │   ├── layout/                 # Header, sidebar, navigation
    │   │   ├── booking/, payments/, venue/
    │   │   ├── notifications/
    │   │   └── management/FieldServicesModal.tsx
    │   ├── pages/
    │   │   ├── BookingPage.tsx và CUSTOMER pages
    │   │   ├── ManagementBookingsPage.tsx
    │   │   ├── ManagementVenuesPage.tsx
    │   │   ├── ManagementProductsPage.tsx
    │   │   ├── LiveManagementDataPages.tsx
    │   │   ├── SystemAdminFacilityApplicationsPage.tsx
    │   │   ├── NotificationsPage.tsx
    │   │   └── AI/analytics/payment pages
    │   ├── services/
    │   │   ├── apiClient.ts, customerApi.ts
    │   │   ├── productService.ts, notificationService.ts
    │   │   └── AI/venue/review services
    │   ├── types/
    │   ├── utils/
    │   └── assets/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig*.json
    └── .env.example
```

## Ánh xạ module quan trọng

| Module | Backend | Frontend |
|---|---|---|
| Hồ sơ/xét duyệt cơ sở | `facilities.py`, `facility.py`, `facility_file_service.py` | `ManagementVenuesPage.tsx`, `SystemAdminFacilityApplicationsPage.tsx` |
| Booking nhiều slot | `bookings.py`, `booking_service.py`, `BookingSlot` | `BookingPage.tsx`, trang chi tiết CUSTOMER/OWNER |
| Dịch vụ/tồn kho | `products.py`, `product_service.py`, `inventory_service.py`, `product.py` | `ManagementProductsPage.tsx`, `FieldServicesModal.tsx`, `productService.ts` |
| Payment/invoice | `payments.py`, `payment_service.py`, `invoice.py` | trang payment, receipt và booking detail |
| Notification | `notifications.py`, `notification_service.py`, `notification.py` | `NotificationBell.tsx`, `NotificationsPage.tsx` |
| AI/analytics | `ai/`, AI/analytics services và repositories | `AIAssistantPage.tsx`, management AI/revenue pages |
