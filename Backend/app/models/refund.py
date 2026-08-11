from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database.base import Base


class RefundStatus(str, Enum):
    REFUND_PENDING = 'refund_pending'
    REFUNDED = 'refunded'
    REFUND_OVERDUE = 'refund_overdue'
    DISPUTED = 'disputed'


class RefundRequest(Base):
    __tablename__ = 'refund_requests'
    __table_args__ = (UniqueConstraint('booking_id', name='uq_refund_request_booking'),)

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete='RESTRICT'), nullable=False, index=True)
    refund_payment_id = Column(Integer, ForeignKey('payments.id', ondelete='RESTRICT'), nullable=False, unique=True)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(30), nullable=False, default=RefundStatus.REFUND_PENDING.value, index=True)
    reason = Column(Text, nullable=False)
    requested_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    processed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    customer_action_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    customer_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    disputed_at = Column(DateTime(timezone=True), nullable=True)
    transaction_reference = Column(String(120), nullable=True, unique=True)
    evidence_url = Column(String(1000), nullable=True)
    dispute_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    booking = relationship('Booking', back_populates='refund_request')
    refund_payment = relationship('Payment', foreign_keys=[refund_payment_id])
    requester = relationship('User', foreign_keys=[requested_by])
    processor = relationship('User', foreign_keys=[processed_by])
    customer_actor = relationship('User', foreign_keys=[customer_action_by])


class BookingActivity(Base):
    __tablename__ = 'booking_activities'

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete='RESTRICT'), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    actor_role = Column(String(20), nullable=True)
    action = Column(String(50), nullable=False, index=True)
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    booking = relationship('Booking', back_populates='activities')
    actor = relationship('User')
