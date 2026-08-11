from fastapi import HTTPException

from ..core.ownership import management_owner_id, owns_field
from ..models.facility import Facility, default_cancellation_rules
from ..models.field import Field, FieldStatus
from ..models.user import User
from ..repositories.field_repository import FieldRepository
from .audit_service import record_audit

class FieldService:
    def __init__(self, repository: FieldRepository):
        self.repository = repository

    def list_for_user(self, user: User | None, **filters):
        if user is None or user.role == 'CUSTOMER':
            filters['status'] = FieldStatus.AVAILABLE.value
            filters['facility_active'] = True
        else:
            owner_id = management_owner_id(user, self.repository.db)
            if owner_id is None:
                raise HTTPException(status_code=403, detail='Tài khoản quản lý chưa được gán cho OWNER')
            filters['owner_id'] = owner_id
        return self.repository.list(**filters)

    def get_for_user(self, field_id: int, user: User | None) -> Field:
        field = self.repository.get(field_id)
        public_hidden = field is not None and field.facility is not None and not field.facility.is_active
        if field is None or ((user is None or user.role == 'CUSTOMER') and (field.status != FieldStatus.AVAILABLE.value or public_hidden)):
            raise HTTPException(status_code=404, detail='Không tìm thấy sân')
        if user is not None and user.role == 'OWNER' and not owns_field(user, field, self.repository.db):
            raise HTTPException(status_code=404, detail='Không tìm thấy sân')
        return field

    def create(self, data: dict, user: User) -> Field:
        data['owner_id'] = management_owner_id(user, self.repository.db)
        if data['owner_id'] is None:
            raise HTTPException(status_code=403, detail='Tài khoản quản lý chưa được gán cho OWNER')
        facility_id = data.get('facility_id')
        if facility_id:
            facility = self.repository.db.get(Facility, facility_id)
            if facility is None or facility.owner_id != data['owner_id']:
                raise HTTPException(status_code=404, detail='Không tìm thấy cơ sở')
            data['location'] = facility.location
        else:
            facility = Facility(
                owner_id=data['owner_id'], name=data['name'], location=data['location'],
                description=data.get('description'), cancellation_rules=default_cancellation_rules(),
            )
            self.repository.db.add(facility); self.repository.db.flush()
            data['facility_id'] = facility.id
        item = self.repository.create(data)
        record_audit(self.repository.db, user, 'field', item.id, 'field_created', {'name': item.name, 'base_price': float(item.base_price), 'status': item.status})
        self.repository.db.commit(); return item

    def update(self, field_id: int, data: dict, user: User) -> Field:
        field = self._get_owned_or_404(field_id, user)
        facility_id = data.get('facility_id') or field.facility_id
        if facility_id:
            facility = self.repository.db.get(Facility, facility_id)
            if facility is None or facility.owner_id != management_owner_id(user, self.repository.db):
                raise HTTPException(status_code=404, detail='Không tìm thấy cơ sở')
            data['facility_id'] = facility.id
            data['location'] = facility.location
        old_price = float(field.base_price); old_status = field.status
        item = self.repository.update(field, data)
        record_audit(self.repository.db, user, 'field', item.id, 'field_updated', {'old_base_price': old_price, 'new_base_price': float(item.base_price), 'old_status': old_status, 'new_status': item.status})
        self.repository.db.commit(); return item

    def update_status(self, field_id: int, status: str, user: User) -> Field:
        field = self._get_owned_or_404(field_id, user)
        old_status = field.status; item = self.repository.update(field, {'status': status})
        record_audit(self.repository.db, user, 'field', item.id, 'field_status_changed', {'from': old_status, 'to': status})
        self.repository.db.commit(); return item

    def delete(self, field_id: int, user: User) -> tuple[str, Field | None]:
        field = self._get_owned_or_404(field_id, user)
        if self.repository.has_booking_usage(field_id):
            field = self.repository.update(field, {'status': FieldStatus.INACTIVE.value})
            record_audit(self.repository.db, user, 'field', field.id, 'field_deactivated', {'reason': 'has_booking_history'}); self.repository.db.commit()
            return 'deactivated', field
        record_audit(self.repository.db, user, 'field', field.id, 'field_deleted', {'name': field.name})
        self.repository.db.commit()
        self.repository.delete(field)
        return 'deleted', None

    def _get_or_404(self, field_id: int) -> Field:
        field = self.repository.get(field_id)
        if field is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy sân')
        return field

    def _get_owned_or_404(self, field_id: int, user: User) -> Field:
        field = self._get_or_404(field_id)
        if not owns_field(user, field, self.repository.db):
            raise HTTPException(status_code=404, detail='Không tìm thấy sân')
        return field
