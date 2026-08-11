from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, Time, text
from sqlalchemy.orm import relationship

from ..database.base import Base

class FieldStatus(str, Enum):
    AVAILABLE = 'available'
    INACTIVE = 'inactive'
    MAINTENANCE = 'maintenance'

class BookingStatus(str, Enum):
    PENDING_PAYMENT = 'pending_payment'
    PENDING_CONFIRMATION = 'pending_confirmation'
    PENDING = 'pending_confirmation'
    CONFIRMED = 'confirmed'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    CANCELLED_BY_CUSTOMER = 'cancelled_by_customer'
    EXPIRED = 'expired'
    NO_SHOW = 'no_show'
    FAILED = 'failed'
    REJECTED = 'rejected'
    CANCELLED_BY_OWNER = 'cancelled_by_owner'

class Field(Base):
    __tablename__ = 'fields'

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=True, index=True)
    facility_id = Column(Integer, ForeignKey('facilities.id', ondelete='RESTRICT'), nullable=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    sport_type = Column(String(80), nullable=False, index=True)
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=False)
    capacity = Column(Integer, nullable=False)
    base_price = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), nullable=False, default=FieldStatus.AVAILABLE.value, index=True)
    image_url = Column(String(500), nullable=True)
    amenities = Column(JSON, nullable=False, default=list)
    rating = Column(Float, nullable=False, default=0)
    review_count = Column(Integer, nullable=False, default=0)
    distance_km = Column(Float, nullable=True)
    deposit_type = Column(String(20), nullable=False, default='percentage')
    deposit_value = Column(Numeric(12, 2), nullable=False, default=30)
    cancellation_policy = Column(String(30), nullable=False, default='manual_review')
    cancellation_refund_percent = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    bookings = relationship('Booking', back_populates='field', passive_deletes=True)
    time_slots = relationship('TimeSlot', back_populates='field', cascade='all, delete-orphan')
    owner = relationship('User', back_populates='owned_fields')
    facility = relationship('Facility', back_populates='fields')

class Booking(Base):
    __tablename__ = 'bookings'
    __table_args__ = (
        Index(
            'uq_open_booking_slot_date', 'field_id', 'booking_date', 'time_slot_id',
            unique=True,
            sqlite_where=text("status IN ('pending_payment', 'pending_confirmation', 'confirmed', 'in_progress')"),
            postgresql_where=text("status IN ('pending_payment', 'pending_confirmation', 'confirmed', 'in_progress')"),
        ),
    )

    id = Column(Integer, primary_key=True)
    booking_code = Column(String(24), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    facility_id = Column(Integer, ForeignKey('facilities.id', ondelete='RESTRICT'), nullable=True, index=True)
    facility_name_snapshot = Column(String(160), nullable=True)
    field_id = Column(Integer, ForeignKey('fields.id', ondelete='RESTRICT'), nullable=False, index=True)
    time_slot_id = Column(Integer, ForeignKey('time_slots.id', ondelete='RESTRICT'), nullable=False, index=True)
    booking_date = Column(Date, nullable=False, index=True)
    start_time_snapshot = Column(Time, nullable=False)
    end_time_snapshot = Column(Time, nullable=False)
    price_snapshot = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    deposit_type = Column(String(20), nullable=False, default='percentage')
    deposit_value = Column(Numeric(12, 2), nullable=False, default=30)
    deposit_amount = Column(Numeric(12, 2), nullable=False, default=0)
    paid_amount = Column(Numeric(12, 2), nullable=False, default=0)
    remaining_amount = Column(Numeric(12, 2), nullable=False, default=0)
    payment_status = Column(String(20), nullable=False, default='unpaid', index=True)
    cancellation_policy = Column(String(30), nullable=False, default='manual_review')
    cancellation_refund_percent = Column(Numeric(5, 2), nullable=True)
    refundable_deposit_amount = Column(Numeric(12, 2), nullable=True)
    free_cancellation_minutes = Column(Integer, nullable=False, default=360)
    refund_amount = Column(Numeric(12, 2), nullable=False, default=0)
    credit_amount = Column(Numeric(12, 2), nullable=False, default=0)
    additional_payment_required = Column(Numeric(12, 2), nullable=False, default=0)
    refund_status = Column(String(20), nullable=False, default='not_requested')
    status = Column(String(30), nullable=False, default=BookingStatus.PENDING_PAYMENT.value, index=True)
    hold_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    cancellation_reason = Column(Text, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    rescheduled_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    field = relationship('Field', back_populates='bookings')
    facility = relationship('Facility')
    time_slot = relationship('TimeSlot', back_populates='bookings')
    customer = relationship('User', back_populates='bookings', foreign_keys=[customer_id])
    canceller = relationship('User', foreign_keys=[cancelled_by])
    payments = relationship('Payment', back_populates='booking', passive_deletes=True)
    invoice = relationship('Invoice', back_populates='booking', uselist=False, passive_deletes=True)
    refund_request = relationship('RefundRequest', back_populates='booking', uselist=False, passive_deletes=True)
    review = relationship('Review', back_populates='booking', uselist=False, passive_deletes=True)
    activities = relationship('BookingActivity', back_populates='booking', passive_deletes=True, order_by='BookingActivity.created_at')
