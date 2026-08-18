from pydantic import BaseModel, Field

from .user import RequestModel, UserResponse


class AdminStatusUpdate(RequestModel):
    is_active: bool


class AdminUserList(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int


class AdminFacilityItem(BaseModel):
    id: int
    owner_id: int
    owner_name: str
    owner_email: str
    name: str
    location: str
    is_active: bool
    field_count: int = Field(ge=0)


class AdminFacilityList(BaseModel):
    items: list[AdminFacilityItem]
    total: int
    page: int
    page_size: int


class AdminSummary(BaseModel):
    total_users: int
    customers: int
    owners: int
    system_admins: int
    active_users: int
    facilities: int
    active_facilities: int
    fields: int
    bookings: int
    pending_applications: int
    pending_facilities: int


class AdminOwnerItem(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None
    avatar_url: str | None
    is_active: bool
    approved_at: str | None
    facility_count: int = Field(ge=0)
    field_count: int = Field(ge=0)


class AdminOwnerList(BaseModel):
    items: list[AdminOwnerItem]
    total: int
    page: int
    page_size: int


class AdminUserCreate(RequestModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str = Field(min_length=10, max_length=10, pattern=r'^0[0-9]{9}$')
    password: str = Field(min_length=8, max_length=72)
    role: str = Field(pattern='^(CUSTOMER|OWNER)$')

class AdminUserUpdate(RequestModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str = Field(min_length=10, max_length=10, pattern=r'^0[0-9]{9}$')
    role: str = Field(pattern='^(CUSTOMER|OWNER)$')
