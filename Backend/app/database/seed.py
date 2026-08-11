from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from ..core.config import settings
from ..core.security import get_password_hash
from ..models.field import Booking, Field
from ..models.facility import Facility
from ..models.payment import Payment
from ..models.time_slot import TimeSlot
from ..models.user import User, UserRole


def seed_db(session):
    _seed_user(
        session, role=UserRole.SYSTEM_ADMIN.value, full_name=settings.SYSTEM_ADMIN_FULL_NAME,
        email=settings.SYSTEM_ADMIN_EMAIL, password=settings.SYSTEM_ADMIN_PASSWORD,
    )
    owner = _seed_user(
        session, role=UserRole.OWNER.value, full_name=settings.OWNER_FULL_NAME,
        email=settings.OWNER_EMAIL, password=settings.OWNER_PASSWORD,
    )
    if not settings.SEED_DEMO_DATA:
        session.commit()
        return
    customer = _seed_user(
        session, role=UserRole.CUSTOMER.value, full_name='Nguyễn Minh Khách',
        email=settings.CUSTOMER_EMAIL, password=settings.CUSTOMER_PASSWORD,
    )
    session.flush()
    if not owner or not customer:
        raise RuntimeError('SEED_DEMO_DATA=true yêu cầu đủ thông tin OWNER và CUSTOMER')
    fields = _seed_fields_and_slots(session, owner.id)
    session.flush()
    _seed_demo_facility_hotlines(session, owner.id)
    _seed_bookings_and_payments(session, owner, customer, fields)
    session.commit()


def _seed_demo_facility_hotlines(session, owner_id: int, hotline: str = '0901 234 567'):
    """Fill only missing contact numbers in demo facilities; OWNER data always wins."""
    facilities = list(session.scalars(
        select(Facility).where(Facility.owner_id == owner_id),
    ).all())
    for facility in facilities:
        if not facility.contact_phone or facility.contact_phone == '0987 654 321':
            facility.contact_phone = hotline


def _seed_user(session, *, role: str, full_name: str, email: str | None, password: str | None):
    if not email and not password:
        return None
    if not email or not password:
        raise RuntimeError(f'Cần cấu hình đồng thời email và password cho vai trò {role}')
    user = session.scalar(select(User).where(User.email == email.lower()))
    if user:
        return user
    user = User(
        full_name=full_name, email=email.lower(), hashed_password=get_password_hash(password),
        role=role, is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def _seed_fields_and_slots(session, owner_id: int | None = None):
    legacy_description = 'Dữ liệu sân mẫu phục vụ kịch bản demo SportHub AI.'
    demo_image_by_sport = {
        'bóng đá': '/images/sports/football-court.webp',
        'cầu lông': '/images/sports/badminton-court.webp',
        'tennis': '/images/sports/tennis-court.webp',
        'bóng rổ': '/images/sports/basketball-court.webp',
        'pickleball': '/images/sports/pickleball-court.webp',
        'bóng chuyền': '/images/sports/volleyball-court.webp',
    }
    definitions = [
        ('Sân bóng đá Trung Tâm', 'bóng đá', 'Quận 1, TP.HCM', 14, 650000,
         'Sân bóng đá cỏ nhân tạo 7 người nằm tại trung tâm thành phố, hệ thống đèn LED tiêu chuẩn và mặt sân được bảo dưỡng định kỳ. Phù hợp cho đội nhóm, giải phong trào và các buổi tập sau giờ làm.',
         ['Bãi xe', 'Phòng thay đồ', 'Nước uống', 'Đèn LED', 'Cho thuê bóng'], [
            ('Ca sáng', time(7), time(9), 550000), ('Ca chiều', time(15), time(17), 600000), ('Ca tối', time(18), time(20), 750000),
        ]),
        ('Sân cầu lông Riverside', 'cầu lông', 'Quận Bình Thạnh, TP.HCM', 4, 180000,
         'Sân cầu lông trong nhà với thảm thi đấu chống trượt, trần cao và ánh sáng không gây chói. Khu vực chờ thoáng mát, phù hợp cho cả người mới chơi và vận động viên luyện tập thường xuyên.',
         ['Bãi xe', 'Phòng thay đồ', 'Máy lạnh', 'Cho thuê vợt', 'Wifi'], [
            ('Ca 08:00', time(8), time(10), 160000), ('Ca 17:00', time(17), time(19), 210000), ('Ca 19:00', time(19), time(21), 230000),
        ]),
        ('Sân Pickleball Green Park', 'pickleball', 'Thành phố Thủ Đức, TP.HCM', 4, 240000,
         'Cụm sân pickleball ngoài trời trong khuôn viên xanh, bề mặt acrylic êm chân và vạch sân rõ nét. Không gian phù hợp cho nhóm bạn, lớp học cơ bản và các trận giao lưu cuối tuần.',
         ['Bãi xe', 'Khu nghỉ', 'Nước uống', 'Cho thuê vợt', 'Tủ đồ'], [
            ('Ca sáng', time(6), time(8), 200000), ('Ca chiều', time(16), time(18), 250000), ('Ca tối', time(18), time(20), 280000),
        ]),
    ]
    recommendation_metadata = [(4.8, 326, 1.8), (4.7, 218, 2.4), (4.9, 184, 3.1)]
    result = []
    for index, (name, sport, location, capacity, price, description, amenities, slots) in enumerate(definitions):
        field = session.scalar(select(Field).where(Field.name == name))
        if field is None:
            field = Field(
                name=name, sport_type=sport, location=location, capacity=capacity, owner_id=owner_id,
                base_price=Decimal(price), status='available',
                description=description, amenities=amenities,
                rating=recommendation_metadata[index][0], review_count=recommendation_metadata[index][1],
                distance_km=recommendation_metadata[index][2],
            )
            session.add(field); session.flush()
        else:
            if not field.rating:
                field.rating, field.review_count, field.distance_km = recommendation_metadata[index]
            if not field.description or field.description == legacy_description:
                field.description = description
            if not field.amenities or field.amenities == ['Bãi xe', 'Phòng thay đồ', 'Nước uống']:
                field.amenities = amenities
        if owner_id and field.owner_id is None:
            field.owner_id = owner_id
        if not field.image_url:
            field.image_url = demo_image_by_sport.get(sport)
        existing_slots = list(session.scalars(select(TimeSlot).where(TimeSlot.field_id == field.id)).all())
        if not existing_slots:
            for slot_name, start, end, slot_price in slots:
                session.add(TimeSlot(
                    field_id=field.id, name=slot_name, start_time=start, end_time=end,
                    price=Decimal(slot_price), is_active=True,
                ))
            session.flush()
            existing_slots = list(session.scalars(select(TimeSlot).where(TimeSlot.field_id == field.id).order_by(TimeSlot.start_time)).all())
        result.append((field, existing_slots))
    return result


def _seed_bookings_and_payments(session, owner: User, customer: User, fields):
    today = date.today()
    definitions = [
        ('DEMO-COMPLETED', fields[0][0], fields[0][1][0], today - timedelta(days=3), 'completed'),
        ('DEMO-CONFIRMED', fields[1][0], fields[1][1][1], today + timedelta(days=2), 'confirmed'),
        ('DEMO-PENDING', fields[2][0], fields[2][1][2], today + timedelta(days=3), 'pending_confirmation'),
    ]
    bookings = {}
    for code, field, slot, booking_date, status in definitions:
        booking = session.scalar(select(Booking).where(Booking.booking_code == code))
        if booking is None:
            booking = Booking(
                booking_code=code, customer_id=customer.id, field_id=field.id,
                time_slot_id=slot.id, booking_date=booking_date,
                start_time_snapshot=slot.start_time, end_time_snapshot=slot.end_time,
                price_snapshot=slot.price, total_amount=slot.price, status=status,
                note='Dữ liệu lịch đặt mẫu phục vụ demo.',
            )
            session.add(booking); session.flush()
        bookings[code] = booking
    completed = bookings['DEMO-COMPLETED']
    if session.scalar(select(Payment).where(Payment.transaction_code == 'PAY-DEMO-001')) is None:
        session.add(Payment(
            booking_id=completed.id, transaction_code='PAY-DEMO-001', amount=completed.total_amount,
            payment_method='cash', payment_type='full', status='paid',
            paid_at=datetime.now(timezone.utc) - timedelta(days=3), confirmed_by=owner.id,
            note='Thanh toán mẫu phục vụ demo.',
        ))
