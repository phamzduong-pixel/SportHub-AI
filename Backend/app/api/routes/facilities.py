from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...database.session import get_db
from ...models.facility import Facility, FacilityDocument, FacilityImage, FacilityReviewEvent, FacilityStatus
from ...models.field import Field
from ...models.user import User
from ...schemas.facility import CancellationPolicyUpdate, FacilityCreate, FacilityHotlineUpdate, FacilityResponse, FacilityUpdate
from ...services.audit_service import record_audit
from ...services.facility_file_service import facility_file_response, facility_image_response, remove_facility_file, store_facility_file
from ...services.notification_service import NotificationService
from ..dependencies import get_current_user, require_owner

router = APIRouter(prefix='/facilities', tags=['facilities'])
EDITABLE = {FacilityStatus.DRAFT.value, FacilityStatus.REJECTED.value}
DOCUMENT_TYPES = {'BUSINESS_REGISTRATION', 'HOUSEHOLD_BUSINESS_LICENSE', 'OTHER', 'BUSINESS_LICENSE'}
SPORTS = {'Bóng đá', 'Cầu lông', 'Pickleball', 'Tennis', 'Bóng rổ', 'Bóng chuyền'}


def binary_cancellation_rules(minutes: int):
    return [{'min_minutes_before': minutes, 'refund_percent': 100}, {'min_minutes_before': 0, 'refund_percent': 0}]


def owned_facility(db: Session, facility_id: int, owner_id: int, details: bool = False) -> Facility:
    query = select(Facility).where(Facility.id == facility_id, Facility.owner_id == owner_id)
    if details:
        query = query.options(selectinload(Facility.images), selectinload(Facility.documents), selectinload(Facility.reviews))
    facility = db.scalar(query)
    if facility is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy cơ sở')
    return facility


def response(db: Session, facility: Facility):
    data = {column.name: getattr(facility, column.name) for column in Facility.__table__.columns}
    data['field_count'] = int(db.scalar(select(func.count(Field.id)).where(Field.facility_id == facility.id)) or 0)
    data['images'] = [{**{column.name: getattr(item, column.name) for column in FacilityImage.__table__.columns if column.name not in {'facility_id', 'file_path'}}, 'url': f'/api/facilities/{facility.id}/images/{item.id}/content'} for item in facility.images]
    data['documents'] = [{**{column.name: getattr(item, column.name) for column in FacilityDocument.__table__.columns if column.name not in {'facility_id', 'file_path', 'file_sha256'}}, 'url': f'/api/facilities/{facility.id}/documents/{item.id}/content'} for item in facility.documents]
    data['reviews'] = [{column.name: getattr(item, column.name) for column in FacilityReviewEvent.__table__.columns if column.name != 'facility_id'} for item in facility.reviews]
    return data


def add_event(db, facility, actor, action, old_status, note=None):
    db.add(FacilityReviewEvent(facility_id=facility.id, actor_id=actor.id, action=action, from_status=old_status, to_status=facility.status, note=note))


@router.get('', response_model=list[FacilityResponse])
def list_facilities(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    items = list(db.scalars(select(Facility).options(selectinload(Facility.images), selectinload(Facility.documents), selectinload(Facility.reviews)).where(Facility.owner_id == owner.id).order_by(Facility.created_at.desc())).all())
    return [response(db, item) for item in items]


@router.get('/{facility_id}', response_model=FacilityResponse)
def get_facility(facility_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    return response(db, owned_facility(db, facility_id, owner.id, True))


@router.post('', response_model=FacilityResponse, status_code=201)
def create_facility(payload: FacilityCreate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    values = payload.model_dump(exclude={'cancellation_rules'})
    values['name'] = payload.name.strip(); values['location'] = payload.location.strip()
    values['description'] = payload.description.strip() if payload.description else None
    values['status'] = FacilityStatus.DRAFT.value; values['is_active'] = False
    values['cancellation_rules'] = binary_cancellation_rules(payload.free_cancellation_minutes)
    facility = Facility(owner_id=owner.id, **values)
    db.add(facility); db.flush(); add_event(db, facility, owner, 'CREATED', None)
    record_audit(db, owner, 'facility', facility.id, 'facility_draft_created', {'name': facility.name})
    db.commit(); db.refresh(facility)
    return response(db, owned_facility(db, facility.id, owner.id, True))


@router.put('/{facility_id}', response_model=FacilityResponse)
def update_facility(facility_id: int, payload: FacilityUpdate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    data = payload.model_dump(exclude={'cancellation_rules', 'free_cancellation_minutes'}, exclude_none=False)
    if facility.status == FacilityStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=409, detail='Hồ sơ đang chờ xét duyệt và không thể chỉnh sửa')
    if facility.status == FacilityStatus.SUSPENDED.value:
        raise HTTPException(status_code=409, detail='Cơ sở đang tạm ngừng; vui lòng liên hệ System Admin')
    if facility.status == FacilityStatus.APPROVED.value and (not payload.name.strip() or not payload.location.strip()):
        raise HTTPException(status_code=422, detail='Cơ sở đã duyệt phải có tên và địa chỉ')
    important_changed = facility.status == FacilityStatus.APPROVED.value and (
        payload.name.strip() != facility.name or payload.location.strip() != facility.location
    )
    for key, value in data.items():
        if key in {'description', 'contact_email', 'city', 'district'} and isinstance(value, str):
            value = value.strip() or None
        elif key in {'name', 'location'} and isinstance(value, str):
            value = value.strip()
        setattr(facility, key, value)
    if payload.free_cancellation_minutes is not None:
        facility.cancellation_rules = binary_cancellation_rules(payload.free_cancellation_minutes)
    if important_changed:
        old = facility.status
        facility.status = FacilityStatus.DRAFT.value; facility.is_active = False
        facility.approved_at = None; facility.approved_by = None
        add_event(db, facility, owner, 'IMPORTANT_INFO_CHANGED', old, 'Tên hoặc địa chỉ thay đổi; cần xét duyệt lại')
    record_audit(db, owner, 'facility', facility.id, 'facility_updated', {'requires_review': important_changed})
    db.commit()
    return response(db, owned_facility(db, facility.id, owner.id, True))


@router.delete('/{facility_id}/draft', status_code=204)
def delete_facility_draft(facility_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    if facility.status != FacilityStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail='Chỉ hồ sơ ở trạng thái DRAFT mới có thể xóa')
    if db.scalar(select(Field.id).where(Field.facility_id == facility.id).limit(1)) is not None:
        raise HTTPException(status_code=409, detail='Bản nháp đang có dữ liệu sân liên kết và không thể xóa')

    image_paths = [item.file_path for item in facility.images]
    document_paths = [item.file_path for item in facility.documents]
    record_audit(db, owner, 'facility', facility.id, 'facility_draft_deleted', {'name': facility.name})
    db.delete(facility)
    db.commit()

    for path in image_paths:
        still_referenced = db.scalar(select(FacilityImage.id).where(FacilityImage.file_path == path).limit(1))
        if still_referenced is None:
            remove_facility_file(path, False)
    for path in document_paths:
        still_referenced = db.scalar(select(FacilityDocument.id).where(FacilityDocument.file_path == path).limit(1))
        if still_referenced is None:
            remove_facility_file(path, True)
    return Response(status_code=204)


@router.post('/{facility_id}/submit', response_model=FacilityResponse)
def submit_facility(facility_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    if facility.status not in EDITABLE:
        raise HTTPException(status_code=409, detail='Trạng thái hiện tại không cho phép gửi xét duyệt')
    missing = []
    for key in ('name', 'location', 'description', 'contact_phone', 'opening_time', 'closing_time'):
        if not getattr(facility, key):
            missing.append(key)
    if not facility.sports:
        missing.append('sports')
    if not any(image.category == 'COVER' for image in facility.images):
        missing.append('cover_image')
    if not facility.documents or any(
        not document.document_number or document.document_type not in DOCUMENT_TYPES
        for document in facility.documents
    ):
        missing.append('verification_documents')
    if missing:
        raise HTTPException(status_code=422, detail='Hồ sơ chưa đầy đủ: ' + ', '.join(missing))
    old = facility.status
    facility.status = FacilityStatus.PENDING_APPROVAL.value; facility.is_active = False
    facility.submitted_at = datetime.now(timezone.utc); facility.reviewed_at = None; facility.rejection_reason = None
    add_event(db, facility, owner, 'SUBMITTED', old)
    record_audit(db, owner, 'facility', facility.id, 'facility_submitted', {})
    NotificationService(db).facility_submitted(facility.id, facility.name, owner.full_name)
    db.commit()
    return response(db, owned_facility(db, facility.id, owner.id, True))


@router.post('/{facility_id}/cancel-review', response_model=FacilityResponse)
def cancel_review(facility_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    if facility.status != FacilityStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=409, detail='Chỉ hồ sơ đang chờ xét duyệt mới có thể hủy')
    old = facility.status; facility.status = FacilityStatus.DRAFT.value; facility.is_active = False
    add_event(db, facility, owner, 'REVIEW_CANCELLED', old)
    db.commit()
    return response(db, owned_facility(db, facility.id, owner.id, True))


@router.post('/{facility_id}/images', response_model=FacilityResponse)
async def upload_image(facility_id: int, category: str = Form('ADDITIONAL'), image: UploadFile = File(...), owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    if facility.status == FacilityStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=409, detail='Không thể thay ảnh khi hồ sơ đang chờ duyệt')
    category = category.upper()
    if category not in {'COVER', 'FRONT', 'COURT_AREA', 'ADDITIONAL'}:
        raise HTTPException(status_code=422, detail='Loại ảnh không hợp lệ')
    stored = await store_facility_file(image, facility.id, False)
    item = FacilityImage(facility_id=facility.id, category=category, **stored)
    db.add(item); db.commit()
    return response(db, owned_facility(db, facility.id, owner.id, True))


@router.get('/{facility_id}/images/{image_id}/content')
def owned_image_content(facility_id: int, image_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(FacilityImage).join(Facility).where(FacilityImage.id == image_id, FacilityImage.facility_id == facility_id))
    if item is None or (user.role != 'SYSTEM_ADMIN' and item.facility.owner_id != user.id):
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh')
    return facility_image_response(item.file_path, item.mime_type, public_cache=False)

@router.delete('/{facility_id}/images/{image_id}', response_model=FacilityResponse)
def delete_image(facility_id: int, image_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    if facility.status == FacilityStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=409, detail='Không thể xóa ảnh khi hồ sơ đang chờ duyệt')
    item = db.scalar(select(FacilityImage).where(FacilityImage.id == image_id, FacilityImage.facility_id == facility.id))
    if item is None: raise HTTPException(status_code=404, detail='Không tìm thấy ảnh')
    path = item.file_path; db.delete(item); db.commit(); remove_facility_file(path, False)
    return response(db, owned_facility(db, facility.id, owner.id, True))


@router.get('/images/{image_id}/content')
def image_content(image_id: int, db: Session = Depends(get_db)):
    item = db.get(FacilityImage, image_id)
    if item is None or (item.facility.status != FacilityStatus.APPROVED.value or not item.facility.is_active):
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh')
    return facility_image_response(item.file_path, item.mime_type, public_cache=True)


@router.post('/{facility_id}/documents', response_model=FacilityResponse)
async def upload_document(facility_id: int, document_type: str = Form(...), document_name: str = Form(...), document_number: str = Form(...), issued_date: str | None = Form(None), issued_by: str | None = Form(None), document: UploadFile = File(...), owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    if facility.status == FacilityStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=409, detail='Không thể thay tài liệu khi hồ sơ đang chờ duyệt')
    from datetime import date
    try: parsed_date = date.fromisoformat(issued_date) if issued_date else None
    except ValueError: raise HTTPException(status_code=422, detail='Ngày cấp không hợp lệ')
    document_type = document_type.strip().upper()
    document_number = document_number.strip()
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail='Loại giấy tờ xác minh không hợp lệ')
    if len(document_name.strip()) < 2 or len(document_number) < 2:
        raise HTTPException(status_code=422, detail='Tên và số giấy tờ là bắt buộc')
    if len(facility.documents) >= 10:
        raise HTTPException(status_code=422, detail='Mỗi hồ sơ tối đa 10 tệp giấy tờ')
    if facility.status == FacilityStatus.APPROVED.value:
        old = facility.status; facility.status = FacilityStatus.DRAFT.value; facility.is_active = False
        facility.approved_at = None; facility.approved_by = None
        add_event(db, facility, owner, 'VERIFICATION_DOCUMENT_CHANGED', old, 'Tài liệu xác minh thay đổi; cần xét duyệt lại')
    stored = await store_facility_file(document, facility.id, True)
    duplicate = db.scalar(select(FacilityDocument.id).where(
        FacilityDocument.facility_id == facility.id,
        FacilityDocument.file_sha256 == stored['file_sha256'],
    ))
    if duplicate is not None:
        remove_facility_file(stored['file_path'], True)
        raise HTTPException(status_code=409, detail='Tệp này đã có trong hồ sơ')
    item = FacilityDocument(facility_id=facility.id, document_type=document_type, document_name=document_name.strip(), document_number=document_number, issued_date=parsed_date, issued_by=(issued_by or '').strip() or None, **stored)
    db.add(item); db.commit()
    return response(db, owned_facility(db, facility.id, owner.id, True))


@router.get('/{facility_id}/documents/{document_id}/content')
def document_content(facility_id: int, document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(FacilityDocument).join(Facility).where(FacilityDocument.id == document_id, FacilityDocument.facility_id == facility_id))
    if item is None or (user.role != 'SYSTEM_ADMIN' and item.facility.owner_id != user.id):
        raise HTTPException(status_code=404, detail='Không tìm thấy tài liệu')
    return facility_file_response(item.file_path, item.mime_type, True)


@router.delete('/{facility_id}/documents/{document_id}', response_model=FacilityResponse)
def delete_document(facility_id: int, document_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    if facility.status == FacilityStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=409, detail='Không thể xóa tài liệu khi hồ sơ đang chờ duyệt')
    item = db.scalar(select(FacilityDocument).where(FacilityDocument.id == document_id, FacilityDocument.facility_id == facility.id))
    if item is None: raise HTTPException(status_code=404, detail='Không tìm thấy tài liệu')
    if facility.status == FacilityStatus.APPROVED.value:
        old = facility.status; facility.status = FacilityStatus.DRAFT.value; facility.is_active = False
        facility.approved_at = None; facility.approved_by = None
        add_event(db, facility, owner, 'VERIFICATION_DOCUMENT_REMOVED', old, 'Tài liệu xác minh thay đổi; cần xét duyệt lại')
    path = item.file_path; db.delete(item); db.commit(); remove_facility_file(path, True)
    return response(db, owned_facility(db, facility.id, owner.id, True))


@router.patch('/{facility_id}/hotline', response_model=FacilityResponse)
def update_facility_hotline(facility_id: int, payload: FacilityHotlineUpdate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    facility.contact_phone = payload.contact_phone; db.commit()
    return response(db, owned_facility(db, facility.id, owner.id, True))


@router.put('/{facility_id}/cancellation-policy', response_model=FacilityResponse)
def update_cancellation_policy(facility_id: int, payload: CancellationPolicyUpdate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id, True)
    minutes = payload.free_cancellation_minutes
    if minutes is None:
        thresholds = [rule.min_minutes_before for rule in payload.rules or [] if rule.refund_percent == 100]
        if not thresholds: raise HTTPException(status_code=422, detail='Chính sách phải có mức hoàn 100%')
        minutes = max(thresholds)
    facility.free_cancellation_minutes = minutes; facility.cancellation_rules = binary_cancellation_rules(minutes)
    db.commit()
    return response(db, owned_facility(db, facility.id, owner.id, True))
