import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.database.demo_seed import DEMO_BOOKING_CODES, DEMO_VENUES, seed_demo_db  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import Booking, Field, Invoice, Payment, Review, TimeSlot, User, UserFavoriteField  # noqa: E402


def main():
    if not settings.SEED_DEMO_DATA:
        raise SystemExit('SEED_DEMO_DATA must be true before running the demo seed.')
    with SessionLocal() as session:
        users = seed_demo_db(session)
        owner_id = users['owner'].id
        field_names = tuple(item['field']['name'] for item in DEMO_VENUES)
        account_emails = (settings.CUSTOMER_EMAIL.lower(), settings.OWNER_EMAIL.lower(), settings.SYSTEM_ADMIN_EMAIL.lower())
        payment_codes = ('PAY-DEMO-001', 'PAY-DEMO-002', 'PAY-DEMO-003')
        counts = {
            'accounts': session.scalar(select(func.count(User.id)).where(User.email.in_(account_emails))) or 0,
            'facilities': session.scalar(select(func.count(func.distinct(Field.facility_id))).where(Field.owner_id == owner_id, Field.name.in_(field_names))) or 0,
            'fields': session.scalar(select(func.count(Field.id)).where(Field.owner_id == owner_id, Field.name.in_(field_names))) or 0,
            'time_slots': session.scalar(select(func.count(TimeSlot.id)).join(Field).where(Field.owner_id == owner_id, Field.name.in_(field_names))) or 0,
            'demo_bookings': session.scalar(select(func.count(Booking.id)).where(Booking.booking_code.in_(DEMO_BOOKING_CODES))) or 0,
            'payments': session.scalar(select(func.count(Payment.id)).where(Payment.transaction_code.in_(payment_codes))) or 0,
            'reviews': session.scalar(select(func.count(Review.id)).join(Booking).where(Booking.booking_code.in_(DEMO_BOOKING_CODES))) or 0,
            'favorites': session.scalar(select(func.count(UserFavoriteField.id)).where(UserFavoriteField.user_id == users['customer'].id, UserFavoriteField.field_id.in_(select(Field.id).where(Field.name.in_(field_names))))) or 0,
            'invoices': session.scalar(select(func.count(Invoice.id)).join(Booking).where(Booking.booking_code.in_(DEMO_BOOKING_CODES))) or 0,
        }
    print('Demo seed complete:', ', '.join(f'{key}={value}' for key, value in counts.items()))


if __name__ == '__main__':
    main()
