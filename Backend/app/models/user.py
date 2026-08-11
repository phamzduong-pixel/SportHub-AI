from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database.base import Base

class UserRole(str, Enum):
    CUSTOMER = 'CUSTOMER'
    OWNER = 'OWNER'
    MANAGER = 'MANAGER'
    SYSTEM_ADMIN = 'SYSTEM_ADMIN'

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default=UserRole.CUSTOMER.value, index=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    management_permissions = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    bookings = relationship('Booking', back_populates='customer', passive_deletes=True, foreign_keys='Booking.customer_id')
    confirmed_payments = relationship('Payment', back_populates='confirmer', foreign_keys='Payment.confirmed_by', passive_deletes=True)
    favorite_fields = relationship('UserFavoriteField', cascade='all, delete-orphan', back_populates='user')
    owned_fields = relationship('Field', back_populates='owner', passive_deletes=True)
    owner = relationship('User', remote_side=[id], foreign_keys=[owner_id])

class UserFavoriteField(Base):
    __tablename__ = 'user_favorite_fields'
    __table_args__ = (UniqueConstraint('user_id', 'field_id', name='uq_user_favorite_field'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    field_id = Column(Integer, ForeignKey('fields.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    user = relationship('User', back_populates='favorite_fields')
    field = relationship('Field')
