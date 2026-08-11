from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Time
from sqlalchemy.orm import relationship

from ..database.base import Base

class TimeSlot(Base):
    __tablename__ = 'time_slots'

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey('fields.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    weekday_price = Column(Numeric(12, 2), nullable=True)
    weekend_price = Column(Numeric(12, 2), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    field = relationship('Field', back_populates='time_slots')
    bookings = relationship('Booking', back_populates='time_slot', passive_deletes=True)
