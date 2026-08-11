from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.user import User
from ...repositories.dashboard_repository import DashboardRepository
from ...schemas.dashboard import (
    BookingReport, DashboardSummary, FieldPerformanceReport,
    RevenueAnalyticsReport, RevenueReport, TimeSlotPerformanceReport,
)
from ...services.dashboard_service import DashboardService
from ..dependencies import require_permission

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


def get_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(DashboardRepository(db))


@router.get('/summary', response_model=DashboardSummary)
def dashboard_summary(
    date_from: date | None = None, date_to: date | None = None,
    field_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_permission('reports.view')),
    service: DashboardService = Depends(get_service),
):
    return service.for_user(current_user).summary(date_from, date_to, field_id)


@router.get('/revenue', response_model=RevenueReport)
def dashboard_revenue(
    date_from: date | None = None, date_to: date | None = None,
    field_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_permission('reports.view')),
    service: DashboardService = Depends(get_service),
):
    return service.for_user(current_user).revenue(date_from, date_to, field_id)


@router.get('/revenue-analytics', response_model=RevenueAnalyticsReport)
def dashboard_revenue_analytics(
    date_from: date | None = None, date_to: date | None = None,
    field_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_permission('reports.view')),
    service: DashboardService = Depends(get_service),
):
    return service.for_user(current_user).revenue_analytics(date_from, date_to, field_id)


@router.get('/bookings', response_model=BookingReport)
def dashboard_bookings(
    date_from: date | None = None, date_to: date | None = None,
    field_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_permission('reports.view')),
    service: DashboardService = Depends(get_service),
):
    return service.for_user(current_user).bookings(date_from, date_to, field_id)


@router.get('/field-performance', response_model=FieldPerformanceReport)
def field_performance(
    date_from: date | None = None, date_to: date | None = None,
    field_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_permission('reports.view')),
    service: DashboardService = Depends(get_service),
):
    return service.for_user(current_user).field_performance(date_from, date_to, field_id)


@router.get('/time-slot-performance', response_model=TimeSlotPerformanceReport)
def time_slot_performance(
    date_from: date | None = None, date_to: date | None = None,
    field_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_permission('reports.view')),
    service: DashboardService = Depends(get_service),
):
    return service.for_user(current_user).time_slot_performance(date_from, date_to, field_id)
