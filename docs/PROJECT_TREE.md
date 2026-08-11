# Cây thư mục SportHub AI

Cây dưới đây loại bỏ `.venv`, `node_modules`, `dist`, `__pycache__` và database runtime.

```text
SportHub AI/
├── README.md
├── .gitignore
├── docs/
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── DEMO_SCRIPT.md
│   ├── PROJECT_TREE.md
│   └── REPORT_GUIDE.md
├── Backend/
│   ├── .env.example
│   ├── README.md
│   ├── requirements.txt
│   ├── migrations/README.md
│   ├── database/datasets/
│   │   ├── booking_demand.csv
│   │   └── README.md
│   ├── app/
│   │   ├── main.py
│   │   ├── ai/
│   │   │   ├── README.md
│   │   │   ├── datasets/loader.py
│   │   │   ├── preprocessing/{feature_engineering.py,pipeline.py}
│   │   │   ├── training/{generate_dataset.py,train_model.py}
│   │   │   ├── evaluation/{metrics.py,evaluate_model.py}
│   │   │   ├── inference/{model_loader.py,prediction_service.py}
│   │   │   └── saved_models/{demand_pipeline.joblib,metrics.json,model_comparison.csv}
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── routes/{ai.py,auth.py,bookings.py,dashboard.py,fields.py,payments.py,time_slots.py}
│   │   ├── core/{config.py,permissions.py,security.py}
│   │   ├── database/{base.py,migrations.py,seed.py,session.py}
│   │   ├── models/{field.py,payment.py,time_slot.py,user.py}
│   │   ├── repositories/{ai_repository.py,booking_repository.py,dashboard_repository.py,field_repository.py,payment_repository.py,time_slot_repository.py}
│   │   ├── schemas/{ai.py,booking.py,dashboard.py,field.py,payment.py,time_slot.py,user.py}
│   │   └── services/{booking_service.py,dashboard_service.py,field_service.py,payment_service.py,time_slot_service.py}
│   └── tests/
│       ├── test_ai.py
│       ├── test_auth_and_permissions.py
│       ├── test_bookings.py
│       ├── test_dashboard.py
│       ├── test_fields.py
│       ├── test_payments.py
│       └── test_time_slots.py
└── Frontend/
    ├── .env.example
    ├── README.md
    ├── index.html
    ├── package.json
    ├── package-lock.json
    ├── public/favicon.svg
    └── src/
        ├── main.jsx
        ├── style.css
        ├── types.jsx
        ├── components/layout/AppLayout.jsx
        ├── config/permissions.jsx
        ├── context/AuthContext.jsx
        ├── pages/{AuthPages.jsx,ProfilePage.jsx,SimplePages.jsx}
        ├── routes/{guards.jsx,router.jsx}
        ├── services/
        │   ├── api/{aiApi.jsx,authApi.jsx,bookingApi.jsx,client.jsx,dashboardApi.jsx,fieldApi.jsx,paymentApi.jsx,timeSlotApi.jsx}
        │   └── storage/{bookingDraftStorage.jsx,tokenStorage.jsx}
        ├── utils/html.jsx
        └── features/
            ├── ai/
            │   ├── ai.css
            │   ├── pages/AIInsightsPage.jsx
            │   └── components/{DemandOverviewChart.jsx,DemandPredictionForm.jsx,DemandResult.jsx,ModelMetricsPanel.jsx,RecommendationList.jsx}
            ├── auth/
            │   ├── auth.css
            │   └── components/{AuthShell.jsx,PasswordField.jsx}
            ├── bookings/
            │   ├── pages/{AdminBookingListPage.jsx,BookingConfirmPage.jsx,BookingDetailPage.jsx,BookingReschedulePage.jsx,BookingSearchPage.jsx,MyBookingsPage.jsx}
            │   └── components/{AvailabilityCard.jsx,BookingActionModal.jsx,BookingDatePicker.jsx,BookingFilters.jsx,BookingStatusBadge.jsx,BookingSummary.jsx,BookingTable.jsx}
            ├── dashboard/
            │   ├── dashboard.css
            │   ├── pages/DashboardPage.jsx
            │   └── components/{BookingChart.jsx,DashboardFilters.jsx,DashboardSummary.jsx,FieldPerformanceTable.jsx,RevenueChart.jsx,TimeSlotPerformanceTable.jsx}
            ├── fields/
            │   ├── pages/{AdminFieldListPage.jsx,CustomerFieldListPage.jsx,FieldDetailPage.jsx,FieldFormPage.jsx}
            │   ├── components/{DeleteFieldModal.jsx,FieldCard.jsx,FieldFilters.jsx,FieldForm.jsx,FieldManagementSummary.jsx,FieldStatusBadge.jsx,FieldTable.jsx}
            │   └── utils.jsx
            ├── payments/
            │   ├── payments.css
            │   ├── pages/{AdminPaymentListPage.jsx,MyPaymentsPage.jsx,PaymentPage.jsx}
            │   └── components/{PaymentConfirmModal.jsx,PaymentFilters.jsx,PaymentForm.jsx,PaymentStatusBadge.jsx,PaymentSummaryCard.jsx,PaymentTable.jsx}
            └── timeSlots/
                ├── pages/{AdminTimeSlotListPage.jsx,TimeSlotFormPage.jsx}
                ├── components/{DeleteTimeSlotModal.jsx,TimeSlotFieldFilter.jsx,TimeSlotForm.jsx,TimeSlotStatusBadge.jsx,TimeSlotTable.jsx}
                └── utils.jsx
```
