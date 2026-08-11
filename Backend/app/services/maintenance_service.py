from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..core.config import settings
from ..core.datetime_utils import as_utc
from ..core.ownership import management_owner_id
from ..models.field import Booking, Field
from ..models.maintenance import FieldMaintenance, MaintenanceStatus
from .audit_service import record_audit


BLOCKING_BOOKING_STATUSES = ('pending_payment', 'pending_confirmation', 'confirmed', 'in_progress')
ACTIVE_MAINTENANCE_STATUSES = (MaintenanceStatus.SCHEDULED.value, MaintenanceStatus.IN_PROGRESS.value)


class MaintenanceService:
    def __init__(self, db):
        self.db = db
        self.tz = ZoneInfo(settings.TIMEZONE)

    def _owner_id(self, user):
        owner_id = management_owner_id(user, self.db)
        if owner_id is None:
            raise HTTPException(status_code=403, detail='Bạn không có quyền quản lý bảo trì')
        return owner_id

    def _normalize(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=self.tz)
        return value.astimezone(timezone.utc)

    def _field(self, field_id: int, user, lock=False):
        query = select(Field).options(joinedload(Field.facility)).where(Field.id == field_id, Field.owner_id == self._owner_id(user))
        if lock:
            query = query.with_for_update()
        field = self.db.scalar(query)
        if field is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy sân thuộc quyền quản lý')
        return field

    def _item(self, maintenance_id: int, user, lock=False):
        query = self._query().where(FieldMaintenance.id == maintenance_id, Field.owner_id == self._owner_id(user))
        if lock:
            query = query.with_for_update()
        item = self.db.scalar(query)
        if item is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy lịch bảo trì')
        return item

    @staticmethod
    def _query():
        return select(FieldMaintenance).options(
            joinedload(FieldMaintenance.field).joinedload(Field.facility),
            joinedload(FieldMaintenance.creator),
        ).join(Field, FieldMaintenance.field_id == Field.id)

    def list(self, user, *, field_id=None, facility_id=None, status=None, maintenance_type=None, date_from=None, date_to=None):
        filters = [Field.owner_id == self._owner_id(user)]
        if field_id:
            filters.append(FieldMaintenance.field_id == field_id)
        if facility_id:
            filters.append(Field.facility_id == facility_id)
        if status:
            filters.append(FieldMaintenance.status == status)
        if maintenance_type:
            filters.append(FieldMaintenance.maintenance_type == maintenance_type)
        if date_from:
            filters.append(FieldMaintenance.ends_at >= self._normalize(datetime.combine(date_from, datetime.min.time())))
        if date_to:
            filters.append(FieldMaintenance.starts_at < self._normalize(datetime.combine(date_to, datetime.max.time())))
        items = self.db.scalars(self._query().where(*filters).order_by(FieldMaintenance.starts_at.desc())).unique().all()
        return [self.response(item) for item in items]

    def summary(self, user):
        items = self.list(user)
        now = datetime.now(timezone.utc)
        return {
            'upcoming': sum(item['status'] == 'SCHEDULED' and as_utc(item['ends_at']) > now for item in items),
            'in_progress': sum(item['status'] == 'IN_PROGRESS' for item in items),
            'completed': sum(item['status'] == 'COMPLETED' for item in items),
            'cancelled': sum(item['status'] == 'CANCELLED' for item in items),
        }

    def create(self, payload, user):
        field = self._field(payload.field_id, user, lock=True)
        values = payload.model_dump()
        values['starts_at'], values['ends_at'] = self._normalize(payload.starts_at), self._normalize(payload.ends_at)
        self._ensure_no_maintenance_overlap(field.id, values['starts_at'], values['ends_at'])
        item = FieldMaintenance(**values, created_by=user.id)
        self.db.add(item); self.db.flush()
        record_audit(self.db, user, 'field_maintenance', item.id, 'maintenance_created', self._audit_values(item))
        self.db.commit()
        return self.response(self._item(item.id, user))

    def update(self, maintenance_id, payload, user):
        item = self._item(maintenance_id, user, lock=True)
        if item.status not in ACTIVE_MAINTENANCE_STATUSES:
            raise HTTPException(status_code=409, detail='Chỉ lịch đang lên kế hoạch hoặc đang thực hiện mới được sửa')
        field = self._field(payload.field_id, user)
        starts_at, ends_at = self._normalize(payload.starts_at), self._normalize(payload.ends_at)
        self._ensure_no_maintenance_overlap(field.id, starts_at, ends_at, exclude_id=item.id)
        before = self._audit_values(item)
        for key, value in payload.model_dump().items():
            setattr(item, key, self._normalize(value) if key in ('starts_at', 'ends_at') else value)
        self.db.flush()
        record_audit(self.db, user, 'field_maintenance', item.id, 'maintenance_updated', {'before': before, 'after': self._audit_values(item)})
        self.db.commit()
        return self.response(self._item(item.id, user))

    def transition(self, maintenance_id, target, user):
        item = self._item(maintenance_id, user, lock=True)
        allowed = {
            'IN_PROGRESS': {'SCHEDULED'}, 'COMPLETED': {'IN_PROGRESS'}, 'CANCELLED': {'SCHEDULED', 'IN_PROGRESS'},
        }
        if target not in allowed or item.status not in allowed[target]:
            raise HTTPException(status_code=409, detail='Chuyển trạng thái bảo trì không hợp lệ')
        old = item.status; now = datetime.now(timezone.utc); item.status = target
        if target == 'IN_PROGRESS': item.started_at = now
        if target == 'COMPLETED': item.completed_at = now
        if target == 'CANCELLED': item.cancelled_at = now
        record_audit(self.db, user, 'field_maintenance', item.id, f'maintenance_{target.lower()}', {'from': old, 'to': target})
        self.db.commit()
        return self.response(self._item(item.id, user))

    def _ensure_no_maintenance_overlap(self, field_id, starts_at, ends_at, exclude_id=None):
        query = select(FieldMaintenance.id).where(
            FieldMaintenance.field_id == field_id, FieldMaintenance.status.in_(ACTIVE_MAINTENANCE_STATUSES),
            FieldMaintenance.starts_at < ends_at, FieldMaintenance.ends_at > starts_at,
        )
        if exclude_id:
            query = query.where(FieldMaintenance.id != exclude_id)
        if self.db.scalar(query.limit(1)):
            raise HTTPException(status_code=409, detail='Khoảng thời gian bị trùng với lịch bảo trì đang hoạt động')

    def _affected_bookings(self, item):
        local_start, local_end = as_utc(item.starts_at).astimezone(self.tz), as_utc(item.ends_at).astimezone(self.tz)
        bookings = self.db.scalars(select(Booking).options(joinedload(Booking.customer)).where(
            Booking.field_id == item.field_id, Booking.status.in_(BLOCKING_BOOKING_STATUSES),
            Booking.booking_date >= local_start.date(), Booking.booking_date <= local_end.date(),
        )).unique().all()
        result = []
        for booking in bookings:
            starts = datetime.combine(booking.booking_date, booking.start_time_snapshot, tzinfo=self.tz).astimezone(timezone.utc)
            ends = datetime.combine(booking.booking_date, booking.end_time_snapshot, tzinfo=self.tz).astimezone(timezone.utc)
            if starts < as_utc(item.ends_at) and ends > as_utc(item.starts_at):
                result.append({'id': booking.id, 'booking_code': booking.booking_code, 'customer_name': booking.customer.full_name,
                               'starts_at': starts, 'ends_at': ends, 'status': booking.status, 'paid_amount': float(booking.paid_amount or 0)})
        return result

    def response(self, item):
        field = item.field
        return {
            'id': item.id, 'field_id': item.field_id, 'field_name': field.name,
            'facility_id': field.facility_id, 'facility_name': field.facility.name if field.facility else field.name,
            'maintenance_type': item.maintenance_type, 'title': item.title,
            'starts_at': as_utc(item.starts_at), 'ends_at': as_utc(item.ends_at), 'priority': item.priority,
            'notes': item.notes, 'estimated_cost': float(item.estimated_cost) if item.estimated_cost is not None else None,
            'actual_cost': float(item.actual_cost) if item.actual_cost is not None else None, 'status': item.status,
            'created_by': item.created_by, 'created_by_name': item.creator.full_name,
            'started_at': as_utc(item.started_at), 'completed_at': as_utc(item.completed_at),
            'cancelled_at': as_utc(item.cancelled_at), 'created_at': as_utc(item.created_at),
            'updated_at': as_utc(item.updated_at), 'affected_bookings': self._affected_bookings(item),
        }

    @staticmethod
    def _audit_values(item):
        return {'field_id': item.field_id, 'type': item.maintenance_type, 'title': item.title,
                'starts_at': as_utc(item.starts_at).isoformat(), 'ends_at': as_utc(item.ends_at).isoformat(),
                'priority': item.priority, 'estimated_cost': float(Decimal(item.estimated_cost or 0))}
