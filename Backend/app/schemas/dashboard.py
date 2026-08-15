from datetime import date, datetime

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    date_from: date
    date_to: date
    total_fields: int
    active_fields: int
    total_bookings: int
    pending_bookings: int
    confirmed_bookings: int
    paid_revenue: float


class RevenuePoint(BaseModel):
    period: str
    revenue: float


class RevenueReport(BaseModel):
    granularity: str
    total: float
    items: list[RevenuePoint]


class BookingPoint(BaseModel):
    period: str
    total: int
    pending: int
    confirmed: int
    completed: int
    cancelled: int
    rejected: int


class BookingReport(BaseModel):
    granularity: str
    total: int
    items: list[BookingPoint]


class FieldPerformanceItem(BaseModel):
    field_id: int
    field_name: str
    sport_type: str
    status: str
    booking_count: int
    confirmed_count: int
    completed_count: int
    paid_revenue: float
    utilization_rate: float


class FieldPerformanceReport(BaseModel):
    items: list[FieldPerformanceItem]


class TimeSlotPerformanceItem(BaseModel):
    time_slot_id: int
    time_slot_name: str
    field_id: int
    field_name: str
    start_time: str
    end_time: str
    booking_count: int
    confirmed_count: int
    completed_count: int
    paid_revenue: float


class TimeSlotPerformanceReport(BaseModel):
    items: list[TimeSlotPerformanceItem]


class RevenueAnalyticsSummary(BaseModel):
    date_from: date
    date_to: date
    booking_value: float
    collected_amount: float
    deposit_amount: float
    held_deposit_amount: float
    outstanding_amount: float
    completed_revenue: float
    refunded_amount: float
    net_revenue: float
    court_revenue: float
    service_revenue: float
    total_revenue: float
    completed_bookings: int
    cancelled_bookings: int
    previous_net_revenue: float
    change_percent: float | None
    today_revenue: float
    week_revenue: float
    month_revenue: float


class RevenueBreakdownItem(BaseModel):
    key: str
    label: str
    booking_count: int
    collected_amount: float
    refunded_amount: float
    net_revenue: float


class RevenueTransactionItem(BaseModel):
    booking_id: int
    booking_code: str
    customer_name: str
    facility_name: str
    field_name: str
    sport_type: str
    booking_date: date
    court_amount: float
    service_amount: float
    total_amount: float
    collected_amount: float
    refunded_amount: float
    net_revenue: float
    outstanding_amount: float
    status: str
    last_paid_at: datetime | None


class ProductUsageItem(BaseModel):
    product_id: int
    name: str
    product_type: str
    quantity: int
    booking_count: int
    revenue: float


class RevenueAnalyticsReport(BaseModel):
    summary: RevenueAnalyticsSummary
    granularity: str
    trend: list[RevenueBreakdownItem]
    by_facility: list[RevenueBreakdownItem]
    by_field: list[RevenueBreakdownItem]
    by_sport: list[RevenueBreakdownItem]
    by_time_slot: list[RevenueBreakdownItem]
    popular_products: list[ProductUsageItem]
    transactions: list[RevenueTransactionItem]
