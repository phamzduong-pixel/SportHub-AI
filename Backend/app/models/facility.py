from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Time
from sqlalchemy.orm import relationship

from ..database.base import Base


def default_cancellation_rules():
    return [
        {'min_minutes_before': 360, 'refund_percent': 100},
        {'min_minutes_before': 0, 'refund_percent': 0},
    ]


class FacilityStatus(str, Enum):
    DRAFT = 'DRAFT'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    SUSPENDED = 'SUSPENDED'


class Facility(Base):
    __tablename__ = 'facilities'

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    name = Column(String(160), nullable=False, index=True)
    location = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    contact_phone = Column(String(20), nullable=True)
    contact_email = Column(String(255), nullable=True)
    city = Column(String(120), nullable=True)
    district = Column(String(120), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)
    sports = Column(JSON, nullable=False, default=list)
    amenities = Column(JSON, nullable=False, default=list)
    image_urls = Column(JSON, nullable=False, default=list)  # legacy public/demo images
    cancellation_rules = Column(JSON, nullable=False, default=default_cancellation_rules)
    free_cancellation_minutes = Column(Integer, nullable=False, default=360)
    legacy_field_id = Column(Integer, nullable=True, unique=True)
    status = Column(String(24), nullable=False, default=FacilityStatus.APPROVED.value, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship('User', foreign_keys=[owner_id])
    approver = relationship('User', foreign_keys=[approved_by])
    fields = relationship('Field', back_populates='facility')
    images = relationship('FacilityImage', back_populates='facility', cascade='all, delete-orphan')
    documents = relationship('FacilityDocument', back_populates='facility', cascade='all, delete-orphan')
    reviews = relationship('FacilityReviewEvent', back_populates='facility', cascade='all, delete-orphan')


class FacilityImage(Base):
    __tablename__ = 'facility_images'
    id = Column(Integer, primary_key=True)
    facility_id = Column(Integer, ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True)
    category = Column(String(30), nullable=False, default='ADDITIONAL')
    file_path = Column(String(500), nullable=False)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    facility = relationship('Facility', back_populates='images')


class FacilityDocument(Base):
    __tablename__ = 'facility_verification_documents'
    id = Column(Integer, primary_key=True)
    facility_id = Column(Integer, ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True)
    document_type = Column(String(50), nullable=False)
    document_name = Column(String(255), nullable=False)
    document_number = Column(String(100), nullable=True)
    issued_date = Column(Date, nullable=True)
    issued_by = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=False)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_sha256 = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    facility = relationship('Facility', back_populates='documents')


class FacilityReviewEvent(Base):
    __tablename__ = 'facility_review_events'
    id = Column(Integer, primary_key=True)
    facility_id = Column(Integer, ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(40), nullable=False)
    from_status = Column(String(24), nullable=True)
    to_status = Column(String(24), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    facility = relationship('Facility', back_populates='reviews')
    actor = relationship('User')
