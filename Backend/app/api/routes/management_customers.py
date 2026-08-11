from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.user import User
from ...schemas.management_customer import ManagementCustomerDetail, ManagementCustomerList
from ...services.management_customer_service import ManagementCustomerService
from ..dependencies import require_permission

router = APIRouter(prefix='/management/customers', tags=['management-customers'])


@router.get('', response_model=ManagementCustomerList)
def list_customers(
    search: str | None = Query(None, max_length=120),
    has_active: bool | None = None, has_completed: bool | None = None, has_cancelled: bool | None = None,
    last_booking_from: date | None = None, last_booking_to: date | None = None,
    sort_by: str = Query('last_booking', pattern='^(last_booking|booking_count|transaction_value)$'),
    sort_order: str = Query('desc', pattern='^(asc|desc)$'),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission('customers.view')), db: Session = Depends(get_db),
):
    items, total = ManagementCustomerService(db).list(
        user, search=search, has_active=has_active, has_completed=has_completed,
        has_cancelled=has_cancelled, last_booking_from=last_booking_from,
        last_booking_to=last_booking_to, sort_by=sort_by, sort_order=sort_order,
        page=page, page_size=page_size,
    )
    return ManagementCustomerList.from_result(items, total, page, page_size)


@router.get('/{customer_id}', response_model=ManagementCustomerDetail)
def customer_detail(
    customer_id: int, user: User = Depends(require_permission('customers.view')),
    db: Session = Depends(get_db),
):
    return ManagementCustomerService(db).detail(user, customer_id)
