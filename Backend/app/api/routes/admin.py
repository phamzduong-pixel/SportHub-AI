from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.facility import Facility
from ...models.field import Booking, Field
from ...models.owner_application import OwnerApplication, OwnerApplicationStatus
from ...models.user import User, UserRole
from ...schemas.admin import AdminFacilityList, AdminOwnerList, AdminStatusUpdate, AdminSummary, AdminUserList
from ...schemas.owner_application import OwnerApplicationDecision, OwnerApplicationResponse, OwnerApplicationReview
from ...schemas.user import UserResponse
from ..dependencies import require_system_admin
from .auth import application_response, user_response
from ...services.audit_service import record_audit
from ...services.partner_document_service import document_response

router = APIRouter(prefix='/admin', tags=['system-admin'])


@router.get('/summary', response_model=AdminSummary)
def summary(_: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    def count(model, *filters):
        return int(db.scalar(select(func.count(model.id)).where(*filters)) or 0)
    return {
        'total_users': count(User),
        'customers': count(User, User.role == UserRole.CUSTOMER.value),
        'owners': count(User, User.role == UserRole.OWNER.value),
        'managers': count(User, User.role == UserRole.MANAGER.value),
        'system_admins': count(User, User.role == UserRole.SYSTEM_ADMIN.value),
        'active_users': count(User, User.is_active.is_(True)), 'facilities': count(Facility),
        'active_facilities': count(Facility, Facility.is_active.is_(True)),
        'fields': count(Field), 'bookings': count(Booking),
        'pending_applications': count(OwnerApplication, OwnerApplication.status == OwnerApplicationStatus.PENDING_REVIEW.value),
    }


@router.get('/owners', response_model=AdminOwnerList)
def list_owners(
    is_active: bool | None = None, search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_system_admin), db: Session = Depends(get_db),
):
    filters = [User.role == UserRole.OWNER.value]
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if search:
        term = f'%{search.strip()}%'; filters.append(or_(User.full_name.ilike(term), User.email.ilike(term), User.phone.ilike(term)))
    total = int(db.scalar(select(func.count(User.id)).where(*filters)) or 0)
    owners = db.scalars(select(User).where(*filters).order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for owner in owners:
        approved_at = db.scalar(select(func.max(OwnerApplication.reviewed_at)).where(
            OwnerApplication.customer_id == owner.id, OwnerApplication.status == OwnerApplicationStatus.APPROVED.value,
        ))
        facility_count = int(db.scalar(select(func.count(Facility.id)).where(Facility.owner_id == owner.id)) or 0)
        field_count = int(db.scalar(select(func.count(Field.id)).where(Field.owner_id == owner.id)) or 0)
        items.append({
            'id': owner.id, 'full_name': owner.full_name, 'email': owner.email, 'phone': owner.phone,
            'avatar_url': owner.avatar_url, 'is_active': owner.is_active,
            'approved_at': approved_at.isoformat() if approved_at else None,
            'facility_count': facility_count, 'field_count': field_count,
        })
    return {'items': items, 'total': total, 'page': page, 'page_size': page_size}


@router.get('/users', response_model=AdminUserList)
def list_users(
    role: UserRole | None = None, is_active: bool | None = None,
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_system_admin), db: Session = Depends(get_db),
):
    filters = []
    if role:
        filters.append(User.role == role.value)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if search:
        term = f'%{search.strip()}%'
        filters.append(or_(User.full_name.ilike(term), User.email.ilike(term), User.phone.ilike(term)))
    total = int(db.scalar(select(func.count(User.id)).where(*filters)) or 0)
    users = db.scalars(select(User).where(*filters).order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {'items': [user_response(user) for user in users], 'total': total, 'page': page, 'page_size': page_size}


@router.patch('/users/{user_id}/status', response_model=UserResponse)
def update_user_status(user_id: int, payload: AdminStatusUpdate, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy tài khoản')
    if user.id == admin.id and not payload.is_active:
        raise HTTPException(status_code=409, detail='SYSTEM_ADMIN không thể tự khóa tài khoản đang đăng nhập')
    user.is_active = payload.is_active
    db.commit(); db.refresh(user)
    return user_response(user)


@router.get('/owner-applications', response_model=list[OwnerApplicationResponse])
def list_owner_applications(
    status: str | None = Query(default=None, pattern='^(DRAFT|PENDING_REVIEW|NEED_MORE_INFO|APPROVED|REJECTED|WITHDRAWN|PENDING)$'),
    search: str | None = Query(default=None, max_length=120), submitted_from: datetime | None = None,
    submitted_to: datetime | None = None, _: User = Depends(require_system_admin), db: Session = Depends(get_db),
):
    query = select(OwnerApplication).join(User, OwnerApplication.customer_id == User.id).order_by(OwnerApplication.submitted_at.desc())
    if status:
        query = query.where(OwnerApplication.status == ('PENDING_REVIEW' if status == 'PENDING' else status))
    if search:
        term = f'%{search.strip()}%'
        query = query.where(or_(User.full_name.ilike(term), User.email.ilike(term), User.phone.ilike(term)))
    if submitted_from:
        query = query.where(OwnerApplication.submitted_at >= submitted_from)
    if submitted_to:
        query = query.where(OwnerApplication.submitted_at <= submitted_to)
    return [application_response(item) for item in db.scalars(query).all()]


@router.get('/owner-applications/{application_id}', response_model=OwnerApplicationResponse)
def get_owner_application_detail(application_id: int, _: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    item = db.get(OwnerApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy hồ sơ đăng ký đối tác')
    return application_response(item)


@router.get('/owner-applications/{application_id}/document')
def get_owner_application_document(application_id: int, _: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    item = db.get(OwnerApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy hồ sơ đăng ký đối tác')
    return document_response(item.document_path, item.document_mime)


def _review_application(item: OwnerApplication, action: str, note: str | None, admin: User, db: Session):
    if item.status != OwnerApplicationStatus.PENDING_REVIEW.value:
        raise HTTPException(status_code=409, detail='Chỉ hồ sơ đang chờ xét duyệt mới được xử lý')
    if action == 'APPROVE' and not item.document_path:
        raise HTTPException(status_code=409, detail='Không thể duyệt hồ sơ chưa có ảnh giấy tờ')
    normalized_note = (note or '').strip()
    if action in ('REQUEST_MORE_INFO', 'REJECT') and len(normalized_note) < 3:
        raise HTTPException(status_code=422, detail='Phải nhập ghi chú hoặc lý do ít nhất 3 ký tự')
    target = {
        'APPROVE': OwnerApplicationStatus.APPROVED.value,
        'REQUEST_MORE_INFO': OwnerApplicationStatus.NEED_MORE_INFO.value,
        'REJECT': OwnerApplicationStatus.REJECTED.value,
    }[action]
    old_status = item.status
    reviewed_at = datetime.now(timezone.utc)
    result = db.execute(
        update(OwnerApplication).where(
            OwnerApplication.id == item.id,
            OwnerApplication.status == OwnerApplicationStatus.PENDING_REVIEW.value,
        ).values(
            status=target, admin_note=normalized_note or None,
            rejection_reason=normalized_note if action == 'REJECT' else None,
            reviewed_by=admin.id, reviewed_at=reviewed_at, updated_at=reviewed_at,
        ).execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail='Hồ sơ đã thay đổi trạng thái; vui lòng tải lại trước khi xử lý')
    db.expire_all()
    item = db.get(OwnerApplication, item.id)
    if action == 'APPROVE' and item.customer.role != UserRole.OWNER.value:
        item.customer.role = UserRole.OWNER.value
    record_audit(db, admin, 'owner_application', item.id, f'partner_application_{action.lower()}', {
        'from_status': old_status, 'to_status': target, 'customer_id': item.customer_id, 'admin_note': item.admin_note,
    })
    db.commit(); db.refresh(item)
    return application_response(item)


@router.patch('/owner-applications/{application_id}/review', response_model=OwnerApplicationResponse)
def review_owner_application(application_id: int, payload: OwnerApplicationReview, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    item = db.get(OwnerApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy hồ sơ đăng ký đối tác')
    return _review_application(item, payload.action, payload.admin_note, admin, db)


@router.patch('/owner-applications/{application_id}', response_model=OwnerApplicationResponse)
def decide_owner_application(application_id: int, payload: OwnerApplicationDecision, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    item = db.get(OwnerApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy hồ sơ đăng ký OWNER')
    return _review_application(item, 'APPROVE' if payload.approved else 'REJECT', payload.rejection_reason, admin, db)


@router.get('/facilities', response_model=AdminFacilityList)
def list_facilities(
    is_active: bool | None = None, search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_system_admin), db: Session = Depends(get_db),
):
    filters = []
    if is_active is not None:
        filters.append(Facility.is_active.is_(is_active))
    if search:
        term = f'%{search.strip()}%'; filters.append(or_(Facility.name.ilike(term), Facility.location.ilike(term)))
    total = int(db.scalar(select(func.count(Facility.id)).where(*filters)) or 0)
    rows = db.execute(
        select(Facility, User, func.count(Field.id)).join(User, Facility.owner_id == User.id)
        .outerjoin(Field, Field.facility_id == Facility.id).where(*filters)
        .group_by(Facility.id, User.id).order_by(Facility.created_at.desc(), Facility.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {'items': [{
        'id': facility.id, 'owner_id': owner.id, 'owner_name': owner.full_name,
        'owner_email': owner.email, 'name': facility.name, 'location': facility.location,
        'is_active': facility.is_active, 'field_count': int(field_count),
    } for facility, owner, field_count in rows], 'total': total, 'page': page, 'page_size': page_size}


@router.patch('/facilities/{facility_id}/status')
def update_facility_status(facility_id: int, payload: AdminStatusUpdate, _: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    facility = db.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy cơ sở')
    facility.is_active = payload.is_active
    db.commit()
    return {'id': facility.id, 'is_active': facility.is_active, 'message': 'Đã cập nhật trạng thái cơ sở'}
