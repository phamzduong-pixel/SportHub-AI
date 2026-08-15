import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.database.migrations import migrate_facility_approval_schema
from app.main import app
from app.models.facility import FacilityDocument, FacilityImage
from app.models.user import User, UserRole


JPEG = b'\xff\xd8\xff\xe0facility-image\xff\xd9'
PDF = b'%PDF-1.4\nfacility document\n%%EOF'


class FacilityApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_image = settings.FACILITY_IMAGE_DIR; self.old_private = settings.FACILITY_PRIVATE_DIR
        settings.FACILITY_IMAGE_DIR = Path(self.temp.name) / 'images'
        settings.FACILITY_PRIVATE_DIR = Path(self.temp.name) / 'private'
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            db.add_all([
                User(full_name='Admin', email='admin@facility.local', hashed_password=get_password_hash('Admin@123456'), role=UserRole.SYSTEM_ADMIN.value),
                User(full_name='Owner A', email='a@facility.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
                User(full_name='Owner B', email='b@facility.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
                User(full_name='Customer', email='customer@facility.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
            ])
            db.commit()
        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.admin = self.login('admin@facility.local', 'Admin@123456')
        self.owner = self.login('a@facility.local', 'Owner@123456')
        self.other = self.login('b@facility.local', 'Owner@123456')
        self.customer = self.login('customer@facility.local', 'Customer@123')

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)
        settings.FACILITY_IMAGE_DIR = self.old_image; settings.FACILITY_PRIVATE_DIR = self.old_private
        self.temp.cleanup()

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    @staticmethod
    def payload(name='SportHub Center'):
        return {'name': name, 'location': '123 Nguyen Trai, Thanh Xuan', 'description': 'Co so the thao trong nha', 'contact_phone': '0901234567', 'contact_email': 'venue@example.com', 'city': 'Ha Noi', 'district': 'Thanh Xuan', 'opening_time': '06:00', 'closing_time': '22:00', 'sports': ['Cầu lông', 'Pickleball'], 'amenities': [], 'image_urls': [], 'free_cancellation_minutes': 360}

    def create_complete(self):
        created = self.client.post('/facilities', headers=self.owner, json=self.payload())
        self.assertEqual(created.status_code, 201, created.text)
        facility_id = created.json()['id']
        image = self.client.post('/facilities/' + str(facility_id) + '/images', headers=self.owner, data={'category': 'COVER'}, files={'image': ('cover.jpg', JPEG, 'image/jpeg')})
        self.assertEqual(image.status_code, 200, image.text)
        document = self.client.post('/facilities/' + str(facility_id) + '/documents', headers=self.owner, data={'document_type': 'BUSINESS_REGISTRATION', 'document_name': 'Giay phep kinh doanh', 'document_number': 'GPKD-001'}, files={'document': ('license.pdf', PDF, 'application/pdf')})
        self.assertEqual(document.status_code, 200, document.text)
        return facility_id

    def test_full_approve_flow_and_customer_visibility(self):
        self.assertEqual(self.client.post('/facilities', headers=self.customer, json=self.payload()).status_code, 403)
        facility_id = self.create_complete()
        self.assertEqual(self.client.get('/fields', headers=self.customer).json()['total'], 0)
        submitted = self.client.post('/facilities/' + str(facility_id) + '/submit', headers=self.owner)
        self.assertEqual(submitted.status_code, 200, submitted.text); self.assertEqual(submitted.json()['status'], 'PENDING_APPROVAL')
        admin_notifications = self.client.get('/notifications', headers=self.admin).json()['items']
        self.assertIn('FACILITY_APPLICATION_SUBMITTED', [item['type'] for item in admin_notifications])
        self.assertEqual(self.client.put('/facilities/' + str(facility_id), headers=self.owner, json=self.payload()).status_code, 409)
        self.assertEqual(self.client.patch('/admin/facility-applications/' + str(facility_id) + '/review', headers=self.owner, json={'action': 'APPROVE'}).status_code, 403)
        detail = self.client.get('/admin/facility-applications/' + str(facility_id), headers=self.admin)
        self.assertEqual(detail.status_code, 200, detail.text); self.assertEqual(len(detail.json()['documents']), 1)
        approved = self.client.patch('/admin/facility-applications/' + str(facility_id) + '/review', headers=self.admin, json={'action': 'APPROVE'})
        self.assertEqual(approved.status_code, 200, approved.text); self.assertEqual(approved.json()['status'], 'APPROVED')
        owner_notifications = self.client.get('/notifications', headers=self.owner).json()['items']
        self.assertIn('FACILITY_APPROVED', [item['type'] for item in owner_notifications])
        field = self.client.post('/fields', headers=self.owner, json={'facility_id': facility_id, 'name': 'Court 1', 'sport_type': 'Cầu lông', 'description': 'Court', 'location': 'ignored', 'capacity': 4, 'base_price': 200000, 'status': 'available', 'amenities': []})
        self.assertEqual(field.status_code, 201, field.text)
        self.assertEqual(self.client.get('/fields', headers=self.customer).json()['total'], 1)

    def test_reject_reason_resubmit_isolation_and_private_files(self):
        facility_id = self.create_complete()
        self.client.post('/facilities/' + str(facility_id) + '/submit', headers=self.owner)
        self.assertEqual(self.client.patch('/admin/facility-applications/' + str(facility_id) + '/review', headers=self.admin, json={'action': 'REJECT'}).status_code, 422)
        rejected = self.client.patch('/admin/facility-applications/' + str(facility_id) + '/review', headers=self.admin, json={'action': 'REJECT', 'reason': 'Can bo sung thong tin bien hieu'})
        self.assertEqual(rejected.json()['status'], 'REJECTED')
        notification = self.client.get('/notifications', headers=self.owner).json()['items'][0]
        self.assertEqual(notification['type'], 'FACILITY_REJECTED')
        self.assertIn('Can bo sung thong tin bien hieu', notification['message'])
        own = self.client.get('/facilities/' + str(facility_id), headers=self.owner)
        self.assertEqual(own.json()['rejection_reason'], 'Can bo sung thong tin bien hieu')
        self.assertEqual(self.client.get('/facilities/' + str(facility_id), headers=self.other).status_code, 404)
        document_id = own.json()['documents'][0]['id']
        self.assertEqual(self.client.get('/facilities/' + str(facility_id) + '/documents/' + str(document_id) + '/content', headers=self.customer).status_code, 404)
        updated_payload = self.payload('SportHub Center Updated')
        self.assertEqual(self.client.put('/facilities/' + str(facility_id), headers=self.owner, json=updated_payload).status_code, 200)
        self.assertEqual(self.client.post('/facilities/' + str(facility_id) + '/submit', headers=self.owner).json()['status'], 'PENDING_APPROVAL')

    def test_pending_and_suspended_facilities_cannot_receive_booking_or_ai_visibility(self):
        facility_id = self.create_complete()
        field_payload = {'facility_id': facility_id, 'name': 'Court hidden', 'sport_type': 'Pickleball', 'description': 'Court', 'location': 'ignored', 'capacity': 4, 'base_price': 200000, 'status': 'available', 'amenities': []}
        self.assertEqual(self.client.post('/fields', headers=self.owner, json=field_payload).status_code, 409)
        self.client.post('/facilities/' + str(facility_id) + '/submit', headers=self.owner)
        self.client.patch('/admin/facility-applications/' + str(facility_id) + '/review', headers=self.admin, json={'action': 'APPROVE'})
        field = self.client.post('/fields', headers=self.owner, json=field_payload).json()
        suspended = self.client.patch('/admin/facility-applications/' + str(facility_id) + '/review', headers=self.admin, json={'action': 'SUSPEND', 'reason': 'Tam ngung de kiem tra'})
        self.assertEqual(suspended.json()['status'], 'SUSPENDED')
        self.assertEqual(self.client.get('/public/courts/' + str(field['id'])).status_code, 404)
        self.assertEqual(self.client.get('/fields', headers=self.customer).json()['total'], 0)

    def test_document_validation_duplicate_and_dangerous_filename(self):
        facility_id = self.create_complete()
        metadata = {'document_type': 'BUSINESS_REGISTRATION', 'document_name': 'Dang ky kinh doanh', 'document_number': 'GPKD-001'}
        duplicate = self.client.post('/facilities/' + str(facility_id) + '/documents', headers=self.owner, data=metadata, files={'document': ('copy.pdf', PDF, 'application/pdf')})
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        executable_name = self.client.post('/facilities/' + str(facility_id) + '/documents', headers=self.owner, data=metadata, files={'document': ('danger.exe', PDF, 'application/pdf')})
        self.assertEqual(executable_name.status_code, 415, executable_name.text)
        missing_number = self.client.post('/facilities/' + str(facility_id) + '/documents', headers=self.owner, data={'document_type': 'OTHER', 'document_name': 'Bo sung'}, files={'document': ('other.pdf', PDF, 'application/pdf')})
        self.assertEqual(missing_number.status_code, 422, missing_number.text)

        blank_name = self.client.post('/facilities/' + str(facility_id) + '/documents', headers=self.owner, data={'document_type': 'OTHER', 'document_name': '   ', 'document_number': 'OTHER-001'}, files={'document': ('blank-name.pdf', PDF + b'blank', 'application/pdf')})
        self.assertEqual(blank_name.status_code, 422, blank_name.text)
        self.assertIn('Tên giấy tờ không được để trống', blank_name.json()['detail'])

        trimmed = self.client.post('/facilities/' + str(facility_id) + '/documents', headers=self.owner, data={'document_type': 'OTHER', 'document_name': '  Giay phep bo sung  ', 'document_number': 'OTHER-002'}, files={'document': ('supplement.pdf', PDF + b'supplement', 'application/pdf')})
        self.assertEqual(trimmed.status_code, 200, trimmed.text)
        self.assertEqual(trimmed.json()['documents'][-1]['document_name'], 'Giay phep bo sung')

    def test_submit_reports_only_the_actual_missing_fields(self):
        created = self.client.post('/facilities', headers=self.owner, json=self.payload())
        self.assertEqual(created.status_code, 201, created.text)
        facility_id = created.json()['id']

        missing_media = self.client.post(f'/facilities/{facility_id}/submit', headers=self.owner)
        self.assertEqual(missing_media.status_code, 422, missing_media.text)
        detail = missing_media.json()['detail']
        self.assertIn('Hồ sơ chưa hoàn tất: thiếu', detail)
        self.assertIn('Ảnh đại diện cơ sở', detail)
        self.assertIn('Giấy phép/Đăng ký kinh doanh', detail)
        self.assertNotIn('Tên cơ sở', detail)
        self.assertNotIn('Số điện thoại', detail)

        image = self.client.post(f'/facilities/{facility_id}/images', headers=self.owner, data={'category': 'COVER'}, files={'image': ('cover.jpg', JPEG, 'image/jpeg')})
        self.assertEqual(image.status_code, 200, image.text)
        missing_document = self.client.post(f'/facilities/{facility_id}/submit', headers=self.owner)
        self.assertEqual(missing_document.status_code, 422, missing_document.text)
        self.assertIn('Giấy phép/Đăng ký kinh doanh', missing_document.json()['detail'])
        self.assertNotIn('Ảnh đại diện cơ sở', missing_document.json()['detail'])

    def test_facility_phone_requires_ten_digits_starting_with_zero(self):
        for phone in ('901234567', '1901234567', '090123456', '09012345678', '0901 234 567', '0901-234-567', '+84901234567', '09012abc67'):
            with self.subTest(phone=phone):
                invalid = self.client.post('/facilities', headers=self.owner, json={**self.payload(), 'contact_phone': phone})
                self.assertEqual(invalid.status_code, 422, invalid.text)
                self.assertIn('10 chữ số', invalid.text)

        valid = self.client.post('/facilities', headers=self.owner, json={**self.payload(), 'contact_phone': '0987654321'})
        self.assertEqual(valid.status_code, 201, valid.text)
        self.assertEqual(valid.json()['contact_phone'], '0987654321')

    def test_owner_can_delete_only_own_draft_and_files_are_cleaned(self):
        facility_id = self.create_complete()
        with self.Session() as db:
            image_path = settings.FACILITY_IMAGE_DIR / db.query(FacilityImage).filter_by(facility_id=facility_id).one().file_path
            document_path = settings.FACILITY_PRIVATE_DIR / db.query(FacilityDocument).filter_by(facility_id=facility_id).one().file_path
        self.assertTrue(image_path.is_file()); self.assertTrue(document_path.is_file())

        endpoint = '/facilities/' + str(facility_id) + '/draft'
        self.assertEqual(self.client.delete(endpoint, headers=self.other).status_code, 404)
        self.assertEqual(self.client.delete(endpoint, headers=self.customer).status_code, 403)
        self.assertEqual(self.client.delete(endpoint, headers=self.admin).status_code, 403)
        self.assertEqual(self.client.delete(endpoint, headers=self.owner).status_code, 204)
        self.assertEqual(self.client.get('/facilities/' + str(facility_id), headers=self.owner).status_code, 404)
        self.assertFalse(image_path.exists()); self.assertFalse(document_path.exists())

    def test_submitted_approved_and_rejected_facilities_cannot_use_delete_draft_api(self):
        pending_id = self.create_complete()
        self.client.post('/facilities/' + str(pending_id) + '/submit', headers=self.owner)
        endpoint = '/facilities/' + str(pending_id) + '/draft'
        self.assertEqual(self.client.delete(endpoint, headers=self.owner).status_code, 409)
        self.client.patch('/admin/facility-applications/' + str(pending_id) + '/review', headers=self.admin, json={'action': 'APPROVE'})
        self.assertEqual(self.client.delete(endpoint, headers=self.owner).status_code, 409)

        rejected_id = self.create_complete()
        self.client.post('/facilities/' + str(rejected_id) + '/submit', headers=self.owner)
        self.client.patch('/admin/facility-applications/' + str(rejected_id) + '/review', headers=self.admin, json={'action': 'REJECT', 'reason': 'Can bo sung giay to'})
        self.assertEqual(self.client.delete('/facilities/' + str(rejected_id) + '/draft', headers=self.owner).status_code, 409)

    def test_partial_draft_is_updated_in_place_without_duplicates(self):
        partial = {'name': '', 'location': '', 'description': 'Dang nhap thong tin', 'sports': [], 'amenities': [], 'image_urls': []}
        created = self.client.post('/facilities', headers=self.owner, json=partial)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()['status'], 'DRAFT')
        facility_id = created.json()['id']

        first = {**partial, 'name': 'Ban nhap SportHub'}
        second = {**first, 'location': '123 Dia chi dang hoan thien'}
        self.assertEqual(self.client.put('/facilities/' + str(facility_id), headers=self.owner, json=first).status_code, 200)
        updated = self.client.put('/facilities/' + str(facility_id), headers=self.owner, json=second)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['location'], second['location'])
        drafts = [item for item in self.client.get('/facilities', headers=self.owner).json() if item['status'] == 'DRAFT']
        self.assertEqual([item['id'] for item in drafts], [facility_id])

    def test_legacy_facility_approval_migration_preserves_documents(self):
        engine = create_engine('sqlite://', poolclass=StaticPool)
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE facilities (id INTEGER PRIMARY KEY, status VARCHAR(24), is_active BOOLEAN, approved_at DATETIME, created_at DATETIME, legacy_field_id INTEGER)'))
            connection.execute(text("INSERT INTO facilities VALUES (1, 'PENDING_REVIEW', 0, NULL, CURRENT_TIMESTAMP, NULL)"))
            connection.execute(text('CREATE TABLE facility_documents (id INTEGER PRIMARY KEY, facility_id INTEGER, file_path VARCHAR(500))'))
            connection.execute(text("INSERT INTO facility_documents VALUES (1, 1, '1/license.pdf')"))
        migrate_facility_approval_schema(engine)
        inspector = inspect(engine)
        self.assertIn('facility_verification_documents', inspector.get_table_names())
        self.assertNotIn('facility_documents', inspector.get_table_names())
        self.assertIn('file_sha256', {column['name'] for column in inspector.get_columns('facility_verification_documents')})
        with engine.connect() as connection:
            self.assertEqual(connection.scalar(text('SELECT status FROM facilities WHERE id=1')), 'PENDING_APPROVAL')
            self.assertEqual(connection.scalar(text('SELECT COUNT(*) FROM facility_verification_documents')), 1)
        engine.dispose()


if __name__ == '__main__':
    unittest.main()
