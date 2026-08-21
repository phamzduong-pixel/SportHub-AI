import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.password_reset import PasswordResetChallenge
from app.models.user import User, UserRole
from app.services.password_reset_service import _hash


class ForgotPasswordOtpTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

        with self.Session() as db:
            user = User(
                full_name='Nguyen Van A',
                email='user@test.local',
                phone='0987654321',
                hashed_password=get_password_hash('OldPassword@123'),
                role=UserRole.CUSTOMER.value,
                is_active=True,
            )
            db.add(user)
            db.commit()
            self.user_id = user.id

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_email_otp_disabled_returns_friendly_error(self):
        with patch.object(settings, 'EMAIL_ENABLED', False), \
             patch.object(settings, 'EMAIL_PROVIDER', 'smtp'):
            response = self.client.post('/auth/forgot-password/email', json={'email': 'user@test.local'})
            self.assertEqual(response.status_code, 503)
            self.assertIn('Gửi email chưa được bật', response.json()['detail'])
            self.assertIn('EMAIL_ENABLED=true', response.json()['detail'])

    def test_email_otp_demo_flow(self):
        with patch.object(settings, 'EMAIL_PROVIDER', 'demo'):
            response = self.client.post('/auth/forgot-password/email', json={'email': 'user@test.local'})
            self.assertEqual(response.status_code, 200)

    def test_email_otp_success_flow(self):
        with patch.object(settings, 'EMAIL_ENABLED', True), \
             patch.object(settings, 'SMTP_HOST', 'smtp.example.com'), \
             patch.object(settings, 'SMTP_USER', 'user@example.com'), \
             patch.object(settings, 'SMTP_PASSWORD', 'secret'), \
             patch('app.services.email_service._send_email_async') as mock_send:

            # 1. Request OTP via email
            response = self.client.post('/auth/forgot-password/email', json={'email': 'user@test.local'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('mã xác nhận', response.json()['message'])

            # Inspect OTP in DB
            with self.Session() as db:
                challenge = db.query(PasswordResetChallenge).filter_by(user_id=self.user_id, channel='email').first()
                self.assertIsNotNone(challenge)
                self.assertFalse(challenge.used)

            # 2. Verify wrong OTP code
            wrong_verify = self.client.post('/auth/verify-otp', json={
                'channel': 'email',
                'identifier': 'user@test.local',
                'otp': '000000',
            })
            self.assertEqual(wrong_verify.status_code, 400)
            self.assertIn('Mã xác nhận không đúng', wrong_verify.json()['detail'])

            # 3. Verify correct OTP
            correct_code = None
            for candidate in range(1000000):
                code_str = f"{candidate:06d}"
                if _hash(code_str) == challenge.otp_hash:
                    correct_code = code_str
                    break

            self.assertIsNotNone(correct_code)

            verify_res = self.client.post('/auth/verify-otp', json={
                'channel': 'email',
                'identifier': 'user@test.local',
                'otp': correct_code,
            })
            self.assertEqual(verify_res.status_code, 200)
            token = verify_res.json().get('token')
            self.assertIsNotNone(token)

            # 4. Reset password
            reset_res = self.client.post('/auth/reset-password', json={
                'token': token,
                'new_password': 'NewPassword@456',
                'confirm_password': 'NewPassword@456',
            })
            self.assertEqual(reset_res.status_code, 200)
            self.assertIn('thành công', reset_res.json()['message'])

            # 5. Login with new password
            login_res = self.client.post('/auth/login', json={
                'email': 'user@test.local',
                'password': 'NewPassword@456',
            })
            self.assertEqual(login_res.status_code, 200)
            self.assertIn('access_token', login_res.json())

            # 6. Login with old password fails
            old_login = self.client.post('/auth/login', json={
                'email': 'user@test.local',
                'password': 'OldPassword@123',
            })
            self.assertEqual(old_login.status_code, 401)

    def test_phone_otp_disabled_returns_friendly_error(self):
        with patch.object(settings, 'SMS_ENABLED', False), \
             patch.object(settings, 'SMS_PROVIDER', 'twilio'):
            response = self.client.post('/auth/forgot-password/phone', json={'phone': '0987654321'})
            self.assertEqual(response.status_code, 503)
            self.assertIn('Chức năng gửi SMS hiện đang bảo trì', response.json()['detail'])

    def test_phone_otp_demo_flow(self):
        with patch.object(settings, 'SMS_PROVIDER', 'demo'):
            response = self.client.post('/auth/forgot-password/phone', json={'phone': '0987654321'})
            self.assertEqual(response.status_code, 200)

    def test_phone_otp_success_flow(self):
        with patch.object(settings, 'SMS_ENABLED', True), \
             patch.object(settings, 'SMS_PROVIDER', 'demo'):

            # 1. Request OTP via phone
            response = self.client.post('/auth/forgot-password/phone', json={'phone': '0987654321'})
            self.assertEqual(response.status_code, 200)

            # 2. Get code
            with self.Session() as db:
                challenge = db.query(PasswordResetChallenge).filter_by(user_id=self.user_id, channel='phone').first()
                self.assertIsNotNone(challenge)

            correct_code = None
            for candidate in range(1000000):
                code_str = f"{candidate:06d}"
                if _hash(code_str) == challenge.otp_hash:
                    correct_code = code_str
                    break

            # 3. Verify OTP
            verify_res = self.client.post('/auth/verify-otp', json={
                'channel': 'phone',
                'identifier': '0987654321',
                'otp': correct_code,
            })
            self.assertEqual(verify_res.status_code, 200)
            token = verify_res.json()['token']

            # 4. Reset password
            reset_res = self.client.post('/auth/reset-password', json={
                'token': token,
                'new_password': 'PhoneNewPass@789',
                'confirm_password': 'PhoneNewPass@789',
            })
            self.assertEqual(reset_res.status_code, 200)

            # 5. Login
            login_res = self.client.post('/auth/login', json={
                'email': 'user@test.local',
                'password': 'PhoneNewPass@789',
            })
            self.assertEqual(login_res.status_code, 200)

    def test_phone_validation_error(self):
        res = self.client.post('/auth/forgot-password/phone', json={'phone': '12345'})
        self.assertEqual(res.status_code, 422)


if __name__ == '__main__':
    unittest.main()
