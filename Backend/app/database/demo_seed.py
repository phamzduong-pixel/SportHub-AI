from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text

from ..core.config import settings
from ..core.security import get_password_hash, verify_password
from ..models.facility import Facility, default_cancellation_rules
from ..models.field import Booking, Field
from ..models.invoice import Invoice
from ..models.payment import EscrowStatus, Payment, PaymentStatus, PaymentType
from ..models.review import Review
from ..models.time_slot import TimeSlot
from ..models.user import User, UserFavoriteField, UserRole

DEMO_BOOKING_CODES = ('DEMO-COMPLETED', 'DEMO-CONFIRMED', 'DEMO-PENDING')
ACTIVE_BOOKING_STATUSES = ('pending_payment', 'pending_confirmation', 'confirmed', 'in_progress')

DEMO_VENUES = (
    {
        'facility': {
            'name': 'SportHub Central Arena', 'location': 'Quận 1, TP.HCM',
            'description': 'Cụm sân trung tâm dành cho bóng đá phong trào và tập luyện sau giờ làm.',
            'contact_phone': '0901 234 567', 'opening_time': time(6), 'closing_time': time(23),
            'amenities': ['Bãi xe', 'Phòng thay đồ', 'Nước uống', 'Wifi'],
            'image_urls': ['/images/sports/football-court.webp'],
        },
        'field': {
            'name': 'Sân bóng đá Trung Tâm', 'sport_type': 'bóng đá', 'capacity': 14,
            'base_price': Decimal('650000'),
            'description': 'Sân cỏ nhân tạo 7 người, đèn LED và mặt sân được bảo dưỡng định kỳ.',
            'amenities': ['Bãi xe', 'Phòng thay đồ', 'Nước uống', 'Đèn LED', 'Cho thuê bóng'],
            'image_url': '/images/sports/football-court.webp',
            'rating': 4.8, 'review_count': 326, 'distance_km': 1.8,
        },
        'slots': (
            ('Ca sáng', time(7), time(9), 550000, 550000, 650000),
            ('Ca chiều', time(15), time(17), 600000, 600000, 700000),
            ('Ca tối', time(18), time(20), 750000, 750000, 850000),
        ),
    },
    {
        'facility': {
            'name': 'SportHub Riverside', 'location': 'Quận Bình Thạnh, TP.HCM',
            'description': 'Cơ sở thể thao trong nhà, thoáng mát và phù hợp luyện tập thường xuyên.',
            'contact_phone': '0901 234 568', 'opening_time': time(6), 'closing_time': time(22),
            'amenities': ['Bãi xe', 'Phòng thay đồ', 'Máy lạnh', 'Wifi'],
            'image_urls': ['/images/sports/badminton-court.webp'],
        },
        'field': {
            'name': 'Sân cầu lông Riverside', 'sport_type': 'cầu lông', 'capacity': 4,
            'base_price': Decimal('180000'),
            'description': 'Sân trong nhà với thảm thi đấu chống trượt, trần cao và ánh sáng không gây chói.',
            'amenities': ['Bãi xe', 'Phòng thay đồ', 'Máy lạnh', 'Cho thuê vợt', 'Wifi'],
            'image_url': '/images/sports/badminton-court.webp',
            'rating': 4.7, 'review_count': 218, 'distance_km': 2.4,
        },
        'slots': (
            ('Ca 08:00', time(8), time(10), 160000, 160000, 180000),
            ('Ca 17:00', time(17), time(19), 210000, 210000, 230000),
            ('Ca 19:00', time(19), time(21), 230000, 230000, 250000),
        ),
    },
    {
        'facility': {
            'name': 'SportHub Green Park', 'location': 'Thành phố Thủ Đức, TP.HCM',
            'description': 'Cụm sân ngoài trời trong khuôn viên xanh dành cho pickleball và giao lưu cuối tuần.',
            'contact_phone': '0901 234 569', 'opening_time': time(5, 30), 'closing_time': time(22),
            'amenities': ['Bãi xe', 'Khu nghỉ', 'Nước uống', 'Tủ đồ'],
            'image_urls': ['/images/sports/pickleball-court.webp'],
        },
        'field': {
            'name': 'Sân Pickleball Green Park', 'sport_type': 'pickleball', 'capacity': 4,
            'base_price': Decimal('240000'),
            'description': 'Mặt sân acrylic êm chân, vạch sân rõ nét và có khu vực nghỉ cho người chơi.',
            'amenities': ['Bãi xe', 'Khu nghỉ', 'Nước uống', 'Cho thuê vợt', 'Tủ đồ'],
            'image_url': '/images/sports/pickleball-court.webp',
            'rating': 4.9, 'review_count': 184, 'distance_km': 3.1,
        },
        'slots': (
            ('Ca sáng', time(6), time(8), 200000, 200000, 220000),
            ('Ca chiều', time(16), time(18), 250000, 250000, 270000),
            ('Ca tối', time(18), time(20), 280000, 280000, 300000),
        ),
    },
)


def seed_demo_db(session):
    if not settings.SEED_DEMO_DATA:
        return
    try:
        _lock_postgresql_seed(session)
        users = _seed_accounts(session)
        facilities, fields, slots = _seed_venues(session, users['owner'])
        bookings = _seed_bookings(session, users['customer'], facilities, fields, slots)
        _seed_payments(session, users['owner'], users['customer'], bookings)
        _seed_related_data(session, users['owner'], users['customer'], fields, bookings)
        session.commit()
        return users
    except Exception:
        session.rollback()
        raise


def _lock_postgresql_seed(session):
    if session.get_bind().dialect.name == 'postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': 734687542021})


def _seed_accounts(session):
    definitions = (
        (UserRole.SYSTEM_ADMIN.value, settings.SYSTEM_ADMIN_FULL_NAME, settings.SYSTEM_ADMIN_EMAIL, settings.SYSTEM_ADMIN_PASSWORD),
        (UserRole.OWNER.value, settings.OWNER_FULL_NAME, settings.OWNER_EMAIL, settings.OWNER_PASSWORD),
        (UserRole.CUSTOMER.value, 'SportHub Customer', settings.CUSTOMER_EMAIL, settings.CUSTOMER_PASSWORD),
    )
    users = {}
    for role, full_name, email, password in definitions:
        if not email or not password:
            raise RuntimeError(f'SEED_DEMO_DATA=true requires email and password for {role}')
        normalized_email = email.strip().lower()
        user = session.scalar(select(User).where(User.email == normalized_email))
        if user is not None:
            if user.role != role:
                raise RuntimeError(f'Demo account {normalized_email} has role {user.role}; expected {role}')
            if settings.SYNC_DEMO_PASSWORDS and not verify_password(password, user.hashed_password):
                user.hashed_password = get_password_hash(password)
        else:
            user = User(
                full_name=full_name.strip(), email=normalized_email,
                hashed_password=get_password_hash(password), role=role, is_active=True,
            )
            session.add(user)
            session.flush()
        users[role.lower()] = user
    return {'admin': users['system_admin'], 'owner': users['owner'], 'customer': users['customer']}


def _seed_venues(session, owner):
    facilities, fields, all_slots = [], [], []
    for definition in DEMO_VENUES:
        field_data = definition['field']
        field = session.scalar(select(Field).where(Field.owner_id == owner.id, Field.name == field_data['name']))
        facility = field.facility if field is not None and field.facility_id is not None else None
        if facility is None:
            facility = session.scalar(select(Facility).where(
                Facility.owner_id == owner.id, Facility.name == definition['facility']['name'],
            ))
        if facility is None:
            facility = Facility(
                owner_id=owner.id, cancellation_rules=default_cancellation_rules(),
                free_cancellation_minutes=360, status='APPROVED', is_active=True, approved_at=datetime.now(timezone.utc), sports=[definition['field']['sport_type']], **definition['facility'],
            )
            session.add(facility)
            session.flush()
        else:
            _fill_missing(facility, definition['facility'])
        if field is None:
            field = Field(
                owner_id=owner.id, facility_id=facility.id, location=facility.location,
                status='available', deposit_type='percentage', deposit_value=Decimal('30'),
                cancellation_policy='facility_rules', **field_data,
            )
            session.add(field)
            session.flush()
        else:
            if field.facility_id is None:
                field.facility_id = facility.id
            _fill_missing(field, field_data)
        venue_slots = _seed_slots(session, field, definition['slots'])
        facilities.append(facility)
        fields.append(field)
        all_slots.append(venue_slots)
    return facilities, fields, all_slots


def _fill_missing(item, values):
    for name, value in values.items():
        if getattr(item, name) in (None, '', []):
            setattr(item, name, value)


def _seed_slots(session, field, definitions):
    slots = []
    for name, start, end, price, weekday_price, weekend_price in definitions:
        slot = session.scalar(select(TimeSlot).where(
            TimeSlot.field_id == field.id,
            TimeSlot.start_time == start,
            TimeSlot.end_time == end,
        ))
        if slot is None:
            slot = TimeSlot(
                field_id=field.id, name=name, start_time=start, end_time=end,
                price=Decimal(price), weekday_price=Decimal(weekday_price),
                weekend_price=Decimal(weekend_price), is_active=True,
            )
            session.add(slot)
            session.flush()
        else:
            if slot.weekday_price is None:
                slot.weekday_price = Decimal(weekday_price)
            if slot.weekend_price is None:
                slot.weekend_price = Decimal(weekend_price)
        slots.append(slot)
    return slots


def _seed_bookings(session, customer, facilities, fields, slots):
    today = date.today()
    definitions = (
        ('DEMO-COMPLETED', 0, 0, today - timedelta(days=3), 'completed', 'full'),
        ('DEMO-CONFIRMED', 1, 1, today + timedelta(days=14), 'confirmed', 'deposit'),
        ('DEMO-PENDING', 2, 2, today + timedelta(days=15), 'pending_confirmation', 'deposit'),
    )
    bookings = {}
    for code, venue_index, slot_index, target_date, status, payment_kind in definitions:
        booking = session.scalar(select(Booking).where(Booking.booking_code == code))
        field, facility, slot = fields[venue_index], facilities[venue_index], slots[venue_index][slot_index]
        if booking is None:
            booking_date = _available_demo_date(session, field.id, slot.id, target_date, status)
            total = Decimal(slot.price)
            deposit = (total * Decimal(field.deposit_value or 0) / Decimal('100')).quantize(Decimal('0.01'))
            paid = total if payment_kind == 'full' else deposit
            booking = Booking(
                booking_code=code, customer_id=customer.id, facility_id=facility.id,
                facility_name_snapshot=facility.name, field_id=field.id, time_slot_id=slot.id,
                booking_date=booking_date, start_time_snapshot=slot.start_time,
                end_time_snapshot=slot.end_time, price_snapshot=total, total_amount=total,
                deposit_type='percentage', deposit_value=field.deposit_value,
                deposit_amount=deposit, paid_amount=paid,
                remaining_amount=max(total - paid, Decimal('0')),
                payment_status='paid' if paid >= total else 'partial',
                cancellation_policy=field.cancellation_policy,
                cancellation_refund_percent=field.cancellation_refund_percent,
                free_cancellation_minutes=facility.free_cancellation_minutes,
                status=status, note='SportHub AI demo booking.',
            )
            session.add(booking)
            session.flush()
        else:
            if booking.facility_id is None:
                booking.facility_id = facility.id
            if not booking.facility_name_snapshot:
                booking.facility_name_snapshot = facility.name
        bookings[code] = booking
    return bookings


def _available_demo_date(session, field_id, slot_id, target_date, status):
    if status not in ACTIVE_BOOKING_STATUSES:
        return target_date
    candidate = target_date
    for _ in range(31):
        conflict = session.scalar(select(Booking.id).where(
            Booking.field_id == field_id,
            Booking.time_slot_id == slot_id,
            Booking.booking_date == candidate,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        ))
        if conflict is None:
            return candidate
        candidate += timedelta(days=1)
    raise RuntimeError('No free date found for demo booking without changing production bookings')


def _seed_payments(session, owner, customer, bookings):
    definitions = (
        ('PAY-DEMO-001', 'DEMO-COMPLETED', PaymentType.REMAINING.value, EscrowStatus.RELEASED.value),
        ('PAY-DEMO-002', 'DEMO-CONFIRMED', PaymentType.DEPOSIT.value, EscrowStatus.HELD.value),
        ('PAY-DEMO-003', 'DEMO-PENDING', PaymentType.DEPOSIT.value, EscrowStatus.HELD.value),
    )
    for transaction_code, booking_code, payment_type, escrow_status in definitions:
        if session.scalar(select(Payment.id).where(Payment.transaction_code == transaction_code)) is not None:
            continue
        booking = bookings[booking_code]
        amount = Decimal(booking.total_amount) if payment_type == PaymentType.REMAINING.value else Decimal(booking.deposit_amount)
        session.add(Payment(
            booking_id=booking.id, customer_id=customer.id, owner_id=owner.id,
            transaction_code=transaction_code, amount=amount,
            total_amount=booking.total_amount, deposit_amount=booking.deposit_amount,
            remaining_amount=max(Decimal(booking.total_amount) - amount, Decimal('0')),
            paid_amount=amount, payment_status=PaymentStatus.PAID.value,
            payment_method='cash', payment_type=payment_type,
            status=PaymentStatus.PAID.value, escrow_status=escrow_status,
            paid_at=datetime.now(timezone.utc) - timedelta(days=3) if booking_code == 'DEMO-COMPLETED' else datetime.now(timezone.utc),
            confirmed_by=owner.id, verification_source='demo_seed',
            note='SportHub AI demo payment.',
        ))


def _seed_related_data(session, owner, customer, fields, bookings):
    completed = bookings['DEMO-COMPLETED']
    if session.scalar(select(Review.id).where(Review.booking_id == completed.id)) is None:
        session.add(Review(
            booking_id=completed.id, customer_id=customer.id, field_id=completed.field_id,
            rating=5, comment='Sân đẹp, hỗ trợ nhanh và đặt sân thuận tiện.',
            owner_reply='Cảm ơn bạn đã sử dụng SportHub!', replied_by=owner.id,
            replied_at=datetime.now(timezone.utc),
        ))
    if session.scalar(select(UserFavoriteField.id).where(
        UserFavoriteField.user_id == customer.id,
        UserFavoriteField.field_id == fields[1].id,
    )) is None:
        session.add(UserFavoriteField(user_id=customer.id, field_id=fields[1].id))
    if session.scalar(select(Invoice.id).where(Invoice.booking_id == completed.id)) is None:
        session.add(Invoice(
            invoice_number='INV-DEMO-001', booking_id=completed.id,
            customer_id=customer.id, owner_id=owner.id, booking_code=completed.booking_code,
            customer_name=customer.full_name, customer_email=customer.email,
            facility_name=completed.facility_name_snapshot, field_name=completed.field.name,
            booking_date=completed.booking_date, start_time=completed.start_time_snapshot,
            end_time=completed.end_time_snapshot, total_amount=completed.total_amount,
            deposit_amount=completed.deposit_amount,
            remaining_payment_amount=max(Decimal(completed.total_amount) - Decimal(completed.deposit_amount), Decimal('0')),
            refund_amount=Decimal('0'), net_received_amount=completed.total_amount,
            payment_methods='cash', paid_at=datetime.now(timezone.utc) - timedelta(days=3),
        ))
