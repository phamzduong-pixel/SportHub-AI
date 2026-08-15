from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..dependencies import get_current_user
from ...database.session import get_db
from ...models.user import User
from ...schemas.notification import NotificationListResponse, NotificationResponse, NotificationUnreadResponse
from ...services.notification_service import NotificationService

router = APIRouter(prefix='/notifications', tags=['notifications'])


@router.get('', response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    service = NotificationService(db)
    service.create_due_reminders(current_user.id)
    return service.list_for_user(current_user.id, page=page, page_size=page_size)


@router.get('/unread-count', response_model=NotificationUnreadResponse)
def unread_count(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service = NotificationService(db)
    service.create_due_reminders(current_user.id)
    return {'unread_count': service.unread_count(current_user.id)}


@router.patch('/read-all')
def mark_all_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {'updated_count': NotificationService(db).mark_all_read(current_user.id)}


@router.patch('/{notification_id}/read', response_model=NotificationResponse)
def mark_read(notification_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return NotificationService(db).mark_read(notification_id, current_user.id)
