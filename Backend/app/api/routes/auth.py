from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from jose import JWTError
from sqlalchemy import or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...core.security import create_access_token, create_refresh_token, decode_refresh_token, get_password_hash, verify_password
from ...database.session import get_db
from ...models.owner_application import OwnerApplication, OwnerApplicationStatus
from ...models.user import User, UserRole
from ...schemas.owner_application import OwnerApplicationDraft, OwnerApplicationRequest, OwnerApplicationResponse, OwnerApplicationWithdraw
from ...schemas.user import ChangePasswordRequest, LoginRequest, MessageResponse, ProfileUpdateRequest, RefreshTokenRequest, RegisterRequest, TokenResponse, UserResponse
from ..dependencies import get_current_user
from ...services.audit_service import record_audit
from ...services.avatar_service import avatar_response, delete_local_avatar, store_avatar
from ...services.partner_document_service import delete_document, document_response, store_document

router = APIRouter(prefix='/auth', tags=['auth'])
logger = logging.getLogger(__name__)


def user_response(user: User) -> UserResponse:
    roles = ['CUSTOMER', 'OWNER'] if user.role == UserRole.OWNER.value else [user.role]
    return UserResponse(
        id=user.id, full_name=user.full_name, email=user.email, phone=user.phone,
        avatar_url=user.avatar_url, role=user.role, roles=roles, owner_id=user.owner_id,
        management_permissions=user.management_permissions or [], is_active=user.is_active,
        created_at=user.created_at, updated_at=user.updated_at,
    )


def application_response(item: OwnerApplication) -> OwnerApplicationResponse:
    return OwnerApplicationResponse(
        id=item.id, customer_id=item.customer_id, customer_name=item.customer.full_name,
        customer_email=item.customer.email, customer_phone=item.customer.phone,
        status=item.status, representative=item.representative,
        venue=item.venue, legal_confirmed=item.legal_confirmed,
        rejection_reason=item.rejection_reason, admin_note=item.admin_note,
        has_document=bool(item.document_path), document_file_name=item.document_original_name,
        document_mime=item.document_mime, document_size=item.document_size,
        document_uploaded_at=item.document_uploaded_at,
        submitted_at=item.submitted_at, reviewed_at=item.reviewed_at,
        withdrawn_at=item.withdrawn_at, withdraw_reason=item.withdraw_reason,
        reviewed_by=item.reviewed_by, reviewer_name=item.reviewer.full_name if item.reviewer else None,
        created_at=item.created_at, updated_at=item.updated_at,
    )


def _latest_application(db: Session, customer_id: int) -> OwnerApplication | None:
    return db.scalar(
        select(OwnerApplication).where(OwnerApplication.customer_id == customer_id)
        .order_by(OwnerApplication.created_at.desc(), OwnerApplication.id.desc()).limit(1)
    )


def _validate_application_data(payload: OwnerApplicationRequest):
    representative, venue = payload.representative.model_dump(), payload.venue.model_dump()
    required_rep = ('name', 'phone', 'email')
    required_venue = ('name', 'address', 'sports')
    missing = [key for key in required_rep if not representative.get(key)] + [key for key in required_venue if not venue.get(key)]
    if missing:
        raise HTTPException(status_code=422, detail=f'Hồ sơ còn thiếu thông tin bắt buộc: {", ".join(missing)}')
    if not isinstance(venue.get('sports'), list) or not venue['sports']:
        raise HTTPException(status_code=422, detail='Phải chọn ít nhất một môn thể thao dự kiến kinh doanh')


def ensure_unique(db: Session, email: str, phone: str | None, exclude_id: int | None = None):
    filters = [User.email == email.lower()]
    if phone:
        filters.append(User.phone == phone)
    query = select(User).where(or_(*filters))
    if exclude_id is not None:
        query = query.where(User.id != exclude_id)
    duplicate = db.scalar(query)
    if duplicate:
        if duplicate.email == email.lower():
            raise HTTPException(status_code=409, detail='Email đã được sử dụng.')
        raise HTTPException(status_code=409, detail='Số điện thoại đã được sử dụng.')


@router.post('/register', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    ensure_unique(db, payload.email, payload.phone)
    user = User(full_name=payload.full_name.strip(), email=payload.email.lower(), phone=payload.phone, hashed_password=get_password_hash(payload.password), role=UserRole.CUSTOMER.value)
    db.add(user); db.commit(); db.refresh(user)
    return user_response(user)


@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Email hoặc mật khẩu không đúng')
    if not user.is_active:
        raise HTTPException(status_code=403, detail='Tài khoản đã bị khóa')
    if user.role not in {role.value for role in UserRole}:
        raise HTTPException(status_code=403, detail='Vai trò tài khoản không còn được hỗ trợ')
    return TokenResponse(
        access_token=create_access_token({'sub': str(user.id), 'role': user.role}),
        refresh_token=create_refresh_token({'sub': str(user.id), 'role': user.role}),
        user=user_response(user),
    )


@router.post('/refresh', response_model=TokenResponse)
def refresh_session(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        claims = decode_refresh_token(payload.refresh_token)
        user_id = int(claims.get('sub', ''))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail='Refresh token không hợp lệ hoặc đã hết hạn')
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.role not in {role.value for role in UserRole}:
        raise HTTPException(status_code=401, detail='Tài khoản không còn hoạt động')
    return TokenResponse(
        access_token=create_access_token({'sub': str(user.id), 'role': user.role}),
        refresh_token=create_refresh_token({'sub': str(user.id), 'role': user.role}),
        user=user_response(user),
    )


@router.post('/logout', response_model=MessageResponse)
def logout():
    return {'message': 'Đăng xuất thành công; client đã xóa access/refresh token'}


@router.get('/me', response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return user_response(current_user)


@router.post('/request-owner', response_model=OwnerApplicationResponse)
def request_owner(payload: OwnerApplicationRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=409, detail='Chỉ CUSTOMER mới có thể gửi yêu cầu trở thành OWNER')
    if not payload.legal_confirmed:
        raise HTTPException(status_code=422, detail='Bạn phải xác nhận thông tin hồ sơ')
    item = _latest_application(db, current_user.id)
    if item is None or not item.document_path:
        raise HTTPException(status_code=422, detail='Bạn phải tải ảnh giấy tờ/CCCD trước khi gửi hồ sơ')
    if item.status in (OwnerApplicationStatus.PENDING_REVIEW.value, OwnerApplicationStatus.APPROVED.value):
        raise HTTPException(status_code=409, detail='Hồ sơ đang chờ xét duyệt hoặc đã được phê duyệt; không thể gửi trùng')
    if item.status == OwnerApplicationStatus.WITHDRAWN.value:
        raise HTTPException(status_code=409, detail='Hồ sơ đã rút không thể gửi lại; hãy tạo hồ sơ đăng ký mới')
    item.status = OwnerApplicationStatus.PENDING_REVIEW.value
    item.representative = payload.representative.model_dump(); item.venue = payload.venue.model_dump()
    item.legal_confirmed = True; item.rejection_reason = None; item.admin_note = None
    item.reviewed_by = None; item.reviewed_at = None; item.withdrawn_at = None; item.withdraw_reason = None
    item.submitted_at = datetime.now(timezone.utc)
    try:
        db.flush()
        record_audit(db, current_user, 'owner_application', item.id, 'partner_application_submitted', {'status': item.status})
        db.commit(); db.refresh(item)
    except SQLAlchemyError:
        db.rollback()
        logger.exception('Database error while customer_id=%s submitted owner application id=%s', current_user.id, item.id)
        raise HTTPException(status_code=500, detail='Không thể lưu hồ sơ do lỗi hệ thống. Vui lòng thử lại sau.')
    return application_response(item)


@router.put('/owner-application', response_model=OwnerApplicationResponse)
def save_owner_application(payload: OwnerApplicationDraft, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=409, detail='Chỉ CUSTOMER được tạo hồ sơ đối tác')
    item = _latest_application(db, current_user.id)
    if item is None:
        item = OwnerApplication(customer_id=current_user.id, status=OwnerApplicationStatus.DRAFT.value, submitted_at=datetime.now(timezone.utc))
        db.add(item)
    elif item.status not in (OwnerApplicationStatus.DRAFT.value, OwnerApplicationStatus.NEED_MORE_INFO.value, OwnerApplicationStatus.REJECTED.value):
        raise HTTPException(status_code=409, detail='Trạng thái hồ sơ hiện tại không cho phép chỉnh sửa')
    item.representative = payload.representative; item.venue = payload.venue; item.legal_confirmed = payload.legal_confirmed
    db.commit(); db.refresh(item); return application_response(item)


@router.post('/owner-application/submit', response_model=OwnerApplicationResponse)
def submit_owner_application(payload: OwnerApplicationRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _validate_application_data(payload)
    return request_owner(payload, current_user, db)


@router.get('/owner-application', response_model=OwnerApplicationResponse)
def get_owner_application(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _latest_application(db, current_user.id)
    if item is None:
        raise HTTPException(status_code=404, detail='Chưa có hồ sơ đăng ký OWNER')
    return application_response(item)


@router.post('/owner-application/{application_id}/withdraw', response_model=OwnerApplicationResponse)
def withdraw_owner_application(
    application_id: int, payload: OwnerApplicationWithdraw,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if current_user.role != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail='Chỉ CUSTOMER được rút hồ sơ đăng ký đối tác')
    reason = (payload.reason or '').strip() or None
    withdrawn_at = datetime.now(timezone.utc)
    result = db.execute(
        update(OwnerApplication).where(
            OwnerApplication.id == application_id,
            OwnerApplication.customer_id == current_user.id,
            OwnerApplication.status.in_([
                OwnerApplicationStatus.PENDING_REVIEW.value,
                OwnerApplicationStatus.NEED_MORE_INFO.value,
            ]),
        ).values(
            status=OwnerApplicationStatus.WITHDRAWN.value,
            withdrawn_at=withdrawn_at,
            withdraw_reason=reason,
            updated_at=withdrawn_at,
        ).execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        owned = db.get(OwnerApplication, application_id)
        if owned is None or owned.customer_id != current_user.id:
            raise HTTPException(status_code=404, detail='Không tìm thấy hồ sơ thuộc tài khoản này')
        raise HTTPException(status_code=409, detail='Trạng thái hồ sơ hiện tại không cho phép rút')
    db.expire_all()
    item = db.get(OwnerApplication, application_id)
    record_audit(db, current_user, 'owner_application', application_id, 'partner_application_withdrawn', {
        'to_status': OwnerApplicationStatus.WITHDRAWN.value, 'reason': reason,
    })
    db.commit(); db.refresh(item)
    return application_response(item)


@router.post('/owner-application/reapply', response_model=OwnerApplicationResponse, status_code=status.HTTP_201_CREATED)
def reapply_owner_application(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail='Chỉ CUSTOMER được tạo hồ sơ đăng ký đối tác')
    previous = _latest_application(db, current_user.id)
    if previous is None or previous.status != OwnerApplicationStatus.WITHDRAWN.value:
        raise HTTPException(status_code=409, detail='Chỉ có thể đăng ký lại sau khi hồ sơ gần nhất đã được rút')
    item = OwnerApplication(
        customer_id=current_user.id, status=OwnerApplicationStatus.DRAFT.value,
        representative=dict(previous.representative or {}), venue=dict(previous.venue or {}),
        legal_confirmed=False, submitted_at=datetime.now(timezone.utc),
    )
    db.add(item); db.flush()
    record_audit(db, current_user, 'owner_application', item.id, 'partner_application_reapplied', {
        'previous_application_id': previous.id,
    })
    db.commit(); db.refresh(item)
    return application_response(item)


@router.post('/owner-application/document', response_model=OwnerApplicationResponse)
async def upload_owner_application_document(
    document: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if current_user.role != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail='Chỉ CUSTOMER được cập nhật ảnh giấy tờ của hồ sơ')
    item = _latest_application(db, current_user.id)
    if item is None:
        item = OwnerApplication(customer_id=current_user.id, status=OwnerApplicationStatus.DRAFT.value, submitted_at=datetime.now(timezone.utc))
        db.add(item); db.flush()
    elif item.status not in (OwnerApplicationStatus.DRAFT.value, OwnerApplicationStatus.NEED_MORE_INFO.value, OwnerApplicationStatus.REJECTED.value):
        raise HTTPException(status_code=409, detail='Trạng thái hồ sơ hiện tại không cho phép thay ảnh giấy tờ')
    stored = await store_document(document)
    old_path = item.document_path
    for key, value in stored.items():
        setattr(item, key, value)
    item.document_uploaded_at = datetime.now(timezone.utc)
    db.flush(); record_audit(db, current_user, 'owner_application', item.id, 'partner_document_uploaded', {
        'mime': item.document_mime, 'size': item.document_size, 'replaced': bool(old_path),
    })
    db.commit(); db.refresh(item)
    if old_path and old_path != item.document_path:
        delete_document(old_path)
    return application_response(item)


@router.get('/owner-application/document')
def get_owner_application_document(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _latest_application(db, current_user.id)
    if item is None:
        raise HTTPException(status_code=404, detail='Chưa có hồ sơ đăng ký đối tác')
    return document_response(item.document_path, item.document_mime)


@router.delete('/owner-application/document', response_model=OwnerApplicationResponse)
def remove_owner_application_document(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail='Chỉ CUSTOMER được xóa ảnh giấy tờ của hồ sơ')
    item = _latest_application(db, current_user.id)
    if item is None:
        raise HTTPException(status_code=404, detail='Chưa có hồ sơ đăng ký đối tác')
    if item.status not in (OwnerApplicationStatus.DRAFT.value, OwnerApplicationStatus.NEED_MORE_INFO.value, OwnerApplicationStatus.REJECTED.value):
        raise HTTPException(status_code=409, detail='Trạng thái hồ sơ hiện tại không cho phép xóa ảnh giấy tờ')
    old_path = item.document_path
    item.document_path = None; item.document_mime = None; item.document_original_name = None
    item.document_size = None; item.document_uploaded_at = None
    record_audit(db, current_user, 'owner_application', item.id, 'partner_document_deleted', {})
    db.commit(); db.refresh(item); delete_document(old_path)
    return application_response(item)


@router.get('/avatars/{file_name}')
def get_avatar(file_name: str):
    return avatar_response(file_name)


@router.post('/profile/avatar', response_model=UserResponse)
async def update_avatar(
    avatar: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _, new_url = await store_avatar(avatar)
    old_url = current_user.avatar_url
    try:
        current_user.avatar_url = new_url
        db.commit(); db.refresh(current_user)
    except Exception:
        db.rollback(); delete_local_avatar(new_url)
        raise
    delete_local_avatar(old_url)
    return user_response(current_user)


@router.put('/profile', response_model=UserResponse)
def update_profile(payload: ProfileUpdateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail='Không có dữ liệu cần cập nhật')
    ensure_unique(db, current_user.email, changes.get('phone', current_user.phone), current_user.id)
    for key, value in changes.items():
        setattr(current_user, key, value.strip() if isinstance(value, str) else value)
    db.commit(); db.refresh(current_user)
    return user_response(current_user)


@router.put('/change-password', response_model=MessageResponse)
def change_password(payload: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail='Mật khẩu hiện tại không đúng')
    if verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail='Mật khẩu mới phải khác mật khẩu hiện tại')
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {'message': 'Đổi mật khẩu thành công'}
