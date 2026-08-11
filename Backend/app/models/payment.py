from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import relationship

from ..database.base import Base


class PaymentMethod(str, Enum):
    CASH = 'cash'
    BANK_TRANSFER = 'bank_transfer'
    MOCK_ONLINE = 'mock_online'


class PaymentType(str, Enum):
    DEPOSIT = 'deposit'
    REMAINING = 'remaining'
    FULL = 'full'
    REFUND = 'refund'


class PaymentStatus(str, Enum):
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'


class EscrowStatus(str, Enum):
    PENDING = 'pending'
    HELD = 'held'
    RELEASED = 'released'
    REFUNDED = 'refunded'
    FAILED = 'failed'


class Payment(Base):
    __tablename__ = 'payments'
    __table_args__ = (
        Index(
            'uq_pending_payment_per_booking', 'booking_id', unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete='RESTRICT'), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=True, index=True)
    transaction_code = Column(String(30), unique=True, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)
    deposit_amount = Column(Numeric(12, 2), nullable=False, default=0)
    remaining_amount = Column(Numeric(12, 2), nullable=False, default=0)
    paid_amount = Column(Numeric(12, 2), nullable=False, default=0)
    payment_status = Column(String(20), nullable=False, default=PaymentStatus.PENDING.value)
    bank_id = Column(String(30), nullable=True)
    bank_name = Column(String(120), nullable=True)
    bank_account_no = Column(String(50), nullable=True)
    bank_account_name = Column(String(150), nullable=True)
    transfer_content = Column(String(80), unique=True, nullable=True, index=True)
    qr_url = Column(String(1000), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    provider_reference = Column(String(120), unique=True, nullable=True, index=True)
    provider = Column(String(80), nullable=True)
    verification_source = Column(String(30), nullable=True)
    refund_status = Column(String(20), nullable=False, default='not_requested', index=True)
    payment_method = Column(String(30), nullable=False, index=True)
    payment_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default=PaymentStatus.PENDING.value, index=True)
    escrow_status = Column(String(20), nullable=False, default=EscrowStatus.PENDING.value, index=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    failed_reason = Column(Text, nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    booking = relationship('Booking', back_populates='payments')
    confirmer = relationship('User', back_populates='confirmed_payments', foreign_keys=[confirmed_by])
