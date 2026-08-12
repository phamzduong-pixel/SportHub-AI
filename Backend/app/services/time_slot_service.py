from fastapi import HTTPException

from ..core.ownership import owns_field
from ..models.field import Field, FieldStatus
from ..models.time_slot import TimeSlot
from ..models.user import User
from ..repositories.time_slot_repository import TimeSlotRepository
from .audit_service import record_audit

class TimeSlotService:
    def __init__(self, repository: TimeSlotRepository):
        self.repository = repository

    def list_manage(self, field_id: int | None, is_active: bool | None, user: User) -> list[TimeSlot]:
        if field_id is not None:
            self._owned_field_or_404(field_id, user)
        return [item for item in self.repository.list(field_id=field_id, is_active=is_active) if owns_field(user, item.field, self.repository.db)]

    def list_for_field(self, field_id: int, user: User | None) -> list[TimeSlot]:
        field = self._field_or_404(field_id)
        if user is None or user.role == 'CUSTOMER':
            if field.status != FieldStatus.AVAILABLE.value:
                raise HTTPException(status_code=404, detail='Không tìm thấy sân')
            return self.repository.list(field_id=field_id, is_active=True)
        if not owns_field(user, field, self.repository.db):
            raise HTTPException(status_code=404, detail='Không tìm thấy sân')
        return self.repository.list(field_id=field_id, is_active=None)

    def create(self, data: dict, user: User) -> TimeSlot:
        self._owned_field_or_404(data['field_id'], user)
        self._validate_overlap(data)
        item = self.repository.create(data)
        record_audit(self.repository.db, user, 'time_slot', item.id, 'time_slot_created', {'field_id': item.field_id, 'price': float(item.price)})
        self.repository.db.commit()
        return item

    def update(self, time_slot_id: int, data: dict, user: User) -> TimeSlot:
        time_slot = self._slot_or_404(time_slot_id)
        self._owned_field_or_404(time_slot.field_id, user)
        self._owned_field_or_404(data['field_id'], user)
        if data['field_id'] != time_slot.field_id and self.repository.has_booking_usage(time_slot_id):
            raise HTTPException(status_code=409, detail='Khung giờ đã có booking nên không thể chuyển sang sân khác')
        self._validate_overlap(data, exclude_id=time_slot_id)
        old_price = float(time_slot.price)
        item = self.repository.update(time_slot, data)
        record_audit(self.repository.db, user, 'time_slot', item.id, 'time_slot_updated', {'old_price': old_price, 'new_price': float(item.price), 'weekday_price': float(item.weekday_price) if item.weekday_price is not None else None, 'weekend_price': float(item.weekend_price) if item.weekend_price is not None else None})
        self.repository.db.commit()
        return item

    def update_status(self, time_slot_id: int, is_active: bool, user: User) -> TimeSlot:
        time_slot = self._slot_or_404(time_slot_id)
        self._owned_field_or_404(time_slot.field_id, user)
        if is_active:
            self._validate_overlap({
                'field_id': time_slot.field_id,
                'start_time': time_slot.start_time,
                'end_time': time_slot.end_time,
                'is_active': True,
            }, exclude_id=time_slot_id)
        item = self.repository.update(time_slot, {'is_active': is_active})
        record_audit(self.repository.db, user, 'time_slot', item.id, 'time_slot_status_changed', {'is_active': is_active})
        self.repository.db.commit()
        return item

    def delete(self, time_slot_id: int, user: User) -> tuple[str, TimeSlot | None]:
        time_slot = self._slot_or_404(time_slot_id)
        self._owned_field_or_404(time_slot.field_id, user)
        if self.repository.has_booking_usage(time_slot_id):
            time_slot = self.repository.update(time_slot, {'is_active': False})
            record_audit(self.repository.db, user, 'time_slot', time_slot.id, 'time_slot_delete_deactivated', {'field_id': time_slot.field_id})
            self.repository.db.commit()
            return 'deactivated', time_slot
        slot_id, field_id = time_slot.id, time_slot.field_id
        self.repository.delete(time_slot)
        record_audit(self.repository.db, user, 'time_slot', slot_id, 'time_slot_deleted', {'field_id': field_id})
        self.repository.db.commit()
        return 'deleted', None

    def _validate_overlap(self, data: dict, exclude_id: int | None = None):
        if not data.get('is_active', True):
            return
        overlap = self.repository.find_overlap(
            field_id=data['field_id'], start_time=data['start_time'],
            end_time=data['end_time'], exclude_id=exclude_id,
        )
        if overlap:
            raise HTTPException(
                status_code=409,
                detail=f'Khung giờ chồng lấn với "{overlap.name}" ({overlap.start_time.strftime("%H:%M")} - {overlap.end_time.strftime("%H:%M")})',
            )

    def _slot_or_404(self, time_slot_id: int) -> TimeSlot:
        time_slot = self.repository.get(time_slot_id)
        if time_slot is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy khung giờ')
        return time_slot

    def _field_or_404(self, field_id: int) -> Field:
        field = self.repository.db.get(Field, field_id)
        if field is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy sân')
        return field

    def _owned_field_or_404(self, field_id: int, user: User) -> Field:
        field = self._field_or_404(field_id)
        if not owns_field(user, field, self.repository.db):
            raise HTTPException(status_code=404, detail='Không tìm thấy sân')
        return field
