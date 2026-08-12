import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.migrations import migrate_partner_application_schema
from app.database.session import get_db
from app.main import app
from app.models.owner_application import OwnerApplication
from app.models.user import User, UserRole


class PartnerApplicationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            db.add_all([
                User(full_name='Admin', email='admin@partner.local', hashed_password=get_password_hash('Admin@123456'), role=UserRole.SYSTEM_ADMIN.value),
                User(full_name='Customer', email='customer@partner.local', phone='0901000001', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Other', email='other@partner.local', phone='0901000002', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Owner', email='owner@partner.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
            ])
            db.commit()
        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def headers(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    @staticmethod
    def payload(name='Sport Center'):
        return {
            'representative': {'name': 'Nguyen Van A', 'phone': '0901000001', 'email': 'customer@partner.local'},
            'venue': {'name': name, 'address': 'Thanh Xuan, Ha Noi', 'city': 'Ha Noi', 'district': 'Thanh Xuan', 'description': 'Muon kinh doanh san the thao'},
            'legal_confirmed': True,
        }

    def test_customer_submits_without_documents_and_stays_customer(self):
        customer = self.headers('customer@partner.local', 'Customer@123')
        draft = self.client.put('/auth/owner-application', headers=customer, json={**self.payload(), 'legal_confirmed': False})
        self.assertEqual(draft.status_code, 200, draft.text)
        self.assertEqual(draft.json()['status'], 'DRAFT')
        submitted = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload())
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()['status'], 'PENDING')
        self.assertNotIn('has_document', submitted.json())
        self.assertNotIn('identity_number', submitted.json()['representative'])
        self.assertEqual(self.client.get('/auth/me', headers=customer).json()['role'], 'CUSTOMER')
        self.assertEqual(self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).status_code, 409)

    def test_admin_approve_grants_owner(self):
        customer = self.headers('customer@partner.local', 'Customer@123')
        admin = self.headers('admin@partner.local', 'Admin@123456')
        item = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        approved = self.client.patch('/admin/owner-applications/' + str(item['id']) + '/review', headers=admin, json={'action': 'APPROVE'})
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()['status'], 'APPROVED')
        fresh = self.client.post('/auth/login', json={'email': 'customer@partner.local', 'password': 'Customer@123'}).json()['user']
        self.assertEqual(fresh['role'], 'OWNER')

    def test_reject_requires_reason_and_customer_can_edit_resubmit(self):
        customer = self.headers('customer@partner.local', 'Customer@123')
        admin = self.headers('admin@partner.local', 'Admin@123456')
        item = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        self.assertEqual(self.client.patch('/admin/owner-applications/' + str(item['id']) + '/review', headers=admin, json={'action': 'REJECT', 'admin_note': ' '}).status_code, 422)
        rejected = self.client.patch('/admin/owner-applications/' + str(item['id']) + '/review', headers=admin, json={'action': 'REJECT', 'admin_note': 'Thong tin lien he chua ro'})
        self.assertEqual(rejected.json()['status'], 'REJECTED')
        self.assertEqual(rejected.json()['rejection_reason'], 'Thong tin lien he chua ro')
        updated = self.payload('Sport Center Updated')
        resubmitted = self.client.post('/auth/owner-application/submit', headers=customer, json=updated)
        self.assertEqual(resubmitted.status_code, 200, resubmitted.text)
        self.assertEqual(resubmitted.json()['status'], 'PENDING')
        self.assertEqual(resubmitted.json()['venue']['name'], 'Sport Center Updated')

    def test_only_system_admin_can_review(self):
        customer = self.headers('customer@partner.local', 'Customer@123')
        owner = self.headers('owner@partner.local', 'Owner@123456')
        item = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        self.assertEqual(self.client.get('/admin/owner-applications', headers=customer).status_code, 403)
        self.assertEqual(self.client.patch('/admin/owner-applications/' + str(item['id']) + '/review', headers=owner, json={'action': 'APPROVE'}).status_code, 403)

    def test_pending_can_be_withdrawn_and_reapplied(self):
        customer = self.headers('customer@partner.local', 'Customer@123')
        item = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        withdrawn = self.client.post('/auth/owner-application/' + str(item['id']) + '/withdraw', headers=customer, json={'reason': 'Chua san sang'})
        self.assertEqual(withdrawn.json()['status'], 'WITHDRAWN')
        reapplied = self.client.post('/auth/owner-application/reapply', headers=customer)
        self.assertEqual(reapplied.status_code, 201, reapplied.text)
        self.assertEqual(reapplied.json()['status'], 'DRAFT')

    def test_migration_archives_legacy_document_metadata(self):
        engine = create_engine('sqlite://')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
            connection.execute(text('INSERT INTO users VALUES (1)'))
            connection.execute(text('''CREATE TABLE owner_applications (
                id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                status VARCHAR(20) NOT NULL, representative JSON NOT NULL, venue JSON NOT NULL,
                legal_confirmed BOOLEAN NOT NULL, rejection_reason TEXT NULL, admin_note TEXT NULL,
                document_path VARCHAR(500), document_mime VARCHAR(50), document_original_name VARCHAR(255),
                document_size INTEGER, document_uploaded_at DATETIME, reviewed_by INTEGER,
                submitted_at DATETIME, reviewed_at DATETIME, created_at DATETIME, updated_at DATETIME
            )'''))
            connection.execute(text("INSERT INTO owner_applications VALUES (1,1,'PENDING_REVIEW','{}','{}',1,NULL,NULL,'legacy.jpg','image/jpeg','cccd.jpg',12,CURRENT_TIMESTAMP,NULL,CURRENT_TIMESTAMP,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        migrate_partner_application_schema(engine)
        columns = {column['name'] for column in inspect(engine).get_columns('owner_applications')}
        self.assertNotIn('document_path', columns)
        with engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT status FROM owner_applications')).scalar_one(), 'PENDING')
            self.assertEqual(connection.execute(text('SELECT document_path FROM owner_application_document_archive')).scalar_one(), 'legacy.jpg')


if __name__ == '__main__':
    unittest.main()