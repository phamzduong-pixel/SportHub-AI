from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from ...database.session import get_db
from ...models.field import Field, FieldStatus
from ...models.facility import Facility
from ...models.time_slot import TimeSlot
from ...schemas.public_court import PublicCourtDetail

router = APIRouter(prefix='/public/courts', tags=['public-courts'])


@router.get('/{court_id}', response_model=PublicCourtDetail)
def get_public_court(court_id: int, db: Session = Depends(get_db)):
    """Canonical public detail endpoint; never applies OWNER tenant filtering."""
    court = db.scalar(
        select(Field).options(joinedload(Field.facility)).where(
            Field.id == court_id,
            Field.status == FieldStatus.AVAILABLE.value,
            or_(Field.facility_id.is_(None), Field.facility.has(and_(Facility.is_active.is_(True), Facility.status == 'APPROVED'))),
        )
    )
    if court is None:
        raise HTTPException(status_code=404, detail='Sân này không tồn tại hoặc đã ngừng hoạt động')
    slots = list(db.scalars(
        select(TimeSlot).where(
            TimeSlot.field_id == court.id,
            TimeSlot.is_active.is_(True),
        ).order_by(TimeSlot.start_time, TimeSlot.id)
    ).all())
    prices = [float(slot.price) for slot in slots] or [float(court.base_price)]
    facility = None if court.facility is None else {
        'id': court.facility.id,
        'name': court.facility.name,
        'location': court.facility.location,
        'description': court.facility.description,
        'contact_phone': court.facility.contact_phone,
        'opening_time': court.facility.opening_time.strftime('%H:%M') if court.facility.opening_time else None,
        'closing_time': court.facility.closing_time.strftime('%H:%M') if court.facility.closing_time else None,
        'amenities': court.facility.amenities or [], 'image_urls': (court.facility.image_urls or []) + [f'/api/facilities/images/{image.id}/content' for image in court.facility.images],
    }
    return {
        'court': court,
        'facility': facility,
        'time_slots': slots,
        'images': ([court.image_url] if court.image_url else []) + ((court.facility.image_urls or []) + [f'/api/facilities/images/{image.id}/content' for image in court.facility.images] if court.facility else []),
        'min_price': min(prices),
        'max_price': max(prices),
    }
