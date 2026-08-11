from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.field import Booking
from ..models.time_slot import TimeSlot

class TimeSlotRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, *, field_id: int | None = None, is_active: bool | None = None) -> list[TimeSlot]:
        filters = []
        if field_id is not None:
            filters.append(TimeSlot.field_id == field_id)
        if is_active is not None:
            filters.append(TimeSlot.is_active == is_active)
        return list(self.db.scalars(select(TimeSlot).where(*filters).order_by(TimeSlot.field_id, TimeSlot.start_time, TimeSlot.id)).all())

    def get(self, time_slot_id: int) -> TimeSlot | None:
        return self.db.get(TimeSlot, time_slot_id)

    def find_overlap(self, *, field_id: int, start_time: time, end_time: time, exclude_id: int | None = None) -> TimeSlot | None:
        query = select(TimeSlot).where(
            TimeSlot.field_id == field_id,
            TimeSlot.is_active.is_(True),
            TimeSlot.start_time < end_time,
            TimeSlot.end_time > start_time,
        )
        if exclude_id is not None:
            query = query.where(TimeSlot.id != exclude_id)
        return self.db.scalar(query.limit(1))

    def create(self, data: dict) -> TimeSlot:
        time_slot = TimeSlot(**data)
        self.db.add(time_slot)
        self.db.commit()
        self.db.refresh(time_slot)
        return time_slot

    def update(self, time_slot: TimeSlot, data: dict) -> TimeSlot:
        for key, value in data.items():
            setattr(time_slot, key, value)
        self.db.commit()
        self.db.refresh(time_slot)
        return time_slot

    def delete(self, time_slot: TimeSlot):
        self.db.delete(time_slot)
        self.db.commit()

    def has_booking_usage(self, time_slot_id: int) -> bool:
        return self.db.scalar(select(Booking.id).where(Booking.time_slot_id == time_slot_id).limit(1)) is not None
