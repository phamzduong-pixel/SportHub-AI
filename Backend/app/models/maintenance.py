from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from ..database.base import Base


class MaintenanceStatus(str, Enum):
    SCHEDULED = 'SCHEDULED'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'


class FieldMaintenance(Base):
    __tablename__ = 'field_maintenances'

    id = Column(Integer, primary_key=True)
    field_id = Column(Integer, ForeignKey('fields.id', ondelete='RESTRICT'), nullable=False, index=True)
    maintenance_type = Column(String(40), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=False, index=True)
    priority = Column(String(20), nullable=False, default='MEDIUM', index=True)
    notes = Column(Text, nullable=True)
    estimated_cost = Column(Numeric(12, 2), nullable=True)
    actual_cost = Column(Numeric(12, 2), nullable=True)
    status = Column(String(20), nullable=False, default=MaintenanceStatus.SCHEDULED.value, index=True)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    field = relationship('Field')
    creator = relationship('User')
