from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.facility import Facility
from ...models.user import User
from ...schemas.facility import CancellationPolicyUpdate, FacilityCreate, FacilityHotlineUpdate, FacilityResponse, FacilityUpdate
from ...services.audit_service import record_audit
from ..dependencies import require_owner

router = APIRouter(prefix='/facilities', tags=['facilities'])


def binary_cancellation_rules(minutes: int):
    return [
        {'min_minutes_before': minutes, 'refund_percent': 100},
        {'min_minutes_before': 0, 'refund_percent': 0},
    ]


def owned_facility(db: Session, facility_id: int, owner_id: int) -> Facility:
    facility = db.scalar(select(Facility).where(Facility.id == facility_id, Facility.owner_id == owner_id))
    if facility is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy cơ sở')
    return facility


@router.get('', response_model=list[FacilityResponse])
def list_facilities(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    return list(db.scalars(select(Facility).where(Facility.owner_id == owner.id).order_by(Facility.name)).all())


@router.post('', response_model=FacilityResponse, status_code=201)
def create_facility(payload: FacilityCreate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = Facility(
        owner_id=owner.id, name=payload.name.strip(), location=payload.location.strip(),
        description=payload.description.strip() if payload.description else None,
        contact_phone=payload.contact_phone, opening_time=payload.opening_time, closing_time=payload.closing_time,
        amenities=payload.amenities, image_urls=payload.image_urls,
        free_cancellation_minutes=payload.free_cancellation_minutes,
        cancellation_rules=binary_cancellation_rules(payload.free_cancellation_minutes),
    )
    db.add(facility); db.flush(); record_audit(db, owner, 'facility', facility.id, 'facility_created', {'name': facility.name, 'location': facility.location}); db.commit(); db.refresh(facility)
    return facility


@router.put('/{facility_id}', response_model=FacilityResponse)
def update_facility(facility_id: int, payload: FacilityUpdate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    facility = owned_facility(db, facility_id, owner.id)
    changes = payload.model_dump(exclude={'cancellation_rules', 'free_cancellation_minutes'})
    for key, value in changes.items():
        setattr(facility, key, value.strip() if isinstance(value, str) else value)
    if payload.free_cancellation_minutes is not None:
        facility.free_cancellation_minutes = payload.free_cancellation_minutes
        facility.cancellation_rules = binary_cancellation_rules(payload.free_cancellation_minutes)
    record_audit(db, owner, 'facility', facility.id, 'facility_updated', {'fields': list(changes)})
    db.commit(); db.refresh(facility); return facility


@router.patch('/{facility_id}/hotline', response_model=FacilityResponse)
def update_facility_hotline(
    facility_id: int, payload: FacilityHotlineUpdate,
    owner: User = Depends(require_owner), db: Session = Depends(get_db),
):
    facility = owned_facility(db, facility_id, owner.id)
    previous = facility.contact_phone
    facility.contact_phone = payload.contact_phone
    record_audit(db, owner, 'facility', facility.id, 'facility_hotline_updated', {
        'previous_contact_phone': previous,
        'contact_phone': facility.contact_phone,
    })
    db.commit(); db.refresh(facility)
    return facility


@router.put('/{facility_id}/cancellation-policy', response_model=FacilityResponse)
def update_cancellation_policy(
    facility_id: int, payload: CancellationPolicyUpdate,
    owner: User = Depends(require_owner), db: Session = Depends(get_db),
):
    facility = owned_facility(db, facility_id, owner.id)
    minutes = payload.free_cancellation_minutes
    if minutes is None:
        full_refund_thresholds = [rule.min_minutes_before for rule in payload.rules or [] if rule.refund_percent == 100]
        if not full_refund_thresholds:
            raise HTTPException(status_code=422, detail='Chính sách phải có mốc hoàn 100% tiền cọc')
        minutes = max(full_refund_thresholds)
    facility.free_cancellation_minutes = minutes
    facility.cancellation_rules = binary_cancellation_rules(minutes)
    record_audit(db, owner, 'facility', facility.id, 'cancellation_policy_updated', {
        'free_cancellation_minutes': minutes, 'rules': facility.cancellation_rules,
    })
    db.commit(); db.refresh(facility)
    return facility
