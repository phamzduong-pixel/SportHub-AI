from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.user import User
from ...repositories.time_slot_repository import TimeSlotRepository
from ...schemas.time_slot import (
    TimeSlotCreate, TimeSlotDeleteResponse, TimeSlotResponse,
    TimeSlotStatusUpdate, TimeSlotUpdate,
)
from ...services.time_slot_service import TimeSlotService
from ..dependencies import get_optional_current_user, require_permission

router = APIRouter(tags=['time-slots'])

def get_service(db: Session = Depends(get_db)) -> TimeSlotService:
    return TimeSlotService(TimeSlotRepository(db))

@router.get('/time-slots', response_model=list[TimeSlotResponse])
def list_time_slots(
    field_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
    current_user: User = Depends(require_permission('time_slots.manage')),
    service: TimeSlotService = Depends(get_service),
):
    return service.list_manage(field_id, is_active, current_user)

@router.get('/fields/{field_id}/time-slots', response_model=list[TimeSlotResponse])
def list_field_time_slots(
    field_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    service: TimeSlotService = Depends(get_service),
):
    return service.list_for_field(field_id, current_user)

@router.post('/time-slots', response_model=TimeSlotResponse, status_code=201)
def create_time_slot(
    payload: TimeSlotCreate,
    current_user: User = Depends(require_permission('time_slots.manage')),
    service: TimeSlotService = Depends(get_service),
):
    return service.create(payload.model_dump(mode='python'), current_user)

@router.put('/time-slots/{time_slot_id}', response_model=TimeSlotResponse)
def update_time_slot(
    time_slot_id: int,
    payload: TimeSlotUpdate,
    current_user: User = Depends(require_permission('time_slots.manage')),
    service: TimeSlotService = Depends(get_service),
):
    return service.update(time_slot_id, payload.model_dump(mode='python'), current_user)

@router.patch('/time-slots/{time_slot_id}/status', response_model=TimeSlotResponse)
def update_time_slot_status(
    time_slot_id: int,
    payload: TimeSlotStatusUpdate,
    current_user: User = Depends(require_permission('time_slots.manage')),
    service: TimeSlotService = Depends(get_service),
):
    return service.update_status(time_slot_id, payload.is_active, current_user)

@router.delete('/time-slots/{time_slot_id}', response_model=TimeSlotDeleteResponse)
def delete_time_slot(
    time_slot_id: int,
    current_user: User = Depends(require_permission('time_slots.manage')),
    service: TimeSlotService = Depends(get_service),
):
    action, time_slot = service.delete(time_slot_id, current_user)
    if action == 'deactivated':
        return {'message': 'Khung giờ đã có lịch đặt nên được khóa thay vì xóa', 'action': action, 'time_slot': time_slot}
    return {'message': 'Đã xóa khung giờ', 'action': action, 'time_slot': None}
