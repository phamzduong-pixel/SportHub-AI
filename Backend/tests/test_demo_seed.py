import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database.base import Base
from app.database.demo_seed import seed_demo_db
from app.models import Booking, Facility, Field, Invoice, Payment, ProductCatalogItem, Review, TimeSlot, User, UserFavoriteField


class DemoSeedTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            name: getattr(settings, name)
            for name in (
                'SEED_DEMO_DATA', 'SYNC_DEMO_PASSWORDS',
                'SYSTEM_ADMIN_EMAIL', 'SYSTEM_ADMIN_PASSWORD',
                'OWNER_EMAIL', 'OWNER_PASSWORD', 'CUSTOMER_EMAIL', 'CUSTOMER_PASSWORD',
            )
        }
        settings.SEED_DEMO_DATA = True
        settings.SYNC_DEMO_PASSWORDS = False
        settings.SYSTEM_ADMIN_EMAIL = 'admin@seed.test'
        settings.SYSTEM_ADMIN_PASSWORD = 'admin-seed-password'
        settings.OWNER_EMAIL = 'owner@seed.test'
        settings.OWNER_PASSWORD = 'owner-seed-password'
        settings.CUSTOMER_EMAIL = 'customer@seed.test'
        settings.CUSTOMER_PASSWORD = 'customer-seed-password'
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def tearDown(self):
        for name, value in self.original.items():
            setattr(settings, name, value)

    def test_seed_is_complete_and_idempotent(self):
        with self.Session() as session:
            seed_demo_db(session)
            first = self._counts(session)
            first_catalog_count = session.scalar(select(func.count(ProductCatalogItem.id)))
            missing_price = session.scalar(select(TimeSlot).where(TimeSlot.name == 'Ca 08:00'))
            missing_price.weekend_price = None
            removable = session.scalar(select(TimeSlot).where(TimeSlot.name == 'Ca chiều'))
            session.delete(removable)
            session.commit()
            seed_demo_db(session)
            second = self._counts(session)
            second_catalog_count = session.scalar(select(func.count(ProductCatalogItem.id)))
            self.assertEqual(first, second)
            self.assertEqual(first, (3, 3, 3, 9, 3, 3, 1, 1, 1))
            self.assertEqual(first_catalog_count, 47)
            self.assertEqual(second_catalog_count, first_catalog_count)
            self.assertEqual(session.scalar(select(func.count(Field.id)).where(Field.facility_id.is_(None))), 0)
            self.assertEqual(session.scalar(select(func.count(TimeSlot.id)).where(
                TimeSlot.weekday_price.is_(None) | TimeSlot.weekend_price.is_(None)
            )), 0)

    def test_catalog_is_seeded_without_demo_accounts(self):
        settings.SEED_DEMO_DATA = False
        with self.Session() as session:
            seed_demo_db(session)
            seed_demo_db(session)
            self.assertEqual(session.scalar(select(func.count(ProductCatalogItem.id))), 47)
            self.assertEqual(session.scalar(select(func.count(User.id))), 0)

    @staticmethod
    def _counts(session):
        models = (User, Facility, Field, TimeSlot, Booking, Payment, Review, UserFavoriteField, Invoice)
        return tuple(session.scalar(select(func.count(model.id))) for model in models)


if __name__ == '__main__':
    unittest.main()
