from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RequestModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: str
    phone: str | None
    avatar_url: str | None
    role: str
    roles: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RegisterRequest(RequestModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str = Field(min_length=10, max_length=10, pattern=r'^0[0-9]{9}$')
    password: str = Field(min_length=8, max_length=72)

    @field_validator('full_name')
    @classmethod
    def validate_name(cls, value: str):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Họ tên phải có ít nhất 2 ký tự')
        return value

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str):
        value = value.strip().lower()
        if len(value) > 255 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Email không hợp lệ')
        return value

    @field_validator('phone', mode='before')
    @classmethod
    def validate_vietnamese_phone(cls, value):
        if not isinstance(value, str):
            raise ValueError('Số điện thoại phải gồm đúng 10 chữ số và bắt đầu bằng 0.')
        return value.strip()

    @field_validator('password')
    @classmethod
    def validate_password_bytes(cls, value: str):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('Mật khẩu không được vượt quá 72 byte')
        return value


class LoginRequest(RequestModel):
    email: str
    password: str = Field(min_length=1, max_length=72)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str):
        return RegisterRequest.validate_email(value)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    user: UserResponse


class RefreshTokenRequest(RequestModel):
    refresh_token: str = Field(min_length=20, max_length=2000)


class ProfileUpdateRequest(RequestModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=8, max_length=20, pattern=r'^\+?[0-9 ]+$')

    @field_validator('full_name')
    @classmethod
    def validate_name(cls, value: str | None):
        return value if value is None else RegisterRequest.validate_name(value)

class ChangePasswordRequest(RequestModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator('new_password')
    @classmethod
    def validate_password_bytes(cls, value: str):
        return RegisterRequest.validate_password_bytes(value)


class StatusUpdateRequest(RequestModel):
    is_active: bool


class MessageResponse(BaseModel):
    message: str
