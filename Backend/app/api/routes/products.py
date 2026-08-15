from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.user import User
from ...schemas.product import (
    InventoryAdjustment, ProductCatalogImport, ProductCatalogSuggestion, ProductCreate, ProductDeleteResponse, ProductPriceUpdate, ProductResponse,
    ProductStatus, ProductStatusUpdate, ProductType, ProductUpdate, StockMovementResponse,
)
from ...services.inventory_service import InventoryService
from ...services.product_service import ProductService
from ..dependencies import require_owner


router = APIRouter(prefix='/facility-products', tags=['facility-products'])


def get_service(db: Session = Depends(get_db)):
    return ProductService(db)


def get_inventory_service(db: Session = Depends(get_db)):
    return InventoryService(db)


@router.get('/catalog', response_model=list[ProductCatalogSuggestion])
def product_catalog(
    sport: str = Query(min_length=2, max_length=80), owner: User = Depends(require_owner),
    service: ProductService = Depends(get_service),
):
    return service.catalog(sport)


@router.post('/from-catalog', response_model=list[ProductResponse], status_code=201)
def create_products_from_catalog(
    payload: ProductCatalogImport, owner: User = Depends(require_owner),
    service: ProductService = Depends(get_service),
):
    return service.create_from_catalog(payload, owner)


@router.get('/available', response_model=list[ProductResponse])
def available_products(
    facility_id: int = Query(gt=0), sport: str | None = Query(default=None, max_length=80),
    service: InventoryService = Depends(get_inventory_service),
):
    return service.public_available(facility_id, sport)


@router.get('', response_model=list[ProductResponse])
def list_products(
    facility_id: int | None = Query(default=None, gt=0),
    product_type: ProductType | None = None,
    status: ProductStatus | None = None,
    search: str | None = Query(default=None, max_length=160),
    sport: str | None = Query(default=None, min_length=2, max_length=80),
    owner: User = Depends(require_owner), service: ProductService = Depends(get_service),
):
    return service.list(owner, facility_id=facility_id, product_type=product_type.value if product_type else None,
                        status=status.value if status else None, search=search, sport=sport)


@router.post('', response_model=ProductResponse, status_code=201)
def create_product(payload: ProductCreate, owner: User = Depends(require_owner), service: ProductService = Depends(get_service)):
    return service.create(payload.model_dump(mode='json'), owner)


@router.put('/{product_id}', response_model=ProductResponse)
def update_product(product_id: int, payload: ProductUpdate, owner: User = Depends(require_owner), service: ProductService = Depends(get_service)):
    return service.update(product_id, payload.model_dump(mode='json'), owner)


@router.patch('/{product_id}/status', response_model=ProductResponse)
def update_product_status(product_id: int, payload: ProductStatusUpdate, owner: User = Depends(require_owner), service: ProductService = Depends(get_service)):
    return service.update_status(product_id, payload.is_active, owner)


@router.patch('/{product_id}/price', response_model=ProductResponse)
def update_product_price(product_id: int, payload: ProductPriceUpdate, owner: User = Depends(require_owner), service: ProductService = Depends(get_service)):
    return service.update_price(product_id, payload.price, owner)


@router.delete('/{product_id}/sports', response_model=ProductResponse)
def unassign_product_sport(
    product_id: int, sport: str = Query(min_length=2, max_length=80),
    owner: User = Depends(require_owner), service: ProductService = Depends(get_service),
):
    return service.unassign_sport(product_id, sport, owner)


@router.patch('/{product_id}/inventory', response_model=ProductResponse)
def adjust_inventory(
    product_id: int, payload: InventoryAdjustment, owner: User = Depends(require_owner),
    service: InventoryService = Depends(get_inventory_service),
):
    return service.adjust(product_id, payload, owner)


@router.get('/{product_id}/inventory-history', response_model=list[StockMovementResponse])
def inventory_history(
    product_id: int, owner: User = Depends(require_owner),
    service: InventoryService = Depends(get_inventory_service),
):
    return service.history(product_id, owner)


@router.delete('/{product_id}', response_model=ProductDeleteResponse)
def delete_product(product_id: int, owner: User = Depends(require_owner), service: ProductService = Depends(get_service)):
    action, product = service.delete(product_id, owner)
    return {
        'action': action, 'product': product,
        'message': 'Đã xóa mềm sản phẩm; dữ liệu booking và hóa đơn cũ vẫn được giữ nguyên.',
    }
