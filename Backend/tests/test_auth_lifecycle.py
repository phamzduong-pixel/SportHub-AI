import unittest
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.notification import Notification
from app.models.user import User, UserRole


class AuthLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            db.add_all([
                User(full_name='Customer A', email='auth-a@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Customer B', email='auth-b@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Owner', email='auth-owner@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
            ])
            db.commit()
            first = db.query(User).filter_by(email='auth-a@test.local').one()
            db.add(Notification(user_id=first.id, type='TEST', title='Riêng A', message='Dữ liệu tài khoản A'))
            db.commit()
            self.first_id = first.id

        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine); self.engine.dispose()

    def login(self, email='auth-a@test.local', password='Customer@123'):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    @staticmethod
    def headers(token):
        return {'Authorization': f'Bearer {token}'}

    def test_logout_clears_auth_state(self):
        session = self.login()
        logged_out = self.client.post('/auth/logout', json={'refresh_token': session['refresh_token']})
        self.assertEqual(logged_out.status_code, 200, logged_out.text)
        self.assertEqual(self.client.get('/auth/me', headers=self.headers(session['access_token'])).status_code, 401)
        self.assertEqual(self.client.post('/auth/refresh', json={'refresh_token': session['refresh_token']}).status_code, 401)
        source = Path('../Frontend/src/contexts/AuthContext.tsx').read_text(encoding='utf-8')
        for key in ('sporthub_booking_context', 'sporthub_booking_draft', 'sporthub_latest_booking'):
            self.assertIn(key, source)
        self.assertIn('setUser(null)', source)
        self.assertIn('sporthub-auth-cleared', source)

    def test_login_second_user_does_not_keep_first_user_data(self):
        first = self.login()
        first_items = self.client.get('/notifications', headers=self.headers(first['access_token'])).json()['items']
        self.assertEqual([item['title'] for item in first_items], ['Riêng A'])
        second = self.login('auth-b@test.local')
        second_items = self.client.get('/notifications', headers=self.headers(second['access_token'])).json()['items']
        self.assertEqual(second_items, [])
        source = Path('../Frontend/src/contexts/AuthContext.tsx').read_text(encoding='utf-8')
        login_body = source[source.index('const login ='):source.index('const register =')]
        self.assertIn('clearToken()', login_body)
        self.assertIn('clearUserScopedCache()', login_body)

    def test_expired_token_rejected(self):
        expired = create_access_token(
            {'sub': str(self.first_id), 'role': 'CUSTOMER', 'sv': 0},
            expires_delta=timedelta(seconds=-1),
        )
        self.assertEqual(self.client.get('/auth/me', headers=self.headers(expired)).status_code, 401)

    def test_refresh_token_flow(self):
        initial = self.login()
        refreshed = self.client.post('/auth/refresh', json={'refresh_token': initial['refresh_token']})
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        rotated = refreshed.json()
        self.assertNotEqual(rotated['refresh_token'], initial['refresh_token'])
        self.assertEqual(self.client.post('/auth/refresh', json={'refresh_token': initial['refresh_token']}).status_code, 401)
        self.assertEqual(self.client.get('/auth/me', headers=self.headers(initial['access_token'])).status_code, 401)
        self.assertEqual(self.client.get('/auth/me', headers=self.headers(rotated['access_token'])).status_code, 200)

    def test_customer_cannot_call_owner_api(self):
        customer = self.login()
        response = self.client.get('/facilities', headers=self.headers(customer['access_token']))
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
