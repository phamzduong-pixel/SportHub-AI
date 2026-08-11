from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, Time
from sqlalchemy.orm import relationship

from ..database.base import Base


def default_cancellation_rules():
    return [
        {'min_minutes_before': 360, 'refund_percent': 100},
        {'min_minutes_before': 0, 'refund_percent': 0},
    ]


class Facility(Base):
    __tablename__ = 'facilities'

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    name = Column(String(160), nullable=False, index=True)
    location = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    contact_phone = Column(String(20), nullable=True)
    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)
    amenities = Column(JSON, nullable=False, default=list)
    image_urls = Column(JSON, nullable=False, default=list)
    cancellation_rules = Column(JSON, nullable=False, default=default_cancellation_rules)
    free_cancellation_minutes = Column(Integer, nullable=False, default=360)
    legacy_field_id = Column(Integer, nullable=True, unique=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship('User')
    fields = relationship('Field', back_populates='facility')
