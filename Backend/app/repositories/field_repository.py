from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models.field import Booking, Field
from ..models.facility import Facility

class FieldRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, *, search: str | None, sport_type: str | None, status: str | None, page: int, page_size: int, owner_id: int | None = None, facility_active: bool | None = None):
        filters = []
        if owner_id is not None:
            filters.append(or_(Field.owner_id == owner_id, Field.owner_id.is_(None)))
        if search:
            filters.append(Field.name.ilike(f'%{search.strip()}%'))
        if sport_type:
            filters.append(func.lower(Field.sport_type) == sport_type.strip().lower())
        if status:
            filters.append(Field.status == status)
        if facility_active is not None:
            filters.append(or_(Field.facility_id.is_(None), Field.facility.has(Facility.is_active.is_(facility_active))))
        total = self.db.scalar(select(func.count(Field.id)).where(*filters)) or 0
        items = self.db.scalars(
            select(Field).where(*filters).order_by(Field.created_at.desc(), Field.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return list(items), total

    def get(self, field_id: int) -> Field | None:
        return self.db.get(Field, field_id)

    def create(self, data: dict) -> Field:
        field = Field(**data)
        self.db.add(field)
        self.db.commit()
        self.db.refresh(field)
        return field

    def update(self, field: Field, data: dict) -> Field:
        for key, value in data.items():
            setattr(field, key, value)
        self.db.commit()
        self.db.refresh(field)
        return field

    def delete(self, field: Field):
        self.db.delete(field)
        self.db.commit()

    def has_booking_usage(self, field_id: int) -> bool:
        return self.db.scalar(select(Booking.id).where(Booking.field_id == field_id).limit(1)) is not None
