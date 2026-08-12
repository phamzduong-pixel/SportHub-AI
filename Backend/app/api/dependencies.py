from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from ..core.security import decode_access_token
from ..database.session import get_db
from ..models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login', auto_error=False)


def _resolve_user(token: str | None, db: Session) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Token không hợp lệ hoặc đã hết hạn',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    if not token:
        raise credentials_error
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get('sub', ''))
    except (JWTError, TypeError, ValueError):
        raise credentials_error
    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    if not user.is_active:
        raise HTTPException(status_code=403, detail='Tài khoản đã bị khóa')
    if user.role not in {'CUSTOMER', 'OWNER', 'SYSTEM_ADMIN'}:
        raise HTTPException(status_code=403, detail='Vai trò tài khoản không còn được hỗ trợ')
    return user


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return _resolve_user(token, db)


def get_optional_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User | None:
    return None if not token else _resolve_user(token, db)


def require_owner(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != 'OWNER':
        raise HTTPException(status_code=403, detail='Chỉ OWNER được thực hiện thao tác này')
    return current_user


def require_system_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != 'SYSTEM_ADMIN':
        raise HTTPException(status_code=403, detail='Chỉ SYSTEM_ADMIN được thực hiện thao tác này')
    return current_user


def get_field_viewer(current_user: User | None = Depends(get_optional_current_user)) -> User | None:
    return current_user
