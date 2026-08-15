from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database.base import Base


class ProductType(str, Enum):
    SELL = 'SELL'
    RENT = 'RENT'
    SERVICE = 'SERVICE'


class ProductStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'
    ARCHIVED = 'ARCHIVED'


class ProductCatalogItem(Base):
    __tablename__ = 'product_catalog_items'

    id = Column(Integer, primary_key=True)
    catalog_key = Column(String(120), nullable=False, unique=True, index=True)
    sport_name = Column(String(80), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    product_type = Column(String(20), nullable=False)
    unit = Column(String(50), nullable=False)
    track_inventory = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FacilityProduct(Base):
    __tablename__ = 'facility_products'
    __table_args__ = (
        CheckConstraint('stock_quantity >= 0', name='ck_facility_product_stock_nonnegative'),
        CheckConstraint('reserved_quantity >= 0', name='ck_facility_product_reserved_nonnegative'),
        CheckConstraint('reserved_quantity <= stock_quantity', name='ck_facility_product_reserved_within_stock'),
    )

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey('facilities.id', ondelete='RESTRICT'), nullable=False, index=True)
    name = Column(String(160), nullable=False, index=True)
    product_type = Column(String(20), nullable=False, index=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(1000), nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    unit = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default=ProductStatus.ACTIVE.value, index=True)
    stock_quantity = Column(Integer, nullable=False, default=0)
    reserved_quantity = Column(Integer, nullable=False, default=0)
    track_inventory = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    facility = relationship('Facility')
    sport_links = relationship('ProductSport', back_populates='product', cascade='all, delete-orphan', lazy='selectin')
    booking_items = relationship('BookingProductItem', back_populates='product', passive_deletes=True)
    stock_movements = relationship('ProductStockMovement', back_populates='product', passive_deletes=True)

    @property
    def available_quantity(self):
        return max(0, int(self.stock_quantity or 0) - int(self.reserved_quantity or 0))


class ProductSport(Base):
    __tablename__ = 'facility_product_sports'
    __table_args__ = (UniqueConstraint('product_id', 'sport_name', name='uq_facility_product_sport'),)

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('facility_products.id', ondelete='CASCADE'), nullable=False, index=True)
    sport_name = Column(String(80), nullable=False, index=True)
    product = relationship('FacilityProduct', back_populates='sport_links')


class BookingProductItem(Base):
    __tablename__ = 'booking_product_items'

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('facility_products.id', ondelete='RESTRICT'), nullable=False, index=True)
    product_name_snapshot = Column(String(160), nullable=False)
    product_type_snapshot = Column(String(20), nullable=False)
    unit_snapshot = Column(String(50), nullable=False)
    unit_price_snapshot = Column(Numeric(12, 2), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    line_total = Column(Numeric(12, 2), nullable=False)
    inventory_status = Column(String(20), nullable=False, default='UNTRACKED', index=True)
    source = Column(String(32), nullable=False, default='CUSTOMER_BOOKING', index=True)
    added_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    booking = relationship('Booking', back_populates='product_items')
    product = relationship('FacilityProduct', back_populates='booking_items')
    added_by_user = relationship('User', foreign_keys=[added_by])


class ProductStockMovement(Base):
    __tablename__ = 'product_stock_movements'

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('facility_products.id', ondelete='RESTRICT'), nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete='SET NULL'), nullable=True, index=True)
    actor_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    movement_type = Column(String(24), nullable=False, index=True)
    stock_delta = Column(Integer, nullable=False, default=0)
    reserved_delta = Column(Integer, nullable=False, default=0)
    stock_before = Column(Integer, nullable=False)
    stock_after = Column(Integer, nullable=False)
    reserved_before = Column(Integer, nullable=False)
    reserved_after = Column(Integer, nullable=False)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    product = relationship('FacilityProduct', back_populates='stock_movements')
    booking = relationship('Booking')
    actor = relationship('User')
