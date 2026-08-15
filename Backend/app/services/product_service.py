import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from ..models.facility import Facility
from ..models.product import BookingProductItem, FacilityProduct, ProductCatalogItem, ProductSport, ProductStatus, ProductStockMovement
from ..models.user import User
from .audit_service import record_audit



class ProductService:
    def __init__(self, db):
        self.db = db

    def list(self, user: User, *, facility_id=None, product_type=None, status=None, search=None, sport=None):
        query = select(FacilityProduct).join(Facility).options(
            selectinload(FacilityProduct.sport_links), selectinload(FacilityProduct.facility),
        ).where(Facility.owner_id == user.id)
        if facility_id is not None:
            query = query.where(FacilityProduct.facility_id == facility_id)
        if product_type is not None:
            query = query.where(FacilityProduct.product_type == product_type)
        if status is not None:
            query = query.where(FacilityProduct.status == status)
        if search:
            query = query.where(func.lower(FacilityProduct.name).contains(search.strip().lower()))
        items = self.db.scalars(query.order_by(FacilityProduct.created_at.desc(), FacilityProduct.id.desc())).unique().all()
        if sport:
            sport_key = ProductService.sport_key(sport)
            items = [item for item in items if any(
                ProductService.sport_key(link.sport_name) == sport_key for link in item.sport_links
            )]
        return [self.response(item) for item in items]

    def catalog(self, sport: str):
        normalized = ProductService.sport_key(sport)
        rows = self.db.scalars(select(ProductCatalogItem).where(
            ProductCatalogItem.is_active.is_(True),
        ).order_by(ProductCatalogItem.sort_order, ProductCatalogItem.id)).all()
        seen, result = set(), []
        for item in rows:
            is_common = ProductService.sport_key(item.sport_name) == ProductService.sport_key('Dùng chung')
            if not is_common and ProductService.sport_key(item.sport_name) != normalized:
                continue
            duplicate_key = (item.name.casefold(), item.product_type)
            if duplicate_key in seen:
                continue
            seen.add(duplicate_key)
            result.append({
                'key': item.catalog_key, 'name': item.name, 'product_type': item.product_type,
                'unit': item.unit, 'track_inventory': bool(item.track_inventory),
                'sport': 'Dùng chung' if is_common else sport.strip(),
            })
        return result

    @staticmethod
    def sport_key(value: str):
        normalized = unicodedata.normalize('NFD', value.strip().casefold())
        plain = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn').replace('đ', 'd')
        plain = ' '.join(plain.split())
        aliases = {
            'badminton': 'cau long',
            'football': 'bong da', 'soccer': 'bong da', 'bong da mini': 'bong da',
            'futsal': 'bong da',
            'basketball': 'bong ro', 'volleyball': 'bong chuyen',
            'table tennis': 'bong ban', 'ping pong': 'bong ban',
        }
        return aliases.get(plain, plain)

    def create(self, data: dict, user: User):
        sports = data.pop('sports')
        self._owned_facility(data['facility_id'], user)
        product = FacilityProduct(**data)
        product.sport_links = [ProductSport(sport_name=name) for name in sports]
        self.db.add(product); self.db.flush()
        if product.track_inventory and product.stock_quantity > 0:
            self.db.add(ProductStockMovement(
                product_id=product.id, actor_id=user.id, movement_type='IMPORT',
                stock_delta=product.stock_quantity, reserved_delta=0,
                stock_before=0, stock_after=product.stock_quantity,
                reserved_before=0, reserved_after=0, note='Tồn kho ban đầu',
            ))
        record_audit(self.db, user, 'facility_product', product.id, 'product_created', self._audit(product, sports))
        self.db.commit()
        return self.response(self._owned_product(product.id, user))

    def create_from_catalog(self, payload, user: User):
        facility = self._owned_facility(payload.facility_id, user)
        requested = set(payload.catalog_keys)
        catalog_items = list(self.db.scalars(select(ProductCatalogItem).where(
            ProductCatalogItem.catalog_key.in_(requested), ProductCatalogItem.is_active.is_(True),
        )).all())
        if {item.catalog_key for item in catalog_items} != requested:
            raise HTTPException(status_code=422, detail='Catalog được chọn không hợp lệ hoặc đã ngừng sử dụng')
        requested_sport = ProductService.sport_key(payload.sport)
        common_sport = ProductService.sport_key('Dùng chung')
        facility_sports = {ProductService.sport_key(name) for name in (facility.sports or [])}
        for field in getattr(facility, 'fields', []):
            if field.sport_type:
                facility_sports.add(ProductService.sport_key(field.sport_type))
        if requested_sport != common_sport and requested_sport not in facility_sports:
            raise HTTPException(status_code=422, detail='Cơ sở không hỗ trợ môn thể thao đã chọn')
        if any(ProductService.sport_key(item.sport_name) not in (requested_sport, common_sport) for item in catalog_items):
            raise HTTPException(status_code=422, detail='Catalog không phù hợp môn thể thao đã chọn')

        existing = list(self.db.scalars(select(FacilityProduct).options(
            selectinload(FacilityProduct.facility), selectinload(FacilityProduct.sport_links),
        ).where(FacilityProduct.facility_id == facility.id)).unique().all())
        existing_by_key = {(item.name.strip().casefold(), item.product_type): item for item in existing}
        selected_products = []
        for item in catalog_items:
            duplicate_key = (item.name.strip().casefold(), item.product_type)
            product = existing_by_key.get(duplicate_key)
            if ProductService.sport_key(item.sport_name) == common_sport:
                # Dùng chung: assign to all sports the facility actually supports
                sports_set = set(facility.sports or [])
                for f in getattr(facility, 'fields', []):
                    if f.sport_type:
                        sports_set.add(f.sport_type)
                sports = list(sports_set)
            else:
                sports = [payload.sport.strip()]
            if not sports:
                sports = [payload.sport.strip()]
            if product is None:
                product = FacilityProduct(
                    facility_id=facility.id, name=item.name, product_type=item.product_type,
                    description=None, image_url=None, price=0, unit=item.unit,
                    status=ProductStatus.INACTIVE.value, stock_quantity=0, reserved_quantity=0,
                    track_inventory=bool(item.track_inventory),
                )
                product.sport_links = [ProductSport(sport_name=name) for name in sports]
                self.db.add(product)
                self.db.flush()
                existing_by_key[duplicate_key] = product
                record_audit(self.db, user, 'facility_product', product.id, 'product_created_from_catalog', {
                    'catalog_key': item.catalog_key, 'facility_id': facility.id, 'sports': sports,
                })
            elif product.status == ProductStatus.ARCHIVED.value:
                product.status = ProductStatus.INACTIVE.value
                record_audit(self.db, user, 'facility_product', product.id, 'product_restored_from_catalog', {
                    'catalog_key': item.catalog_key,
                })
            existing_sports = {ProductService.sport_key(link.sport_name) for link in product.sport_links}
            added_sports = [name for name in sports if ProductService.sport_key(name) not in existing_sports]
            if added_sports:
                product.sport_links.extend(ProductSport(sport_name=name) for name in added_sports)
                record_audit(self.db, user, 'facility_product', product.id, 'product_catalog_sports_extended', {
                    'catalog_key': item.catalog_key, 'sports': added_sports,
                })
            selected_products.append(product)
        self.db.commit()
        return [self.response(self._owned_product(product.id, user)) for product in selected_products]

    def update(self, product_id: int, data: dict, user: User):
        product = self._owned_product(product_id, user)
        if product.status == ProductStatus.ARCHIVED.value:
            raise HTTPException(status_code=409, detail='Sản phẩm đã lưu trữ và không thể chỉnh sửa')
        sports = data.pop('sports')
        self._owned_facility(data['facility_id'], user)
        for key, value in data.items():
            setattr(product, key, value)
        product.sport_links.clear()
        self.db.flush()
        product.sport_links.extend(ProductSport(sport_name=name) for name in sports)
        record_audit(self.db, user, 'facility_product', product.id, 'product_updated', self._audit(product, sports))
        self.db.commit()
        return self.response(self._owned_product(product.id, user))

    def update_status(self, product_id: int, is_active: bool, user: User):
        product = self._owned_product(product_id, user)
        if product.status == ProductStatus.ARCHIVED.value:
            raise HTTPException(status_code=409, detail='Sản phẩm đã lưu trữ không thể bật lại')
        product.status = ProductStatus.ACTIVE.value if is_active else ProductStatus.INACTIVE.value
        record_audit(self.db, user, 'facility_product', product.id, 'product_status_updated', {'status': product.status})
        self.db.commit()
        return self.response(self._owned_product(product.id, user))

    def update_price(self, product_id: int, price: float, user: User):
        product = self._owned_product(product_id, user)
        if product.status == ProductStatus.ARCHIVED.value:
            raise HTTPException(status_code=409, detail='Sản phẩm đã lưu trữ và không thể chỉnh giá')
        old_price = float(product.price)
        product.price = price
        record_audit(self.db, user, 'facility_product', product.id, 'product_price_updated', {'from': old_price, 'to': price})
        self.db.commit()
        return self.response(self._owned_product(product.id, user))

    def unassign_sport(self, product_id: int, sport: str, user: User):
        product = self._owned_product(product_id, user)
        if product.status == ProductStatus.ARCHIVED.value:
            raise HTTPException(status_code=409, detail='Sản phẩm đã được bỏ khỏi cấu hình')
        sport_key = ProductService.sport_key(sport)
        removed = [link for link in product.sport_links if ProductService.sport_key(link.sport_name) == sport_key]
        if not removed:
            raise HTTPException(status_code=404, detail='Dịch vụ không áp dụng cho môn thể thao này')
        for link in removed:
            product.sport_links.remove(link)
        self.db.flush()
        remaining_sports = [link.sport_name for link in product.sport_links]
        if not remaining_sports:
            product.status = ProductStatus.ARCHIVED.value
        record_audit(self.db, user, 'facility_product', product.id, 'product_sport_unassigned', {
            'sport': sport, 'remaining_sports': remaining_sports, 'status': product.status,
        })
        self.db.commit()
        return self.response(self._owned_product(product.id, user))

    def delete(self, product_id: int, user: User):
        product = self._owned_product(product_id, user)
        product.status = ProductStatus.ARCHIVED.value
        record_audit(self.db, user, 'facility_product', product.id, 'product_archived', {
            'name': product.name, 'has_booking_history': self._has_booking_history(product.id),
        })
        self.db.commit()
        return 'archived', self.response(self._owned_product(product.id, user))

    def response(self, product: FacilityProduct):
        return {
            'id': product.id, 'facility_id': product.facility_id, 'facility_name': product.facility.name,
            'name': product.name, 'product_type': product.product_type, 'description': product.description,
            'image_url': product.image_url, 'price': float(product.price), 'unit': product.unit,
            'status': product.status, 'sports': [item.sport_name for item in product.sport_links],
            'stock_quantity': int(product.stock_quantity or 0),
            'reserved_quantity': int(product.reserved_quantity or 0),
            'available_quantity': product.available_quantity,
            'track_inventory': bool(product.track_inventory),
            'is_available': product.status == ProductStatus.ACTIVE.value and (
                not product.track_inventory or product.available_quantity > 0
            ),
            'has_booking_history': self._has_booking_history(product.id),
            'created_at': product.created_at, 'updated_at': product.updated_at,
        }

    def _owned_facility(self, facility_id: int, user: User):
        facility = self.db.scalar(select(Facility).options(selectinload(Facility.fields)).where(Facility.id == facility_id, Facility.owner_id == user.id))
        if facility is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy cơ sở')
        return facility

    def _owned_product(self, product_id: int, user: User):
        product = self.db.scalar(select(FacilityProduct).join(Facility).options(
            selectinload(FacilityProduct.sport_links), selectinload(FacilityProduct.facility),
        ).where(FacilityProduct.id == product_id, Facility.owner_id == user.id))
        if product is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy sản phẩm hoặc dịch vụ')
        return product

    def _has_booking_history(self, product_id: int):
        return self.db.scalar(select(BookingProductItem.id).where(BookingProductItem.product_id == product_id).limit(1)) is not None

    @staticmethod
    def _audit(product, sports):
        return {'facility_id': product.facility_id, 'name': product.name, 'type': product.product_type,
                'price': float(product.price), 'unit': product.unit, 'status': product.status, 'sports': sports,
                'stock_quantity': int(product.stock_quantity or 0), 'track_inventory': bool(product.track_inventory)}
