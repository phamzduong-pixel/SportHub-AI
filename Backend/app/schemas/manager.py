from pydantic import Field, field_validator

from .user import RegisterRequest, RequestModel

MANAGEMENT_PERMISSIONS = {
    'bookings.manage', 'customers.view', 'fields.create', 'fields.update', 'fields.delete',
    'maintenance.view', 'maintenance.manage', 'payments.manage', 'reports.view',
    'time_slots.manage', 'ai.view',
}


class ManagerCreate(RequestModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str | None = Field(default=None, min_length=8, max_length=20, pattern=r'^\+?[0-9 ]+$')
    password: str = Field(min_length=8, max_length=72)
    permissions: list[str] = Field(default_factory=list, max_length=30)

    @field_validator('full_name')
    @classmethod
    def name_valid(cls, value: str): return RegisterRequest.validate_name(value)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value: str): return RegisterRequest.validate_email(value)

    @field_validator('password')
    @classmethod
    def password_valid(cls, value: str): return RegisterRequest.validate_password_bytes(value)

    @field_validator('permissions')
    @classmethod
    def permissions_valid(cls, values: list[str]):
        normalized = list(dict.fromkeys(values))
        invalid = set(normalized) - MANAGEMENT_PERMISSIONS
        if invalid:
            raise ValueError(f'Quyền quản lý không hợp lệ: {", ".join(sorted(invalid))}')
        return normalized


class ManagerUpdate(RequestModel):
    permissions: list[str] | None = Field(default=None, max_length=30)
    is_active: bool | None = None

    @field_validator('permissions')
    @classmethod
    def permissions_valid(cls, values: list[str] | None):
        return values if values is None else ManagerCreate.permissions_valid(values)
