from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.field import FieldStatus
from ...models.user import User
from ...repositories.field_repository import FieldRepository
from ...schemas.field import (
    FieldCreate, FieldDeleteResponse, FieldListResponse, FieldResponse,
    FieldStatusUpdate, FieldUpdate,
)
from ...services.field_service import FieldService
from ..dependencies import get_field_viewer, require_owner

router = APIRouter(prefix='/fields', tags=['fields'])

def get_service(db: Session = Depends(get_db)) -> FieldService:
    return FieldService(FieldRepository(db))

@router.get('', response_model=FieldListResponse)
def list_fields(
    search: str | None = Query(default=None, max_length=120),
    sport_type: str | None = Query(default=None, max_length=80),
    status: FieldStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
    current_user: User | None = Depends(get_field_viewer),
    service: FieldService = Depends(get_service),
):
    items, total = service.list_for_user(
        current_user, search=search, sport_type=sport_type,
        status=status.value if status else None, page=page, page_size=page_size,
    )
    return FieldListResponse.from_result(items, total, page, page_size)

@router.get('/{field_id}', response_model=FieldResponse)
def get_field(
    field_id: int,
    current_user: User | None = Depends(get_field_viewer),
    service: FieldService = Depends(get_service),
):
    return service.get_for_user(field_id, current_user)

@router.post('', response_model=FieldResponse, status_code=201)
def create_field(
    payload: FieldCreate,
    current_user: User = Depends(require_owner),
    service: FieldService = Depends(get_service),
):
    return service.create(payload.model_dump(mode='json'), current_user)

@router.put('/{field_id}', response_model=FieldResponse)
def update_field(
    field_id: int,
    payload: FieldUpdate,
    current_user: User = Depends(require_owner),
    service: FieldService = Depends(get_service),
):
    return service.update(field_id, payload.model_dump(mode='json'), current_user)

@router.patch('/{field_id}/status', response_model=FieldResponse)
def update_field_status(
    field_id: int,
    payload: FieldStatusUpdate,
    current_user: User = Depends(require_owner),
    service: FieldService = Depends(get_service),
):
    return service.update_status(field_id, payload.status.value, current_user)

@router.delete('/{field_id}', response_model=FieldDeleteResponse)
def delete_field(
    field_id: int,
    current_user: User = Depends(require_owner),
    service: FieldService = Depends(get_service),
):
    action, field = service.delete(field_id, current_user)
    if action == 'deactivated':
        return {'message': 'Sân có lịch đặt trong tương lai nên đã được chuyển sang inactive', 'action': action, 'field': field}
    return {'message': 'Đã xóa sân', 'action': action, 'field': None}
