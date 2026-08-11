import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.user import User, UserRole

class AuthPermissionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False); Base.metadata.create_all(self.engine)
        with self.Session() as db:
            db.add(User(full_name='Owner', email='owner@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value)); db.commit()
        def override_db():
            with self.Session() as db: yield db
        app.dependency_overrides[get_db] = override_db; self.client = TestClient(app)
    def tearDown(self): self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)
    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password}); self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}
    def test_customer_auth_profile_password_and_owner_api_denied(self):
        payload = {'full_name': 'Customer', 'email': 'customer@example.com', 'phone': '0901234567', 'password': 'Customer@123'}
        registered = self.client.post('/auth/register', json=payload); self.assertEqual(registered.status_code, 201); self.assertEqual(registered.json()['role'], 'CUSTOMER'); self.assertNotIn('permissions', registered.json())
        headers = self.login(payload['email'], payload['password']); self.assertEqual(self.client.post('/fields', headers=headers, json={}).status_code, 403)
        profile = self.client.put('/auth/profile', headers=headers, json={'full_name': 'Customer Updated', 'phone': '0909999999'}); self.assertEqual(profile.status_code, 200)
        changed = self.client.put('/auth/change-password', headers=headers, json={'current_password': 'Customer@123', 'new_password': 'NewPassword@123'}); self.assertEqual(changed.status_code, 200)
    def test_public_payload_cannot_select_elevated_role(self):
        payload = {'full_name': 'Valid Name', 'email': 'valid@example.com', 'phone': '0901111111', 'password': 'Password@123'}
        self.assertEqual(self.client.post('/auth/register', json={**payload, 'role': 'OWNER'}).status_code, 422)
        self.assertEqual(self.client.post('/auth/register', json={**payload, 'role': 'SYSTEM_ADMIN'}).status_code, 422)
    def test_duplicate_and_validation_errors(self):
        payload = {'full_name': 'Valid Name', 'email': 'valid@example.com', 'phone': '0901111111', 'password': 'Password@123'}
        self.assertEqual(self.client.post('/auth/register', json=payload).status_code, 201); self.assertEqual(self.client.post('/auth/register', json=payload).status_code, 409); self.assertEqual(self.client.get('/auth/me').status_code, 401)

    def test_registration_requires_valid_vietnamese_phone(self):
        invalid_phones = ['098765432', '09876543210', '123456789', '09abc54321', '0987 654 321', '', '   ']
        for index, phone in enumerate(invalid_phones):
            with self.subTest(phone=phone):
                response = self.client.post('/auth/register', json={
                    'full_name': 'Phone Validation', 'email': f'invalid{index}@example.com',
                    'phone': phone, 'password': 'Password@123',
                })
                self.assertEqual(response.status_code, 422, response.text)
        with self.Session() as db:
            self.assertEqual(db.scalar(select(func.count(User.id)).where(User.email.like('invalid%@example.com'))), 0)

        valid = self.client.post('/auth/register', json={
            'full_name': 'Valid Phone', 'email': 'valid.phone@example.com',
            'phone': ' 0987654321 ', 'password': 'Password@123',
        })
        self.assertEqual(valid.status_code, 201, valid.text)
        self.assertEqual(valid.json()['phone'], '0987654321')
        duplicate = self.client.post('/auth/register', json={
            'full_name': 'Duplicate Phone', 'email': 'other.email@example.com',
            'phone': '0987654321', 'password': 'Password@123',
        })
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.assertEqual(duplicate.json()['detail'], 'Số điện thoại đã được sử dụng.')

        logged_in = self.client.post('/auth/login', json={'email': 'valid.phone@example.com', 'password': 'Password@123'})
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        self.assertEqual(logged_in.json()['user']['phone'], '0987654321')

if __name__ == '__main__': unittest.main()
