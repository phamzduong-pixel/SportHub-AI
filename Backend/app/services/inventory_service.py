from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models.facility import Facility, FacilityStatus
from ..models.field import Booking
from ..models.product import BookingProductItem, FacilityProduct, ProductStatus, ProductStockMovement, ProductType
from ..models.user import User
from .audit_service import record_audit
from .product_service import ProductService


class InventoryService:
    def __init__(self, db):
        self.db = db

    def adjust(self, product_id: int, payload, user: User):
        product = self._owned_product(product_id, user, lock=True)
        if product.status == ProductStatus.ARCHIVED.value:
            raise HTTPException(status_code=409, detail='Sản phẩm đã lưu trữ không thể điều chỉnh tồn kho')
        before_stock, before_reserved = int(product.stock_quantity or 0), int(product.reserved_quantity or 0)
        before_tracking = bool(product.track_inventory)
        next_stock = payload.stock_quantity if payload.stock_quantity is not None else before_stock + (payload.quantity_change or 0)
        next_tracking = product.track_inventory if payload.track_inventory is None else payload.track_inventory
        if next_stock < 0:
            raise HTTPException(status_code=409, detail='Tồn kho không được âm')
        if next_stock < before_reserved:
            raise HTTPException(status_code=409, detail='Tồn kho không thể thấp hơn số lượng đang được giữ')
        if not next_tracking and before_reserved > 0:
            raise HTTPException(status_code=409, detail='Không thể tắt quản lý tồn kho khi còn số lượng đang được giữ')
        product.stock_quantity = next_stock
        product.track_inventory = next_tracking
        delta = next_stock - before_stock
        movement_type = 'IMPORT' if delta > 0 else 'ADJUSTMENT'
        if delta or next_tracking != before_tracking:
            self._movement(product, movement_type, delta, 0, before_stock, before_reserved, user.id, None, payload.note)
        elif payload.track_inventory is not None:
            self._movement(product, 'ADJUSTMENT', 0, 0, before_stock, before_reserved, user.id, None, payload.note)
        record_audit(self.db, user, 'facility_product', product.id, 'inventory_adjusted', {
            'stock_before': before_stock, 'stock_after': next_stock, 'track_inventory': next_tracking,
        })
        self.db.commit()
        return ProductService(self.db).response(self._owned_product(product.id, user))

    def history(self, product_id: int, user: User):
        self._owned_product(product_id, user)
        return list(self.db.scalars(select(ProductStockMovement).where(
            ProductStockMovement.product_id == product_id,
        ).order_by(ProductStockMovement.created_at.desc(), ProductStockMovement.id.desc())).all())

    def public_available(self, facility_id: int, sport: str | None = None):
        query = select(FacilityProduct).join(Facility).options(
            selectinload(FacilityProduct.facility), selectinload(FacilityProduct.sport_links),
        ).where(
            FacilityProduct.facility_id == facility_id,
            FacilityProduct.status == ProductStatus.ACTIVE.value,
            Facility.status == FacilityStatus.APPROVED.value,
            Facility.is_active.is_(True),
        )
        products = self.db.scalars(query.order_by(FacilityProduct.name)).unique().all()
        if sport:
            sport_key = ProductService.sport_key(sport)
            products = [p for p in products if sport_key in {ProductService.sport_key(link.sport_name) for link in p.sport_links}]
        return [ProductService(self.db).response(item) for item in products if not item.track_inventory or item.available_quantity > 0]


    def owner_booking_options(self, booking: Booking, user: User):
        facility_id = booking.facility_id or booking.field.facility_id
        query = select(FacilityProduct).join(Facility).options(
            selectinload(FacilityProduct.facility), selectinload(FacilityProduct.sport_links),
        ).where(
            FacilityProduct.facility_id == facility_id,
            FacilityProduct.status == ProductStatus.ACTIVE.value,
            Facility.owner_id == user.id,
        ).order_by(FacilityProduct.name, FacilityProduct.id)
        booking_sport = ProductService.sport_key(booking.field.sport_type)
        products = self.db.scalars(query).unique().all()
        matched = [
            product for product in products
            if booking_sport in {ProductService.sport_key(link.sport_name) for link in product.sport_links}
        ]
        return [ProductService(self.db).response(product) for product in matched]

    def validate_selections(self, field, selections, *, lock: bool):
        if not selections:
            return [], 0
        requested = {int(item.product_id): int(item.quantity) for item in selections}
        query = select(FacilityProduct).options(
            selectinload(FacilityProduct.sport_links), selectinload(FacilityProduct.facility),
        ).where(FacilityProduct.id.in_(requested))
        if lock:
            query = query.with_for_update()
        products = {item.id: item for item in self.db.scalars(query).unique().all()}
        snapshots, total = [], 0
        for selection in selections:
            product = products.get(selection.product_id)
            quantity = int(selection.quantity)
            if product is None or product.facility_id != field.facility_id:
                raise HTTPException(status_code=409, detail='Sản phẩm không thuộc cơ sở đang đặt')
            if product.status != ProductStatus.ACTIVE.value:
                raise HTTPException(status_code=409, detail=f'Sản phẩm "{product.name}" đang ngừng cung cấp')
            supported = {ProductService.sport_key(item.sport_name) for item in product.sport_links}
            if ProductService.sport_key(field.sport_type) not in supported:
                raise HTTPException(status_code=409, detail=f'Sản phẩm "{product.name}" không áp dụng cho môn thể thao này')
            if product.track_inventory and product.available_quantity < quantity:
                raise HTTPException(status_code=409, detail=f'Sản phẩm "{product.name}" chỉ còn {product.available_quantity} {product.unit}')
            subtotal = product.price * quantity
            snapshots.append({
                'product_id': product.id, 'name': product.name, 'product_type': product.product_type,
                'unit': product.unit, 'quantity': quantity, 'unit_price': product.price,
                'subtotal': subtotal, 'track_inventory': bool(product.track_inventory),
            })
            total += subtotal
        return snapshots, total

    def validate_reschedule(self, field, booking_items):
        """Validate an existing reservation against the target schedule.

        Inventory already held by this booking must not be reserved a second
        time. The check therefore verifies ownership, sport compatibility and
        that the original hold still exists for tracked products.
        """
        for item in booking_items:
            product = self._product(item.product_id, lock=True)
            if product.facility_id != field.facility_id:
                raise HTTPException(status_code=409, detail=f'Sản phẩm "{item.product_name_snapshot}" không thuộc cơ sở mới')
            if product.status != ProductStatus.ACTIVE.value:
                raise HTTPException(status_code=409, detail=f'Sản phẩm "{item.product_name_snapshot}" đang ngừng cung cấp')
            supported = {ProductService.sport_key(link.sport_name) for link in product.sport_links}
            if ProductService.sport_key(field.sport_type) not in supported:
                raise HTTPException(status_code=409, detail=f'Sản phẩm "{item.product_name_snapshot}" không áp dụng cho môn thể thao của sân mới')
            if product.track_inventory and (
                item.inventory_status != 'RESERVED'
                or int(product.reserved_quantity or 0) < int(item.quantity or 0)
            ):
                raise HTTPException(status_code=409, detail=f'Số lượng giữ cho sản phẩm "{item.product_name_snapshot}" không còn hợp lệ')

    def reserve(self, item: BookingProductItem, actor_id: int | None = None):
        product = self._product(item.product_id, lock=True)
        if product.status != ProductStatus.ACTIVE.value:
            raise HTTPException(status_code=409, detail='Sản phẩm đang ngừng cung cấp')
        booking = self.db.get(Booking, item.booking_id)
        if booking is None or product.facility_id != (booking.facility_id or booking.field.facility_id):
            raise HTTPException(status_code=409, detail='Sản phẩm không thuộc cơ sở của booking')
        if not product.track_inventory:
            item.inventory_status = 'UNTRACKED'
            return
        quantity = int(item.quantity or 0)
        if quantity <= 0 or product.available_quantity < quantity:
            raise HTTPException(status_code=409, detail='Số lượng khả dụng không đủ')
        before_stock, before_reserved = product.stock_quantity, product.reserved_quantity
        product.reserved_quantity += quantity
        item.inventory_status = 'RESERVED'
        self._movement(product, 'RESERVE', 0, quantity, before_stock, before_reserved, actor_id, item.booking_id, 'Giữ cho booking')

    def fulfill(self, item: BookingProductItem, actor_id: int | None = None):
        if item.inventory_status != 'RESERVED':
            return
        product = self._product(item.product_id, lock=True)
        quantity = int(item.quantity)
        before_stock, before_reserved = product.stock_quantity, product.reserved_quantity
        if item.product_type_snapshot == ProductType.RENT.value:
            return
        product.reserved_quantity -= quantity
        product.stock_quantity -= quantity
        if product.stock_quantity < 0 or product.reserved_quantity < 0:
            raise HTTPException(status_code=409, detail='Tồn kho không hợp lệ')
        item.inventory_status = 'SOLD' if item.product_type_snapshot == ProductType.SELL.value else 'CONSUMED'
        self._movement(product, 'SALE', -quantity, -quantity, before_stock, before_reserved, actor_id, item.booking_id, 'Xuất theo booking')

    def release(self, item: BookingProductItem, actor_id: int | None = None, returned=False):
        if item.inventory_status != 'RESERVED':
            return
        product = self._product(item.product_id, lock=True)
        quantity = int(item.quantity)
        before_stock, before_reserved = product.stock_quantity, product.reserved_quantity
        product.reserved_quantity -= quantity
        if product.reserved_quantity < 0:
            raise HTTPException(status_code=409, detail='Số lượng giữ không hợp lệ')
        item.inventory_status = 'RETURNED' if returned else 'RELEASED'
        movement = 'RETURN' if returned and item.product_type_snapshot == ProductType.RENT.value else 'RELEASE'
        self._movement(product, movement, 0, -quantity, before_stock, before_reserved, actor_id, item.booking_id, 'Trả lại khả dụng' if returned else 'Giải phóng booking')

    def _movement(self, product, movement_type, stock_delta, reserved_delta, stock_before, reserved_before, actor_id, booking_id, note):
        self.db.add(ProductStockMovement(
            product_id=product.id, booking_id=booking_id, actor_id=actor_id, movement_type=movement_type,
            stock_delta=stock_delta, reserved_delta=reserved_delta,
            stock_before=stock_before, stock_after=product.stock_quantity,
            reserved_before=reserved_before, reserved_after=product.reserved_quantity, note=note,
        ))

    def _product(self, product_id: int, lock=False):
        query = select(FacilityProduct).where(FacilityProduct.id == product_id)
        if lock:
            query = query.with_for_update()
        product = self.db.scalar(query)
        if product is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy sản phẩm')
        return product

    def _owned_product(self, product_id: int, user: User, lock=False):
        query = select(FacilityProduct).join(Facility).options(
            selectinload(FacilityProduct.facility), selectinload(FacilityProduct.sport_links),
        ).where(FacilityProduct.id == product_id, Facility.owner_id == user.id)
        if lock:
            query = query.with_for_update()
        product = self.db.scalar(query)
        if product is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy sản phẩm')
        return product
