from datetime import datetime, timezone

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from ..database.base import Base


class OwnerApplicationStatus(str, Enum):
    DRAFT = 'DRAFT'
    PENDING_REVIEW = 'PENDING_REVIEW'
    NEED_MORE_INFO = 'NEED_MORE_INFO'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    WITHDRAWN = 'WITHDRAWN'


class OwnerApplication(Base):
    __tablename__ = 'owner_applications'
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=OwnerApplicationStatus.DRAFT.value, index=True)
    representative = Column(JSON, nullable=False, default=dict)
    venue = Column(JSON, nullable=False, default=dict)
    legal_confirmed = Column(Boolean, nullable=False, default=False)
    rejection_reason = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    document_path = Column(String(500), nullable=True)
    document_mime = Column(String(50), nullable=True)
    document_original_name = Column(String(255), nullable=True)
    document_size = Column(Integer, nullable=True)
    document_uploaded_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    withdrawn_at = Column(DateTime(timezone=True), nullable=True)
    withdraw_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    customer = relationship('User', foreign_keys=[customer_id])
    reviewer = relationship('User', foreign_keys=[reviewed_by])
