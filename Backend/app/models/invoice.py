from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Time
from sqlalchemy.orm import relationship

from ..database.base import Base


class Invoice(Base):
    __tablename__ = 'invoices'

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(40), nullable=False, unique=True, index=True)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete='RESTRICT'), nullable=False, unique=True, index=True)
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    booking_code = Column(String(24), nullable=False)
    customer_name = Column(String(120), nullable=False)
    customer_email = Column(String(255), nullable=False)
    facility_name = Column(String(160), nullable=False)
    field_name = Column(String(120), nullable=False)
    booking_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    court_amount = Column(Numeric(12, 2), nullable=False, default=0)
    service_amount = Column(Numeric(12, 2), nullable=False, default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    deposit_amount = Column(Numeric(12, 2), nullable=False)
    remaining_payment_amount = Column(Numeric(12, 2), nullable=False)
    refund_amount = Column(Numeric(12, 2), nullable=False, default=0)
    net_received_amount = Column(Numeric(12, 2), nullable=False)
    payment_methods = Column(String(255), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    booking = relationship('Booking', back_populates='invoice')
