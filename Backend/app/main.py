from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import admin, ai, auth, bookings, dashboard, facilities, favorites, fields, maintenance, management_customers, managers, operations, payments, public_courts, refunds, reviews, time_slots
from .core.config import settings
from .database.base import Base
from .database.seed import seed_db
from .database.migrations import migrate_deposit_payment_schema, migrate_empty_legacy_booking_schema, migrate_field_recommendation_columns, migrate_ownership_columns, migrate_partner_application_schema, migrate_professional_booking_schema, migrate_refund_workflow_schema, migrate_system_roles, migrate_user_profile_columns
from .database.session import SessionLocal, engine
from .models import AuditLog, Booking, BookingActivity, BookingComplaint, Facility, Field, FieldBlock, FieldMaintenance, Invoice, OwnerApplication, Payment, RefundRequest, Review, TimeSlot, User, UserFavoriteField  # noqa: F401 - registers metadata

@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate_empty_legacy_booking_schema(engine)
    migrate_field_recommendation_columns(engine)
    migrate_user_profile_columns(engine)
    migrate_ownership_columns(engine)
    migrate_system_roles(engine)
    migrate_deposit_payment_schema(engine)
    migrate_professional_booking_schema(engine)
    migrate_partner_application_schema(engine)
    Base.metadata.create_all(bind=engine)
    migrate_system_roles(engine)
    migrate_professional_booking_schema(engine)
    migrate_refund_workflow_schema(engine)
    with SessionLocal() as session:
        seed_db(session)
    # A newly seeded OWNER may not have existed during the schema migration above.
    migrate_ownership_columns(engine)
    yield

app = FastAPI(title=settings.PROJECT_NAME, version='1.0.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(facilities.router)
app.include_router(fields.router)
app.include_router(public_courts.router)
app.include_router(time_slots.router)
app.include_router(bookings.router)
app.include_router(management_customers.router)
app.include_router(managers.router)
app.include_router(maintenance.router)
app.include_router(payments.router)
app.include_router(refunds.router)
app.include_router(operations.router)
app.include_router(dashboard.router)
app.include_router(ai.router)
app.include_router(favorites.router)
app.include_router(reviews.router)

@app.get('/')
def read_root():
    return {'message': 'Welcome to SportHub AI API'}
