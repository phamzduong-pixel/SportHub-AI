from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database.base import Base


class FieldBlock(Base):
    __tablename__ = 'field_blocks'

    id = Column(Integer, primary_key=True)
    field_id = Column(Integer, ForeignKey('fields.id', ondelete='CASCADE'), nullable=False, index=True)
    block_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    reason = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    field = relationship('Field')
    creator = relationship('User')


class BookingComplaint(Base):
    __tablename__ = 'booking_complaints'
    __table_args__ = (UniqueConstraint('booking_id', 'customer_id', name='uq_booking_complaint_customer'),)

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete='RESTRICT'), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    category = Column(String(40), nullable=False)
    description = Column(Text, nullable=False)
    evidence_url = Column(String(1000), nullable=True)
    status = Column(String(20), nullable=False, default='open', index=True)
    resolution = Column(Text, nullable=True)
    resolved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    booking = relationship('Booking')
    customer = relationship('User', foreign_keys=[customer_id])
    resolver = relationship('User', foreign_keys=[resolved_by])


class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    actor_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    actor_role = Column(String(20), nullable=True)
    entity_type = Column(String(40), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    action = Column(String(60), nullable=False, index=True)
    changes = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    actor = relationship('User', foreign_keys=[actor_id])
