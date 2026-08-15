from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload
from ...database.session import get_db
from ...models.field import Field
from ...models.time_slot import TimeSlot
from ...models.user import User, UserFavoriteField
from ...schemas.favorite import FavoriteFieldResponse, FavoriteStatusResponse
from ...repositories.booking_repository import BookingRepository
from ...services.availability_service import AvailabilityService
from ..dependencies import get_current_user
router = APIRouter(prefix='/favorites', tags=['favorites'])
def customer(user: User = Depends(get_current_user)):
    if user.role not in ('CUSTOMER', 'OWNER'): raise HTTPException(status_code=403, detail='Chỉ tài khoản khách hàng được sử dụng sân yêu thích')
    return user
@router.get('', response_model=list[FavoriteFieldResponse])
def list_favorites(user: User = Depends(customer), db: Session = Depends(get_db)):
    entries = list(db.scalars(select(UserFavoriteField).options(joinedload(UserFavoriteField.field)).where(UserFavoriteField.user_id == user.id).order_by(UserFavoriteField.created_at.desc())).all()); result = []
    for entry in entries:
        field = entry.field; slots = list(db.scalars(select(TimeSlot).where(TimeSlot.field_id == field.id, TimeSlot.is_active.is_(True)).order_by(TimeSlot.start_time)).all())
        availability = AvailabilityService(BookingRepository(db)).list(booking_date=date.today(), field_id=field.id)
        available = availability[0]['available_slots'] if availability else []
        result.append({'field_id': field.id, 'field_name': field.name, 'sport_type': field.sport_type, 'location': field.location, 'image_url': field.image_url, 'price': min((float(slot.price) for slot in slots), default=float(field.base_price)), 'rating': field.rating, 'review_count': field.review_count, 'distance_km': field.distance_km, 'status': field.status, 'has_availability': field.status == 'available' and bool(available), 'next_slot': available[0].start_time.strftime('%H:%M') if available else None, 'created_at': entry.created_at})
    return result
@router.get('/{field_id}', response_model=FavoriteStatusResponse)
def favorite_status(field_id: int, user: User = Depends(customer), db: Session = Depends(get_db)):
    return {'field_id': field_id, 'is_favorite': db.scalar(select(UserFavoriteField.id).where(UserFavoriteField.user_id == user.id, UserFavoriteField.field_id == field_id)) is not None}
@router.put('/{field_id}', response_model=FavoriteStatusResponse)
def add_favorite(field_id: int, user: User = Depends(customer), db: Session = Depends(get_db)):
    if db.get(Field, field_id) is None: raise HTTPException(status_code=404, detail='Không tìm thấy sân')
    if db.scalar(select(UserFavoriteField.id).where(UserFavoriteField.user_id == user.id, UserFavoriteField.field_id == field_id)) is None: db.add(UserFavoriteField(user_id=user.id, field_id=field_id)); db.commit()
    return {'field_id': field_id, 'is_favorite': True}
@router.delete('/{field_id}', response_model=FavoriteStatusResponse)
def remove_favorite(field_id: int, user: User = Depends(customer), db: Session = Depends(get_db)):
    entry = db.scalar(select(UserFavoriteField).where(UserFavoriteField.user_id == user.id, UserFavoriteField.field_id == field_id))
    if entry: db.delete(entry); db.commit()
    return {'field_id': field_id, 'is_favorite': False}
