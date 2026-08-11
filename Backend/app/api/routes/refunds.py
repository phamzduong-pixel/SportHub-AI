from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.refund import RefundStatus
from ...models.user import User
from ...schemas.refund import RefundDisputeRequest, RefundListResponse, RefundMarkPaidRequest, RefundReputationResponse, RefundResponse
from ...services.refund_service import RefundService
from ..dependencies import get_current_user, require_permission

router = APIRouter(tags=['refunds'])


def get_service(db: Session = Depends(get_db)):
    return RefundService(db)


@router.get('/refunds/my', response_model=RefundListResponse)
def my_refunds(status: RefundStatus | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), current_user: User = Depends(get_current_user), service: RefundService = Depends(get_service)):
    items, total = service.list_my(current_user, status=status.value if status else None, page=page, page_size=page_size)
    return RefundListResponse.from_result(items, total, page, page_size)


@router.get('/refunds/reputation', response_model=RefundReputationResponse)
def refund_reputation(current_user: User = Depends(require_permission('payments.manage')), service: RefundService = Depends(get_service)):
    return service.reputation(current_user)


@router.get('/refunds', response_model=RefundListResponse)
def manage_refunds(status: RefundStatus | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), current_user: User = Depends(require_permission('payments.manage')), service: RefundService = Depends(get_service)):
    items, total = service.list_manage(current_user, status=status.value if status else None, page=page, page_size=page_size)
    return RefundListResponse.from_result(items, total, page, page_size)


@router.get('/refunds/{refund_id}', response_model=RefundResponse)
def get_refund(refund_id: int, current_user: User = Depends(get_current_user), service: RefundService = Depends(get_service)):
    return service.get_for_user(refund_id, current_user)


@router.patch('/refunds/{refund_id}/mark-refunded', response_model=RefundResponse)
def mark_refunded(refund_id: int, payload: RefundMarkPaidRequest, current_user: User = Depends(require_permission('payments.manage')), service: RefundService = Depends(get_service)):
    return service.mark_refunded(refund_id, payload, current_user)


@router.patch('/refunds/{refund_id}/confirm-received', response_model=RefundResponse)
def confirm_received(refund_id: int, current_user: User = Depends(get_current_user), service: RefundService = Depends(get_service)):
    return service.confirm_received(refund_id, current_user)


@router.patch('/refunds/{refund_id}/dispute', response_model=RefundResponse)
def dispute_refund(refund_id: int, payload: RefundDisputeRequest, current_user: User = Depends(get_current_user), service: RefundService = Depends(get_service)):
    return service.dispute(refund_id, payload.reason, current_user)
