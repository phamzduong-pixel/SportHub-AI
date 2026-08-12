import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
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
        document = self.client.post('/facilities/' + str(facility_id) + '/documents', headers=self.owner, data={'document_type': 'BUSINESS_LICENSE', 'document_name': 'Giay phep kinh doanh'}, files={'document': ('license.pdf', PDF, 'application/pdf')})
        self.assertEqual(document.status_code, 200, document.text)
        return facility_id

    def test_full_approve_flow_and_customer_visibility(self):
        self.assertEqual(self.client.post('/facilities', headers=self.customer, json=self.payload()).status_code, 403)
        facility_id = self.create_complete()
        self.assertEqual(self.client.get('/fields', headers=self.customer).json()['total'], 0)
        submitted = self.client.post('/facilities/' + str(facility_id) + '/submit', headers=self.owner)
        self.assertEqual(submitted.status_code, 200, submitted.text); self.assertEqual(submitted.json()['status'], 'PENDING_REVIEW')
        self.assertEqual(self.client.put('/facilities/' + str(facility_id), headers=self.owner, json=self.payload()).status_code, 409)
        self.assertEqual(self.client.patch('/admin/facility-applications/' + str(facility_id) + '/review', headers=self.owner, json={'action': 'APPROVE'}).status_code, 403)
        detail = self.client.get('/admin/facility-applications/' + str(facility_id), headers=self.admin)
        self.assertEqual(detail.status_code, 200, detail.text); self.assertEqual(len(detail.json()['documents']), 1)
        approved = self.client.patch('/admin/facility-applications/' + str(facility_id) + '/review', headers=self.admin, json={'action': 'APPROVE'})
        self.assertEqual(approved.status_code, 200, approved.text); self.assertEqual(approved.json()['status'], 'APPROVED')
        field = self.client.post('/fields', headers=self.owner, json={'facility_id': facility_id, 'name': 'Court 1', 'sport_type': 'Cầu lông', 'description': 'Court', 'location': 'ignored', 'capacity': 4, 'base_price': 200000, 'status': 'available', 'amenities': []})
        self.assertEqual(field.status_code, 201, field.text)
        self.assertEqual(self.client.get('/fields', headers=self.customer).json()['total'], 1)

    def test_reject_reason_resubmit_isolation_and_private_files(self):
        facility_id = self.create_complete()
        self.client.post('/facilities/' + str(facility_id) + '/submit', headers=self.owner)
        rejected = self.client.patch('/admin/facility-applications/' + str(facility_id) + '/review', headers=self.admin, json={'action': 'REJECT', 'reason': 'Can bo sung thong tin bien hieu'})
        self.assertEqual(rejected.json()['status'], 'REJECTED')
        own = self.client.get('/facilities/' + str(facility_id), headers=self.owner)
        self.assertEqual(own.json()['rejection_reason'], 'Can bo sung thong tin bien hieu')
        self.assertEqual(self.client.get('/facilities/' + str(facility_id), headers=self.other).status_code, 404)
        document_id = own.json()['documents'][0]['id']
        self.assertEqual(self.client.get('/facilities/' + str(facility_id) + '/documents/' + str(document_id) + '/content', headers=self.customer).status_code, 404)
        updated_payload = self.payload('SportHub Center Updated')
        self.assertEqual(self.client.put('/facilities/' + str(facility_id), headers=self.owner, json=updated_payload).status_code, 200)
        self.assertEqual(self.client.post('/facilities/' + str(facility_id) + '/submit', headers=self.owner).json()['status'], 'PENDING_REVIEW')

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


if __name__ == '__main__':
    unittest.main()