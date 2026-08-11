from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...core.security import get_password_hash
from ...database.session import get_db
from ...models.user import User, UserRole
from ...schemas.manager import ManagerCreate, ManagerUpdate
from ...schemas.user import UserResponse
from ..dependencies import require_owner
from .auth import user_response

router = APIRouter(prefix='/management/managers', tags=['owner-managers'])


@router.get('', response_model=list[UserResponse])
def list_managers(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    items = db.scalars(select(User).where(
        User.role == UserRole.MANAGER.value, User.owner_id == owner.id,
    ).order_by(User.created_at.desc(), User.id.desc())).all()
    return [user_response(item) for item in items]


@router.post('', response_model=UserResponse, status_code=201)
def create_manager(payload: ManagerCreate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    identity_filters = [User.email == payload.email]
    if payload.phone:
        identity_filters.append(User.phone == payload.phone)
    duplicate = db.scalar(select(User).where(or_(*identity_filters)))
    if duplicate:
        raise HTTPException(status_code=409, detail='Email hoặc số điện thoại đã được sử dụng')
    manager = User(
        full_name=payload.full_name, email=payload.email, phone=payload.phone,
        hashed_password=get_password_hash(payload.password), role=UserRole.MANAGER.value,
        owner_id=owner.id, management_permissions=payload.permissions, is_active=True,
    )
    db.add(manager); db.commit(); db.refresh(manager)
    return user_response(manager)


@router.patch('/{manager_id}', response_model=UserResponse)
def update_manager(manager_id: int, payload: ManagerUpdate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    manager = db.scalar(select(User).where(
        User.id == manager_id, User.role == UserRole.MANAGER.value, User.owner_id == owner.id,
    ))
    if manager is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy MANAGER thuộc OWNER này')
    if payload.permissions is not None:
        manager.management_permissions = payload.permissions
    if payload.is_active is not None:
        manager.is_active = payload.is_active
    db.commit(); db.refresh(manager)
    return user_response(manager)
