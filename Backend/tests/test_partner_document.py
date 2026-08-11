import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.owner_application import OwnerApplication
from app.models.user import User, UserRole


JPEG = b'\xff\xd8\xff\xe0' + b'sporthub-private-document' + b'\xff\xd9'
PNG = b'\x89PNG\r\n\x1a\n' + b'sporthub-private-document' + b'IEND'


class PartnerDocumentTests(unittest.TestCase):
    def setUp(self):
        self.upload_dir = tempfile.TemporaryDirectory(); self.old_upload_dir = settings.PARTNER_DOCUMENT_DIR
        settings.PARTNER_DOCUMENT_DIR = Path(self.upload_dir.name).resolve()
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine); Base.metadata.create_all(self.engine)
        with self.Session() as db:
            users = [
                User(full_name='Customer A', email='doc.a@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Customer B', email='doc.b@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Owner', email='doc.owner@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
                User(full_name='Admin', email='doc.admin@test.local', hashed_password=get_password_hash('Admin@123456'), role=UserRole.SYSTEM_ADMIN.value),
                User(full_name='Manager', email='doc.manager@test.local', hashed_password=get_password_hash('Manager@123'), role='MANAGER'),
            ]
            db.add_all(users); db.commit(); self.ids = {user.email: user.id for user in users}
        def override_db():
            with self.Session() as db: yield db
        app.dependency_overrides[get_db] = override_db; self.client = TestClient(app)
        self.a = self.login('doc.a@test.local', 'Customer@123'); self.b = self.login('doc.b@test.local', 'Customer@123')
        self.owner = self.login('doc.owner@test.local', 'Owner@123456'); self.admin = self.login('doc.admin@test.local', 'Admin@123456')

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)
        settings.PARTNER_DOCUMENT_DIR = self.old_upload_dir; self.upload_dir.cleanup()

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password}); self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    @staticmethod
    def payload():
        return {'representative': {'name': 'Nguyễn Văn A', 'phone': '0901234567', 'email': 'doc.a@test.local', 'identity_number': '001234567890'}, 'venue': {'name': 'Cơ sở A', 'address': '1 Nguyễn Trãi', 'sports': ['Cầu lông'], 'description': 'Sân trong nhà'}, 'legal_confirmed': True}

    def upload(self, headers, content=JPEG, name='cccd.jpg', mime='image/jpeg'):
        return self.client.post('/auth/owner-application/document', headers=headers, files={'document': (name, content, mime)})

    def test_valid_upload_is_private_and_authorized(self):
        uploaded = self.upload(self.a); self.assertEqual(uploaded.status_code, 200, uploaded.text); self.assertTrue(uploaded.json()['has_document'])
        own = self.client.get('/auth/owner-application/document', headers=self.a); self.assertEqual(own.status_code, 200); self.assertEqual(own.content, JPEG); self.assertEqual(own.headers['cache-control'], 'private, no-store, max-age=0')
        application_id = uploaded.json()['id']
        self.assertEqual(self.client.get('/auth/owner-application/document', headers=self.b).status_code, 404)
        self.assertEqual(self.client.get(f'/admin/owner-applications/{application_id}/document', headers=self.b).status_code, 403)
        self.assertEqual(self.client.get(f'/admin/owner-applications/{application_id}/document', headers=self.owner).status_code, 403)
        manager = {'Authorization': f"Bearer {create_access_token({'sub': str(self.ids['doc.manager@test.local']), 'role': 'MANAGER'})}"}
        self.assertEqual(self.client.get(f'/admin/owner-applications/{application_id}/document', headers=manager).status_code, 403)
        admin = self.client.get(f'/admin/owner-applications/{application_id}/document', headers=self.admin); self.assertEqual(admin.status_code, 200); self.assertEqual(admin.content, JPEG)

    def test_invalid_type_size_and_missing_document_are_rejected(self):
        mismatch = self.upload(self.a, JPEG, 'fake.png', 'image/png'); self.assertEqual(mismatch.status_code, 415)
        invalid = self.upload(self.a, b'not-an-image', 'fake.jpg', 'image/jpeg'); self.assertEqual(invalid.status_code, 415)
        too_large = self.upload(self.a, b'x' * (settings.PARTNER_DOCUMENT_MAX_BYTES + 1), 'large.jpg', 'image/jpeg'); self.assertEqual(too_large.status_code, 413)
        missing = self.client.post('/auth/owner-application/submit', headers=self.b, json=self.payload()); self.assertEqual(missing.status_code, 422); self.assertEqual(self.client.get('/auth/me', headers=self.b).json()['role'], 'CUSTOMER')

    def test_more_info_replace_resubmit_approve_and_no_duplicate_approval(self):
        uploaded = self.upload(self.a); self.assertEqual(uploaded.status_code, 200)
        submitted = self.client.post('/auth/owner-application/submit', headers=self.a, json=self.payload()); self.assertEqual(submitted.status_code, 200, submitted.text); application_id = submitted.json()['id']
        self.assertEqual(self.client.get('/auth/me', headers=self.a).json()['role'], 'CUSTOMER')
        more = self.client.patch(f'/admin/owner-applications/{application_id}/review', headers=self.admin, json={'action': 'REQUEST_MORE_INFO', 'admin_note': 'Ảnh bị mờ, vui lòng chụp lại'}); self.assertEqual(more.status_code, 200)
        replaced = self.upload(self.a, PNG, 'cccd-moi.png', 'image/png'); self.assertEqual(replaced.status_code, 200); self.assertEqual(replaced.json()['document_mime'], 'image/png')
        resubmitted = self.client.post('/auth/owner-application/submit', headers=self.a, json=self.payload()); self.assertEqual(resubmitted.json()['status'], 'PENDING_REVIEW')
        approved = self.client.patch(f'/admin/owner-applications/{application_id}/review', headers=self.admin, json={'action': 'APPROVE'}); self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(self.client.post('/auth/login', json={'email': 'doc.a@test.local', 'password': 'Customer@123'}).json()['user']['role'], 'OWNER')
        self.assertEqual(self.client.patch(f'/admin/owner-applications/{application_id}/review', headers=self.admin, json={'action': 'APPROVE'}).status_code, 409)

    def test_admin_cannot_approve_legacy_pending_application_without_document(self):
        with self.Session() as db:
            item = OwnerApplication(customer_id=self.ids['doc.b@test.local'], status='PENDING_REVIEW', representative={}, venue={}, legal_confirmed=True)
            db.add(item); db.commit(); application_id = item.id
        response = self.client.patch(f'/admin/owner-applications/{application_id}/review', headers=self.admin, json={'action': 'APPROVE'})
        self.assertEqual(response.status_code, 409)


if __name__ == '__main__': unittest.main()
