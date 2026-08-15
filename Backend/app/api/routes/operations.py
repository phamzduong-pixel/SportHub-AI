from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ...core.ownership import management_owner_id, owns_field
from ...database.session import get_db
from ...models.field import Booking, BookingSlot, Field
from ...models.operations import AuditLog, BookingComplaint, FieldBlock
from ...models.user import User
from ...schemas.operations import AuditLogResponse, ComplaintCreate, ComplaintResponse, ComplaintUpdate, FieldBlockCreate, FieldBlockResponse
from ...services.audit_service import record_audit
from ..dependencies import get_current_user, require_owner

router = APIRouter(tags=['operations'])


def block_response(item):
    return {'id': item.id, 'field_id': item.field_id, 'field_name': item.field.name, 'block_date': item.block_date, 'start_time': item.start_time, 'end_time': item.end_time, 'reason': item.reason, 'created_by': item.created_by, 'created_by_name': item.creator.full_name, 'created_at': item.created_at}


def complaint_response(item):
    return {'id': item.id, 'booking_id': item.booking_id, 'booking_code': item.booking.booking_code, 'customer_id': item.customer_id, 'customer_name': item.customer.full_name, 'field_id': item.booking.field_id, 'field_name': item.booking.field.name, 'category': item.category, 'description': item.description, 'evidence_url': item.evidence_url, 'status': item.status, 'resolution': item.resolution, 'resolved_by': item.resolved_by, 'resolved_by_name': item.resolver.full_name if item.resolver else None, 'resolved_at': item.resolved_at, 'created_at': item.created_at, 'updated_at': item.updated_at}


def complaint_query():
    return select(BookingComplaint).options(joinedload(BookingComplaint.booking).joinedload(Booking.field), joinedload(BookingComplaint.customer), joinedload(BookingComplaint.resolver))


@router.get('/field-blocks', response_model=list[FieldBlockResponse])
def list_blocks(field_id: int | None = Query(None, gt=0), block_date: date | None = None, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    owner_id = management_owner_id(user, db)
    filters = [or_(Field.owner_id == owner_id, Field.owner_id.is_(None))]
    if field_id: filters.append(FieldBlock.field_id == field_id)
    if block_date: filters.append(FieldBlock.block_date == block_date)
    items = db.scalars(select(FieldBlock).options(joinedload(FieldBlock.field), joinedload(FieldBlock.creator)).join(Field).where(*filters).order_by(FieldBlock.block_date, FieldBlock.start_time)).all()
    return [block_response(item) for item in items]


@router.post('/field-blocks', response_model=FieldBlockResponse, status_code=201)
def create_block(payload: FieldBlockCreate, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    field = db.scalar(select(Field).where(Field.id == payload.field_id).with_for_update())
    if field is None or not owns_field(user, field, db):
        raise HTTPException(status_code=404, detail='Không tìm thấy sân')
    overlap = db.scalar(select(FieldBlock.id).where(FieldBlock.field_id == field.id, FieldBlock.block_date == payload.block_date, FieldBlock.start_time < payload.end_time, FieldBlock.end_time > payload.start_time))
    if overlap:
        raise HTTPException(status_code=409, detail='Khoảng khóa sân bị trùng với lịch khóa hiện có')
    booking = db.scalar(select(Booking.id).outerjoin(BookingSlot, BookingSlot.booking_id == Booking.id).where(
        Booking.field_id == field.id, Booking.booking_date == payload.block_date,
        Booking.status.in_(('pending_payment','pending_confirmation','confirmed','in_progress')),
        or_(
            BookingSlot.start_time_snapshot < payload.end_time,
            and_(~Booking.booking_slots.any(), Booking.start_time_snapshot < payload.end_time),
        ),
        or_(
            BookingSlot.end_time_snapshot > payload.start_time,
            and_(~Booking.booking_slots.any(), Booking.end_time_snapshot > payload.start_time),
        ),
    ))
    if booking:
        raise HTTPException(status_code=409, detail='Không thể khóa khoảng thời gian đang có booking hoạt động')
    item = FieldBlock(**payload.model_dump(), created_by=user.id)
    db.add(item); db.flush(); record_audit(db, user, 'field_block', item.id, 'field_block_created', {'field_id': field.id, 'date': payload.block_date.isoformat(), 'start_time': str(payload.start_time), 'end_time': str(payload.end_time), 'reason': payload.reason}); db.commit()
    item = db.scalar(select(FieldBlock).options(joinedload(FieldBlock.field), joinedload(FieldBlock.creator)).where(FieldBlock.id == item.id))
    return block_response(item)


@router.delete('/field-blocks/{block_id}', status_code=204)
def delete_block(block_id: int, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    item = db.scalar(select(FieldBlock).options(joinedload(FieldBlock.field)).where(FieldBlock.id == block_id))
    if item is None or not owns_field(user, item.field, db):
        raise HTTPException(status_code=404, detail='Không tìm thấy lịch khóa sân')
    changes = {'field_id': item.field_id, 'date': item.block_date.isoformat(), 'reason': item.reason}
    db.delete(item); record_audit(db, user, 'field_block', block_id, 'field_block_deleted', changes); db.commit()


@router.post('/complaints', response_model=ComplaintResponse, status_code=201)
def create_complaint(payload: ComplaintCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ('CUSTOMER', 'OWNER'):
        raise HTTPException(status_code=403, detail='Chỉ CUSTOMER được gửi khiếu nại booking')
    booking = db.scalar(select(Booking).options(joinedload(Booking.field)).where(Booking.id == payload.booking_id))
    if booking is None or booking.customer_id != user.id:
        raise HTTPException(status_code=404, detail='Không tìm thấy booking của bạn')
    if booking.status == 'pending_payment':
        raise HTTPException(status_code=409, detail='Booking chưa phát sinh sử dụng hoặc thanh toán để khiếu nại')
    item = BookingComplaint(customer_id=user.id, **payload.model_dump())
    db.add(item)
    try:
        db.flush(); record_audit(db, user, 'booking_complaint', item.id, 'complaint_created', {'booking_id': booking.id, 'category': item.category}); db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail='Booking này đã có một khiếu nại')
    return complaint_response(db.scalar(complaint_query().where(BookingComplaint.id == item.id)))


@router.get('/complaints/my', response_model=list[ComplaintResponse])
def my_complaints(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [complaint_response(item) for item in db.scalars(complaint_query().where(BookingComplaint.customer_id == user.id).order_by(BookingComplaint.created_at.desc())).unique().all()]


@router.get('/complaints', response_model=list[ComplaintResponse])
def manage_complaints(status: str | None = Query(None, pattern='^(open|in_review|resolved|rejected)$'), user: User = Depends(require_owner), db: Session = Depends(get_db)):
    owner_id = management_owner_id(user, db); filters = [Booking.field.has(or_(Field.owner_id == owner_id, Field.owner_id.is_(None)))]
    if status: filters.append(BookingComplaint.status == status)
    return [complaint_response(item) for item in db.scalars(complaint_query().join(Booking).where(*filters).order_by(BookingComplaint.created_at.desc())).unique().all()]


@router.patch('/complaints/{complaint_id}', response_model=ComplaintResponse)
def update_complaint(complaint_id: int, payload: ComplaintUpdate, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    item = db.scalar(complaint_query().where(BookingComplaint.id == complaint_id))
    if item is None or not owns_field(user, item.booking.field, db):
        raise HTTPException(status_code=404, detail='Không tìm thấy khiếu nại')
    old = item.status; item.status = payload.status; item.resolution = payload.resolution.strip(); item.resolved_by = user.id
    item.resolved_at = datetime.now(timezone.utc) if payload.status in ('resolved','rejected') else None
    record_audit(db, user, 'booking_complaint', item.id, 'complaint_status_changed', {'from': old, 'to': item.status, 'resolution': item.resolution}); db.commit()
    return complaint_response(item)


@router.get('/audit-logs', response_model=list[AuditLogResponse])
def audit_logs(limit: int = Query(100, ge=1, le=500), user: User = Depends(require_owner), db: Session = Depends(get_db)):
    owner_id = management_owner_id(user, db)
    items = db.scalars(select(AuditLog).options(joinedload(AuditLog.actor)).where(AuditLog.owner_id == owner_id).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [{'id': item.id, 'actor_id': item.actor_id, 'actor_name': item.actor.full_name if item.actor else None, 'actor_role': item.actor_role, 'entity_type': item.entity_type, 'entity_id': item.entity_id, 'action': item.action, 'changes': item.changes or {}, 'created_at': item.created_at} for item in items]
