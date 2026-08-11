import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.database.migrations import migrate_partner_application_schema
from app.main import app
from app.models.owner_application import OwnerApplication
from app.models.user import User, UserRole


class PartnerApplicationTests(unittest.TestCase):
    def setUp(self):
        self.upload_dir = tempfile.TemporaryDirectory(); self.old_upload_dir = settings.PARTNER_DOCUMENT_DIR
        settings.PARTNER_DOCUMENT_DIR = Path(self.upload_dir.name).resolve()
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            db.add_all([
                User(full_name='System Admin', email='admin@partner.local', hashed_password=get_password_hash('Admin@123456'), role=UserRole.SYSTEM_ADMIN.value),
                User(full_name='Customer A', email='customer.a@partner.local', phone='0901000001', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Customer B', email='customer.b@partner.local', phone='0901000002', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Existing Owner', email='owner@partner.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
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
        settings.PARTNER_DOCUMENT_DIR = self.old_upload_dir; self.upload_dir.cleanup()

    def headers(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def upload_document(self, headers):
        image = b'\xff\xd8\xff\xe0' + b'partner-document' + b'\xff\xd9'
        response = self.client.post('/auth/owner-application/document', headers=headers, files={'document': ('cccd.jpg', image, 'image/jpeg')})
        self.assertEqual(response.status_code, 200, response.text)

    @staticmethod
    def payload(name='Sân Đối Tác'):
        return {
            'representative': {'name': 'Nguyễn Văn A', 'phone': '0901000001', 'email': 'customer.a@partner.local', 'identity_number': '001234567890'},
            'venue': {'name': name, 'address': '1 Nguyễn Trãi', 'city': 'Hà Nội', 'district': 'Thanh Xuân', 'phone': '0901000001', 'sports': ['Cầu lông'], 'description': 'Cơ sở thể thao trong nhà'},
            'legal_confirmed': True,
        }

    def test_customer_can_save_reopen_and_submit_draft(self):
        customer = self.headers('customer.a@partner.local', 'Customer@123')
        draft = self.client.put('/auth/owner-application', headers=customer, json={**self.payload(), 'legal_confirmed': False})
        self.assertEqual(draft.status_code, 200, draft.text)
        self.assertEqual(draft.json()['status'], 'DRAFT')
        reopened = self.client.get('/auth/owner-application', headers=customer)
        self.assertEqual(reopened.json()['venue']['name'], 'Sân Đối Tác')
        self.upload_document(customer)
        submitted = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload())
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()['status'], 'PENDING_REVIEW')
        self.assertEqual(self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).status_code, 409)
        self.assertEqual(self.client.get('/auth/me', headers=customer).json()['role'], 'CUSTOMER')

    def test_required_data_and_admin_authorization(self):
        customer = self.headers('customer.a@partner.local', 'Customer@123')
        owner = self.headers('owner@partner.local', 'Owner@123456')
        invalid = self.payload(); invalid['venue']['sports'] = []
        self.assertEqual(self.client.post('/auth/owner-application/submit', headers=customer, json=invalid).status_code, 422)
        self.upload_document(customer)
        created = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        self.assertEqual(self.client.get('/admin/owner-applications', headers=customer).status_code, 403)
        self.assertEqual(self.client.patch(f"/admin/owner-applications/{created['id']}/review", headers=owner, json={'action': 'APPROVE'}).status_code, 403)
        self.assertEqual(self.client.get(f"/admin/owner-applications/{created['id']}", headers=customer).status_code, 403)

    def test_submit_auth_owner_duplicate_and_database_rollback(self):
        payload = self.payload()
        self.assertEqual(self.client.post('/auth/owner-application/submit', json=payload).status_code, 401)
        owner = self.headers('owner@partner.local', 'Owner@123456')
        self.assertEqual(self.client.post('/auth/owner-application/submit', headers=owner, json=payload).status_code, 409)
        customer = self.headers('customer.a@partner.local', 'Customer@123')
        self.upload_document(customer)
        with patch.object(self.Session.class_, 'commit', side_effect=SQLAlchemyError('simulated database failure')):
            failed = self.client.post('/auth/owner-application/submit', headers=customer, json=payload)
        self.assertEqual(failed.status_code, 500, failed.text)
        self.assertNotIn('simulated database failure', failed.text)
        with self.Session() as db:
            application = db.scalar(select(OwnerApplication).where(OwnerApplication.customer_id == 2))
            self.assertEqual(application.status, 'DRAFT')

    def test_more_info_resubmit_then_approve_same_user(self):
        customer = self.headers('customer.a@partner.local', 'Customer@123')
        admin = self.headers('admin@partner.local', 'Admin@123456')
        self.upload_document(customer)
        created = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        missing_note = self.client.patch(f"/admin/owner-applications/{created['id']}/review", headers=admin, json={'action': 'REQUEST_MORE_INFO'})
        self.assertEqual(missing_note.status_code, 422)
        more = self.client.patch(f"/admin/owner-applications/{created['id']}/review", headers=admin, json={'action': 'REQUEST_MORE_INFO', 'admin_note': 'Bổ sung ảnh giấy phép kinh doanh'})
        self.assertEqual(more.status_code, 200, more.text)
        self.assertEqual(more.json()['status'], 'NEED_MORE_INFO')
        resubmitted = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload('Sân Đối Tác Cập Nhật'))
        self.assertEqual(resubmitted.json()['status'], 'PENDING_REVIEW')
        approved = self.client.patch(f"/admin/owner-applications/{created['id']}/review", headers=admin, json={'action': 'APPROVE', 'admin_note': 'Hồ sơ hợp lệ'})
        self.assertEqual(approved.status_code, 200, approved.text)
        fresh = self.client.post('/auth/login', json={'email': 'customer.a@partner.local', 'password': 'Customer@123'}).json()['user']
        self.assertEqual(fresh['role'], 'OWNER')
        self.assertEqual(fresh['roles'], ['CUSTOMER', 'OWNER'])
        self.assertEqual(fresh['id'], created['customer_id'])
        owner_customer = self.headers('customer.a@partner.local', 'Customer@123')
        self.assertEqual(self.client.get('/facilities', headers=owner_customer).status_code, 200)
        self.assertEqual(self.client.get('/favorites', headers=owner_customer).status_code, 200)
        self.assertEqual(self.client.get('/bookings/my', headers=owner_customer).status_code, 200)
        repeated = self.client.patch(f"/admin/owner-applications/{created['id']}/review", headers=admin, json={'action': 'APPROVE'})
        self.assertEqual(repeated.status_code, 409)
        with self.Session() as db:
            self.assertEqual(db.scalar(select(func.count(User.id)).where(User.email == 'customer.a@partner.local')), 1)
            self.assertEqual(db.scalar(select(func.count(OwnerApplication.id)).where(OwnerApplication.customer_id == created['customer_id'])), 1)

    def test_reject_requires_reason_and_customer_can_resubmit(self):
        customer = self.headers('customer.a@partner.local', 'Customer@123')
        admin = self.headers('admin@partner.local', 'Admin@123456')
        self.upload_document(customer)
        created = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        self.assertEqual(self.client.patch(f"/admin/owner-applications/{created['id']}/review", headers=admin, json={'action': 'REJECT', 'admin_note': '  '}).status_code, 422)
        rejected = self.client.patch(f"/admin/owner-applications/{created['id']}/review", headers=admin, json={'action': 'REJECT', 'admin_note': 'Thông tin cơ sở chưa thể xác minh'})
        self.assertEqual(rejected.json()['status'], 'REJECTED')
        self.assertEqual(rejected.json()['rejection_reason'], 'Thông tin cơ sở chưa thể xác minh')
        self.assertEqual(self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload('Cơ sở đã xác minh')).json()['status'], 'PENDING_REVIEW')


    def test_customer_can_withdraw_pending_and_reapply_without_losing_history(self):
        customer = self.headers('customer.a@partner.local', 'Customer@123')
        self.upload_document(customer)
        submitted = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        withdrawn = self.client.post(
            f"/auth/owner-application/{submitted['id']}/withdraw", headers=customer,
            json={'reason': 'Tam thoi chua co nhu cau'},
        )
        self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
        self.assertEqual(withdrawn.json()['status'], 'WITHDRAWN')
        self.assertEqual(withdrawn.json()['withdraw_reason'], 'Tam thoi chua co nhu cau')
        self.assertIsNotNone(withdrawn.json()['withdrawn_at'])
        reapplied = self.client.post('/auth/owner-application/reapply', headers=customer)
        self.assertEqual(reapplied.status_code, 201, reapplied.text)
        self.assertEqual(reapplied.json()['status'], 'DRAFT')
        self.assertNotEqual(reapplied.json()['id'], submitted['id'])
        with self.Session() as db:
            rows = db.scalars(select(OwnerApplication).where(OwnerApplication.customer_id == submitted['customer_id']).order_by(OwnerApplication.id)).all()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].status, 'WITHDRAWN')
            self.assertEqual(rows[0].venue['name'], self.payload()['venue']['name'])

    def test_customer_can_withdraw_need_more_info(self):
        customer = self.headers('customer.a@partner.local', 'Customer@123')
        admin = self.headers('admin@partner.local', 'Admin@123456')
        self.upload_document(customer)
        submitted = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        more = self.client.patch(
            f"/admin/owner-applications/{submitted['id']}/review", headers=admin,
            json={'action': 'REQUEST_MORE_INFO', 'admin_note': 'Vui long bo sung giay phep'},
        )
        self.assertEqual(more.status_code, 200, more.text)
        withdrawn = self.client.post(f"/auth/owner-application/{submitted['id']}/withdraw", headers=customer, json={'reason': None})
        self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
        self.assertEqual(withdrawn.json()['status'], 'WITHDRAWN')

    def test_withdraw_rejects_approved_and_foreign_applications(self):
        customer = self.headers('customer.a@partner.local', 'Customer@123')
        other = self.headers('customer.b@partner.local', 'Customer@123')
        admin = self.headers('admin@partner.local', 'Admin@123456')
        self.upload_document(customer)
        submitted = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        foreign = self.client.post(f"/auth/owner-application/{submitted['id']}/withdraw", headers=other, json={})
        self.assertEqual(foreign.status_code, 404)
        approved = self.client.patch(f"/admin/owner-applications/{submitted['id']}/review", headers=admin, json={'action': 'APPROVE'})
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(self.client.post(f"/auth/owner-application/{submitted['id']}/withdraw", headers=customer, json={}).status_code, 403)

    def test_withdrawn_application_cannot_be_approved_from_stale_admin_view(self):
        customer = self.headers('customer.a@partner.local', 'Customer@123')
        admin = self.headers('admin@partner.local', 'Admin@123456')
        self.upload_document(customer)
        submitted = self.client.post('/auth/owner-application/submit', headers=customer, json=self.payload()).json()
        stale_admin_copy = self.client.get(f"/admin/owner-applications/{submitted['id']}", headers=admin)
        self.assertEqual(stale_admin_copy.json()['status'], 'PENDING_REVIEW')
        self.assertEqual(self.client.post(f"/auth/owner-application/{submitted['id']}/withdraw", headers=customer, json={}).status_code, 200)
        approve = self.client.patch(f"/admin/owner-applications/{submitted['id']}/review", headers=admin, json={'action': 'APPROVE'})
        self.assertEqual(approve.status_code, 409)
        with self.Session() as db:
            self.assertEqual(db.get(OwnerApplication, submitted['id']).status, 'WITHDRAWN')

    def test_legacy_unique_customer_schema_is_migrated_without_data_loss(self):
        engine = create_engine('sqlite://')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
            connection.execute(text('INSERT INTO users (id) VALUES (1)'))
            connection.execute(text('''CREATE TABLE owner_applications (
                id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                status VARCHAR(20) NOT NULL, representative JSON NOT NULL, venue JSON NOT NULL,
                legal_confirmed BOOLEAN NOT NULL, rejection_reason TEXT NULL, reviewed_by INTEGER NULL,
                submitted_at DATETIME NULL, reviewed_at DATETIME NULL, updated_at DATETIME NULL
            )'''))
            connection.execute(text("INSERT INTO owner_applications VALUES (1,1,'PENDING','{}','{}',1,NULL,NULL,CURRENT_TIMESTAMP,NULL,CURRENT_TIMESTAMP)"))
        migrate_partner_application_schema(engine)
        inspector = inspect(engine)
        self.assertFalse(any(set(item.get('column_names') or []) == {'customer_id'} for item in inspector.get_unique_constraints('owner_applications')))
        self.assertIn('withdrawn_at', {column['name'] for column in inspector.get_columns('owner_applications')})
        with engine.begin() as connection:
            self.assertEqual(connection.execute(text('SELECT status FROM owner_applications WHERE id=1')).scalar_one(), 'PENDING_REVIEW')
            connection.execute(text("INSERT INTO owner_applications (id,customer_id,status,representative,venue,legal_confirmed,created_at,updated_at) VALUES (2,1,'DRAFT','{}','{}',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM owner_applications WHERE customer_id=1')).scalar_one(), 2)


if __name__ == '__main__':
    unittest.main()
