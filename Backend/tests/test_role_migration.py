import unittest

from sqlalchemy import create_engine, text

from app import models  # noqa: F401 - register all tables on Base.metadata
from app.database.base import Base
from app.database.migrations import migrate_system_roles


class RoleMigrationTests(unittest.TestCase):
    def test_legacy_accounts_are_preserved_and_normalized(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            for index, role in enumerate(('MANAGER', 'OWNER_PENDING', 'ADMIN'), start=1):
                connection.execute(text(
                    'INSERT INTO users (full_name,email,hashed_password,role,is_active,created_at,updated_at,owner_id,management_permissions) '
                    "VALUES (:name,:email,:password,:role,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,99,'[]')"
                ), {'name': f'Legacy {index}', 'email': f'legacy{index}@test.local', 'password': 'unused', 'role': role})
        migrate_system_roles(engine)
        with engine.connect() as connection:
            roles = connection.execute(text('SELECT role FROM users ORDER BY id')).scalars().all()
            applications = connection.execute(text("SELECT COUNT(*) FROM owner_applications WHERE status='PENDING'")).scalar_one()
            owner_ids = connection.execute(text('SELECT owner_id FROM users ORDER BY id')).scalars().all()
        self.assertEqual(roles, ['MANAGER', 'CUSTOMER', 'SYSTEM_ADMIN'])
        self.assertEqual(applications, 1)
        self.assertEqual(owner_ids, [99, None, None])


if __name__ == '__main__':
    unittest.main()
