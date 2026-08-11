from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.config import settings
from ...database.session import get_db
from ...models.payment import PaymentMethod, PaymentStatus
from ...models.user import User
from ...repositories.payment_repository import PaymentRepository
from ...schemas.payment import BankPaymentIntentCreate, BankWebhookPayload, DepositReceiptResponse, PaymentActionNote, PaymentCreate, PaymentListResponse, PaymentResponse, PaymentSummary
from ...services.payment_service import PaymentService
from ..dependencies import get_current_user, require_permission

router = APIRouter(tags=['payments'])


def get_service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(PaymentRepository(db))


@router.post('/payments', response_model=PaymentResponse, status_code=201)
def create_payment(payload: PaymentCreate, current_user: User = Depends(get_current_user), service: PaymentService = Depends(get_service)):
    return service.create(payload, current_user)


@router.post('/payments/bank-intents', response_model=PaymentResponse, status_code=201)
def create_bank_intent(payload: BankPaymentIntentCreate, current_user: User = Depends(get_current_user), service: PaymentService = Depends(get_service)):
    return service.create_bank_intent(payload, current_user)


@router.post('/payments/webhook/bank', response_model=PaymentResponse)
def bank_webhook(
    payload: BankWebhookPayload,
    webhook_secret: str | None = Header(default=None, alias='X-Payment-Webhook-Secret'),
    service: PaymentService = Depends(get_service),
):
    if not settings.PAYMENT_WEBHOOK_SECRET or webhook_secret != settings.PAYMENT_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail='Invalid payment webhook secret')
    return service.confirm_webhook(payload)


@router.get('/payments/my', response_model=PaymentListResponse)
def my_payments(
    status: PaymentStatus | None = None,
    payment_method: PaymentMethod | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user), service: PaymentService = Depends(get_service),
):
    items, total = service.list_my(
        current_user, status=status.value if status else None,
        payment_method=payment_method.value if payment_method else None,
        search=None, page=page, page_size=page_size,
    )
    return PaymentListResponse.from_result(items, total, page, page_size)


@router.get('/payments', response_model=PaymentListResponse)
def list_payments(
    status: PaymentStatus | None = None,
    payment_method: PaymentMethod | None = None,
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_permission('payments.manage')), service: PaymentService = Depends(get_service),
):
    items, total = service.list_manage(
        current_user,
        status=status.value if status else None,
        payment_method=payment_method.value if payment_method else None,
        search=search, page=page, page_size=page_size,
    )
    return PaymentListResponse.from_result(items, total, page, page_size)


@router.get('/payments/{payment_id}', response_model=PaymentResponse)
def get_payment(payment_id: int, current_user: User = Depends(get_current_user), service: PaymentService = Depends(get_service)):
    return service.get_for_user(payment_id, current_user)


@router.get('/payments/{payment_id}/deposit-receipt', response_model=DepositReceiptResponse)
def get_deposit_receipt(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_service),
):
    return service.deposit_receipt(payment_id, current_user)


@router.patch('/payments/{payment_id}/confirm', response_model=PaymentResponse)
def confirm_payment(
    payment_id: int, payload: PaymentActionNote = PaymentActionNote(),
    current_user: User = Depends(get_current_user), service: PaymentService = Depends(get_service),
):
    return service.confirm(payment_id, current_user, payload.note)


@router.post('/payments/{payment_id}/demo-confirm', response_model=PaymentResponse)
def demo_confirm_payment(
    payment_id: int, current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_service),
):
    return service.demo_confirm(payment_id, current_user)


@router.patch('/payments/{payment_id}/cancel', response_model=PaymentResponse)
def cancel_payment(
    payment_id: int, payload: PaymentActionNote = PaymentActionNote(),
    current_user: User = Depends(get_current_user), service: PaymentService = Depends(get_service),
):
    return service.cancel(payment_id, current_user, payload.note)

@router.patch('/payments/{payment_id}/fail', response_model=PaymentResponse)
def fail_payment(
    payment_id: int, payload: PaymentActionNote = PaymentActionNote(),
    current_user: User = Depends(get_current_user), service: PaymentService = Depends(get_service),
):
    return service.fail(payment_id, current_user, payload.note)


@router.get('/bookings/{booking_id}/payment-summary', response_model=PaymentSummary)
def payment_summary(booking_id: int, current_user: User = Depends(get_current_user), service: PaymentService = Depends(get_service)):
    return service.summary(booking_id, current_user)
