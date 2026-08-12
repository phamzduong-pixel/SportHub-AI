from datetime import date, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.field import BookingStatus
from ...models.user import User
from ...repositories.booking_repository import BookingRepository
from ...schemas.booking import (
    AvailabilityField, BookingActionNote, BookingCancellationQuote, BookingCancellationRequest,
    BookingCreate, BookingInvoiceResponse, BookingListResponse, BookingQuote,
    BookingRescheduleQuote, BookingRescheduleRequest, BookingResponse, BookingUpdate,
)
from ...services.booking_service import BookingService
from ..dependencies import get_current_user, require_owner

router = APIRouter(tags=['bookings'])

def get_service(db: Session = Depends(get_db)) -> BookingService:
    return BookingService(BookingRepository(db))

@router.get('/availability', response_model=list[AvailabilityField])
def availability(
    booking_date: date = Query(alias='date'),
    field_id: int | None = Query(default=None, gt=0),
    search: str | None = Query(default=None, max_length=120),
    sport_type: str | None = Query(default=None, max_length=80),
    location: str | None = Query(default=None, max_length=120),
    start_time: time | None = Query(default=None),
    max_price: float | None = Query(default=None, ge=0, le=1_000_000_000),
    sort_by: str = Query(default='relevance', pattern='^(relevance|price|rating)$'),
    service: BookingService = Depends(get_service),
):
    return service.availability(booking_date=booking_date, field_id=field_id, search=search, sport_type=sport_type, location=location, start_time=start_time, max_price=max_price, sort_by=sort_by)

@router.post('/bookings', response_model=BookingResponse, status_code=201)
def create_booking(
    payload: BookingCreate,
    current_user: User = Depends(get_current_user),
    service: BookingService = Depends(get_service),
):
    return service.create(payload, current_user)

@router.get('/bookings/quote', response_model=BookingQuote)
def booking_quote(
    field_id: int = Query(gt=0), time_slot_id: int = Query(gt=0),
    booking_date: date = Query(alias='date'), service: BookingService = Depends(get_service),
):
    return service.quote(field_id=field_id, time_slot_id=time_slot_id, booking_date=booking_date)

@router.get('/bookings/my', response_model=BookingListResponse)
def my_bookings(
    booking_date: date | None = Query(default=None, alias='date'),
    field_id: int | None = Query(default=None, gt=0),
    status: BookingStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: BookingService = Depends(get_service),
):
    items, total = service.list_my(
        current_user, booking_date=booking_date, field_id=field_id,
        status=status.value if status else None, search=None, page=page, page_size=page_size,
    )
    return BookingListResponse.from_result(items, total, page, page_size)

@router.get('/bookings', response_model=BookingListResponse)
def list_bookings(
    booking_date: date | None = Query(default=None, alias='date'),
    field_id: int | None = Query(default=None, gt=0),
    status: BookingStatus | None = None,
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_owner),
    service: BookingService = Depends(get_service),
):
    items, total = service.list_manage(
        current_user,
        booking_date=booking_date, field_id=field_id,
        status=status.value if status else None, search=search, page=page, page_size=page_size,
    )
    return BookingListResponse.from_result(items, total, page, page_size)

@router.get('/bookings/{booking_id}', response_model=BookingResponse)
def get_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    service: BookingService = Depends(get_service),
):
    return service.get_for_user(booking_id, current_user)

@router.put('/bookings/{booking_id}', response_model=BookingResponse)
def update_booking(
    booking_id: int,
    payload: BookingUpdate,
    current_user: User = Depends(require_owner),
    service: BookingService = Depends(get_service),
):
    return service.update(booking_id, payload, current_user)

@router.patch('/bookings/{booking_id}/confirm', response_model=BookingResponse)
def confirm_booking(
    booking_id: int,
    payload: BookingActionNote = BookingActionNote(),
    current_user: User = Depends(require_owner),
    service: BookingService = Depends(get_service),
):
    return service.confirm(booking_id, payload.note, current_user)

@router.patch('/bookings/{booking_id}/reject', response_model=BookingResponse)
def reject_booking(
    booking_id: int,
    payload: BookingActionNote = BookingActionNote(),
    current_user: User = Depends(require_owner),
    service: BookingService = Depends(get_service),
):
    return service.reject(booking_id, payload.note, current_user)

@router.patch('/bookings/{booking_id}/cancel', response_model=BookingResponse)
def cancel_booking(
    booking_id: int,
    payload: BookingCancellationRequest = BookingCancellationRequest(),
    current_user: User = Depends(get_current_user),
    service: BookingService = Depends(get_service),
):
    return service.cancel(booking_id, current_user, payload.reason or payload.note)

@router.get('/bookings/{booking_id}/cancellation-quote', response_model=BookingCancellationQuote)
def cancellation_quote(
    booking_id: int, current_user: User = Depends(get_current_user),
    service: BookingService = Depends(get_service),
):
    return service.cancellation_quote(booking_id, current_user)

@router.post('/bookings/{booking_id}/reschedule/quote', response_model=BookingRescheduleQuote)
def reschedule_quote(
    booking_id: int, payload: BookingRescheduleRequest,
    current_user: User = Depends(get_current_user), service: BookingService = Depends(get_service),
):
    quote, _ = service.reschedule_quote(booking_id, payload, current_user)
    return quote

@router.patch('/bookings/{booking_id}/reschedule', response_model=BookingResponse)
def reschedule_booking(
    booking_id: int, payload: BookingRescheduleRequest,
    current_user: User = Depends(get_current_user), service: BookingService = Depends(get_service),
):
    return service.reschedule(booking_id, payload, current_user)

@router.patch('/bookings/{booking_id}/start', response_model=BookingResponse)
def start_booking(
    booking_id: int, payload: BookingActionNote = BookingActionNote(),
    current_user: User = Depends(require_owner),
    service: BookingService = Depends(get_service),
):
    return service.start(booking_id, payload.note, current_user)

@router.patch('/bookings/{booking_id}/no-show', response_model=BookingResponse)
def mark_no_show(
    booking_id: int, payload: BookingActionNote = BookingActionNote(),
    current_user: User = Depends(require_owner),
    service: BookingService = Depends(get_service),
):
    return service.no_show(booking_id, payload.note, current_user)

@router.get('/bookings/{booking_id}/invoice', response_model=BookingInvoiceResponse)
def booking_invoice(
    booking_id: int, current_user: User = Depends(get_current_user),
    service: BookingService = Depends(get_service),
):
    return service.invoice_for_user(booking_id, current_user)

@router.patch('/bookings/{booking_id}/complete', response_model=BookingResponse)
def complete_booking(
    booking_id: int,
    payload: BookingActionNote = BookingActionNote(),
    current_user: User = Depends(require_owner),
    service: BookingService = Depends(get_service),
):
    return service.complete(booking_id, payload.note, current_user)
