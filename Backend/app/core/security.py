from datetime import datetime, timedelta, timezone
from typing import Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from .config import settings

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    issued_at = datetime.now(timezone.utc)
    if expires_delta:
        expire = issued_at + expires_delta
    else:
        expire = issued_at + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'iat': issued_at, 'exp': expire, 'type': 'access'})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    issued_at = datetime.now(timezone.utc)
    to_encode.update({'iat': issued_at, 'exp': issued_at + timedelta(days=7), 'type': 'refresh'})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_refresh_token(token: str) -> Any:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get('type') != 'refresh':
        raise JWTError('Token type không hợp lệ')
    return payload

def decode_access_token(token: str) -> Any:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get('type') != 'access':
            raise JWTError('Token type không hợp lệ')
        return payload
    except JWTError as e:
        raise e

def create_password_reset_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {'sub': email, 'exp': expire, 'iat': datetime.now(timezone.utc), 'type': 'password_reset'},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM,
    )

def verify_password_reset_token(token: str) -> str:
    """Decode a password-reset JWT and return the email. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get('type') != 'password_reset':
        raise JWTError('Token type không hợp lệ')
    email: str | None = payload.get('sub')
    if not email:
        raise JWTError('Token không chứa email')
    return email
