import unittest

from sqlalchemy import create_engine, text

from app import models  # noqa: F401 - register all tables on Base.metadata
from app.database.base import Base
from app.database.migrations import migrate_cancelled_booking_balances, migrate_system_roles


class RoleMigrationTests(unittest.TestCase):
    def test_cancelled_booking_balances_are_normalized_without_touching_active_bookings(self):
        engine = create_engine('sqlite://')
        with engine.begin() as connection:
            connection.execute(text(
                'CREATE TABLE bookings ('
                'id INTEGER PRIMARY KEY, status VARCHAR(30) NOT NULL, '
                'remaining_amount NUMERIC(12,2) NOT NULL, '
                'additional_payment_required NUMERIC(12,2) NOT NULL)'
            ))
            connection.execute(text(
                "INSERT INTO bookings VALUES "
                "(1,'cancelled_by_customer',200000,50000),"
                "(2,'cancelled_by_owner',300000,0),"
                "(3,'confirmed',400000,100000)"
            ))

        migrate_cancelled_booking_balances(engine)
        migrate_cancelled_booking_balances(engine)

        with engine.connect() as connection:
            balances = connection.execute(text(
                'SELECT remaining_amount, additional_payment_required FROM bookings ORDER BY id'
            )).all()
        self.assertEqual([tuple(map(float, row)) for row in balances], [
            (0.0, 0.0),
            (0.0, 0.0),
            (400000.0, 100000.0),
        ])

    def test_legacy_accounts_are_preserved_and_normalized(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE users ADD COLUMN owner_id INTEGER NULL REFERENCES users(id)'))
            connection.execute(text("ALTER TABLE users ADD COLUMN management_permissions JSON NOT NULL DEFAULT '[]'"))
            for index, role in enumerate(('LEGACY_OPERATOR', 'OWNER_PENDING', 'ADMIN'), start=1):
                connection.execute(text(
                    'INSERT INTO users (full_name,email,hashed_password,role,is_active,created_at,updated_at,owner_id,management_permissions) '
                    "VALUES (:name,:email,:password,:role,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,99,'[]')"
                ), {'name': f'Legacy {index}', 'email': f'legacy{index}@test.local', 'password': 'unused', 'role': role})
        migrate_system_roles(engine)
        with engine.connect() as connection:
            roles = connection.execute(text('SELECT role FROM users ORDER BY id')).scalars().all()
            applications = connection.execute(text("SELECT COUNT(*) FROM owner_applications WHERE status='PENDING'")).scalar_one()
            owner_ids = connection.execute(text('SELECT owner_id FROM users ORDER BY id')).scalars().all()
        self.assertEqual(roles, ['CUSTOMER', 'CUSTOMER', 'SYSTEM_ADMIN'])
        self.assertEqual(applications, 1)
        self.assertEqual(owner_ids, [None, None, None])


if __name__ == '__main__':
    unittest.main()
