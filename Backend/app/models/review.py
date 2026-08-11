from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from ..database.base import Base
class Review(Base):
    __tablename__ = 'reviews'
    __table_args__ = (UniqueConstraint('booking_id', name='uq_review_booking'),)
    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete='RESTRICT'), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    field_id = Column(Integer, ForeignKey('fields.id', ondelete='CASCADE'), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=False)
    owner_reply = Column(Text, nullable=True)
    replied_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    booking = relationship('Booking', back_populates='review')
    customer = relationship('User', foreign_keys=[customer_id])
    field = relationship('Field')
    replier = relationship('User', foreign_keys=[replied_by])
