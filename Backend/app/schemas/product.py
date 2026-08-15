from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .user import RequestModel


class ProductType(str, Enum):
    SELL = 'SELL'
    RENT = 'RENT'
    SERVICE = 'SERVICE'


class ProductStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'
    ARCHIVED = 'ARCHIVED'


class ProductBase(RequestModel):
    facility_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=160)
    product_type: ProductType
    description: str | None = Field(default=None, max_length=3000)
    image_url: str | None = Field(default=None, max_length=1000)
    price: float = Field(ge=0, le=1_000_000_000)
    unit: str = Field(min_length=1, max_length=50)
    sports: list[str] = Field(default_factory=list, max_length=30)

    @field_validator('name', 'unit')
    @classmethod
    def normalize_required_text(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError('Giá trị không được để trống')
        return value

    @field_validator('description', 'image_url')
    @classmethod
    def normalize_optional_text(cls, value: str | None):
        return value.strip() or None if value else None

    @field_validator('sports')
    @classmethod
    def normalize_sports(cls, values: list[str]):
        result = []
        for value in values:
            value = value.strip()
            if value and value.casefold() not in {item.casefold() for item in result}:
                result.append(value[:80])
        if not result:
            raise ValueError('Phải chọn ít nhất một môn thể thao áp dụng')
        return result


class ProductCreate(ProductBase):
    status: ProductStatus = ProductStatus.ACTIVE
    stock_quantity: int = Field(default=0, ge=0, le=1_000_000_000)
    track_inventory: bool | None = None

    @model_validator(mode='after')
    def inventory_default(self):
        if self.track_inventory is None:
            self.track_inventory = self.product_type != ProductType.SERVICE
        return self


class ProductUpdate(ProductBase):
    status: ProductStatus


class ProductStatusUpdate(RequestModel):
    is_active: bool


class ProductPriceUpdate(RequestModel):
    price: float = Field(ge=0, le=1_000_000_000)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    facility_id: int
    facility_name: str
    name: str
    product_type: ProductType
    description: str | None
    image_url: str | None
    price: float
    unit: str
    status: ProductStatus
    stock_quantity: int
    reserved_quantity: int
    available_quantity: int
    track_inventory: bool
    is_available: bool
    sports: list[str]
    has_booking_history: bool
    created_at: datetime
    updated_at: datetime


class ProductDeleteResponse(BaseModel):
    message: str
    action: str
    product: ProductResponse | None = None


class ProductCatalogSuggestion(BaseModel):
    key: str
    name: str
    product_type: ProductType
    unit: str
    track_inventory: bool
    sport: str


class ProductCatalogImport(RequestModel):
    facility_id: int = Field(gt=0)
    sport: str = Field(min_length=2, max_length=80)
    catalog_keys: list[str] = Field(min_length=1, max_length=50)

    @field_validator('catalog_keys')
    @classmethod
    def unique_catalog_keys(cls, values: list[str]):
        result = []
        for value in values:
            key = value.strip()
            if key and key not in result:
                result.append(key)
        if not result:
            raise ValueError('Phải chọn ít nhất một mục catalog')
        return result


class InventoryAdjustment(RequestModel):
    stock_quantity: int | None = Field(default=None, ge=0, le=1_000_000_000)
    quantity_change: int | None = Field(default=None, ge=-1_000_000_000, le=1_000_000_000)
    track_inventory: bool | None = None
    note: str = Field(min_length=2, max_length=500)

    @model_validator(mode='after')
    def one_quantity_mode(self):
        if self.stock_quantity is not None and self.quantity_change is not None:
            raise ValueError('Chỉ dùng stock_quantity hoặc quantity_change')
        if self.stock_quantity is None and self.quantity_change is None and self.track_inventory is None:
            raise ValueError('Không có thay đổi tồn kho')
        return self


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    booking_id: int | None
    actor_id: int | None
    movement_type: str
    stock_delta: int
    reserved_delta: int
    stock_before: int
    stock_after: int
    reserved_before: int
    reserved_after: int
    note: str | None
    created_at: datetime
