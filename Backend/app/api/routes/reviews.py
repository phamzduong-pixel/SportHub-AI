from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from ...database.session import get_db
from ...models.field import Booking, Field
from ...models.review import Review
from ...models.user import User
from ...schemas.review import ReviewCreate, ReviewUpdate, ReviewReply, ReviewResponse, ReviewSummaryResponse
from ..dependencies import get_current_user
router = APIRouter(tags=['reviews'])
def response(review: Review):
    return {'id': review.id, 'booking_id': review.booking_id, 'customer_id': review.customer_id, 'customer_name': review.customer.full_name, 'field_id': review.field_id, 'field_name': review.field.name, 'rating': review.rating, 'comment': review.comment, 'owner_reply': review.owner_reply, 'replied_at': review.replied_at, 'created_at': review.created_at}
def query(): return select(Review).options(joinedload(Review.customer), joinedload(Review.field))
def refresh_rating(db: Session, field_id: int):
    average, count = db.execute(select(func.avg(Review.rating), func.count(Review.id)).where(Review.field_id == field_id)).one(); field = db.get(Field, field_id); field.rating = round(float(average or 0), 1); field.review_count = int(count or 0)
@router.post('/reviews', response_model=ReviewResponse, status_code=201)
def create_review(payload: ReviewCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ('CUSTOMER', 'OWNER'): raise HTTPException(status_code=403, detail='Chỉ tài khoản khách hàng được đánh giá sân')
    booking = db.get(Booking, payload.booking_id)
    if booking is None or booking.customer_id != user.id: raise HTTPException(status_code=404, detail='Không tìm thấy booking của bạn')
    if booking.status != 'completed': raise HTTPException(status_code=409, detail='Chỉ được đánh giá sau khi booking hoàn thành')
    if db.scalar(select(Review.id).where(Review.booking_id == booking.id)): raise HTTPException(status_code=409, detail='Booking này đã được đánh giá')
    review = Review(booking_id=booking.id, customer_id=user.id, field_id=booking.field_id, rating=payload.rating, comment=payload.comment); db.add(review)
    try:
        db.flush(); refresh_rating(db, booking.field_id); db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Booking này đã được đánh giá')
    return response(db.scalar(query().where(Review.id == review.id)))
@router.patch('/reviews/{review_id}', response_model=ReviewResponse)
def update_review(review_id: int, payload: ReviewUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ('CUSTOMER', 'OWNER'): raise HTTPException(status_code=403, detail='Chỉ khách hàng mới có thể chỉnh sửa đánh giá')
    review = db.scalar(query().where(Review.id == review_id))
    if review is None or review.customer_id != user.id: raise HTTPException(status_code=404, detail='Không tìm thấy đánh giá của bạn')
    
    review.rating = payload.rating
    review.comment = payload.comment
    db.commit()
    refresh_rating(db, review.field_id)
    db.commit()
    return response(db.scalar(query().where(Review.id == review.id)))

@router.get('/fields/{field_id}/reviews', response_model=ReviewSummaryResponse)
def field_reviews(field_id: int, db: Session = Depends(get_db)):
    if db.get(Field, field_id) is None: raise HTTPException(status_code=404, detail='Không tìm thấy sân')
    items = list(db.scalars(query().where(Review.field_id == field_id).order_by(Review.created_at.desc())).all()); average = sum(item.rating for item in items) / len(items) if items else 0
    return {'field_id': field_id, 'average_rating': round(average, 1), 'total_reviews': len(items), 'items': [response(item) for item in items]}

@router.get('/bookings/{booking_id}/review', response_model=ReviewResponse)
def get_booking_review(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if booking is None or booking.customer_id != user.id: raise HTTPException(status_code=404, detail='Không tìm thấy booking của bạn')
    review = db.scalar(query().where(Review.booking_id == booking_id))
    if review is None: raise HTTPException(status_code=404, detail='Đánh giá không tồn tại')
    return response(review)

@router.get('/customer/reviews', response_model=list[ReviewResponse])
def customer_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ('CUSTOMER', 'OWNER'): raise HTTPException(status_code=403, detail='Chỉ khách hàng mới có thể xem')
    return [response(item) for item in db.scalars(query().where(Review.customer_id == user.id).order_by(Review.created_at.desc())).all()]

@router.get('/management/reviews', response_model=list[ReviewResponse])
def management_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != 'OWNER': raise HTTPException(status_code=403, detail='Chỉ OWNER được xem và phản hồi đánh giá')
    return [response(item) for item in db.scalars(query().join(Field, Review.field_id == Field.id).where(or_(Field.owner_id == user.id, Field.owner_id.is_(None))).order_by(Review.created_at.desc())).all()]
@router.put('/management/reviews/{review_id}/reply', response_model=ReviewResponse)
def reply_review(review_id: int, payload: ReviewReply, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != 'OWNER': raise HTTPException(status_code=403, detail='Chỉ OWNER được phản hồi đánh giá')
    review = db.scalar(query().join(Field, Review.field_id == Field.id).where(Review.id == review_id, or_(Field.owner_id == user.id, Field.owner_id.is_(None))))
    if review is None: raise HTTPException(status_code=404, detail='Không tìm thấy đánh giá')
    review.owner_reply = payload.reply.strip(); review.replied_by = user.id; review.replied_at = datetime.now(timezone.utc); db.commit(); return response(review)
