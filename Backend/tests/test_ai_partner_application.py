from pathlib import Path
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.owner_application import OwnerApplication
from app.models.user import User, UserRole


class AIPartnerApplicationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            users = [
                User(full_name='No Application', email='none@ai-partner.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Pending Customer', email='pending@ai-partner.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Approved Owner', email='approved@ai-partner.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
                User(full_name='Rejected Customer', email='rejected@ai-partner.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
            ]
            db.add_all(users); db.flush()
            by_email = {user.email: user for user in users}
            common = {'representative': {'name': 'Đại diện'}, 'venue': {'name': 'Cơ sở dự kiến'}, 'legal_confirmed': True}
            db.add_all([
                OwnerApplication(customer_id=by_email['pending@ai-partner.local'].id, status='PENDING', **common),
                OwnerApplication(customer_id=by_email['approved@ai-partner.local'].id, status='APPROVED', **common),
                OwnerApplication(customer_id=by_email['rejected@ai-partner.local'].id, status='REJECTED', rejection_reason='Địa chỉ cơ sở chưa đầy đủ.', **common),
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
        self.engine.dispose()

    def headers(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def ask(self, email, password, message='Hồ sơ của tôi đang ở trạng thái nào?'):
        response = self.client.post('/ai/assistant', headers=self.headers(email, password), json={'message': message})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload['intent'], 'PARTNER_APPLICATION_SUPPORT')
        return payload

    def test_intent_partner_application_support(self):
        for message in ('Làm sao để trở thành chủ sân?', 'Tôi muốn đăng ký làm đối tác.', 'Cần chuẩn bị thông tin gì?'):
            with self.subTest(message=message):
                payload = self.client.post('/ai/assistant', json={'message': message}).json()
                self.assertEqual(payload['intent'], 'PARTNER_APPLICATION_SUPPORT')
                self.assertIn('SYSTEM_ADMIN', payload['reply'])

    def test_partner_follow_up_keeps_context(self):
        headers = self.headers('none@ai-partner.local', 'Customer@123')
        first = self.client.post('/ai/assistant', headers=headers, json={'message': 'Tôi muốn trở thành chủ sân.'}).json()
        follow_up = self.client.post('/ai/assistant', headers=headers, json={
            'message': 'Bước tiếp theo?', 'context': first['understood'],
        }).json()
        self.assertEqual(follow_up['intent'], 'PARTNER_APPLICATION_SUPPORT')
        self.assertEqual(follow_up['partner_application_status'], 'NONE')

    def test_customer_without_application(self):
        payload = self.ask('none@ai-partner.local', 'Customer@123')
        self.assertEqual(payload['partner_application_status'], 'NONE')
        self.assertEqual(payload['action'], {'label': 'Đăng ký trở thành chủ sân', 'route': '/owner-application', 'kind': 'link'})

    def test_pending_application(self):
        payload = self.ask('pending@ai-partner.local', 'Customer@123')
        self.assertEqual(payload['partner_application_status'], 'PENDING')
        self.assertEqual(payload['action']['route'], '/owner-application/status')

    def test_approved_application(self):
        payload = self.ask('approved@ai-partner.local', 'Owner@123456')
        self.assertEqual(payload['partner_application_status'], 'APPROVED')
        self.assertEqual(payload['action']['route'], '/management/dashboard')

    def test_rejected_application_uses_database_reason(self):
        payload = self.ask('rejected@ai-partner.local', 'Customer@123', 'Tại sao hồ sơ bị từ chối?')
        self.assertEqual(payload['partner_application_status'], 'REJECTED')
        self.assertIn('Địa chỉ cơ sở chưa đầy đủ.', payload['reply'])
        self.assertEqual(payload['action']['route'], '/owner-application')

    def test_action_navigation_matches_status(self):
        cases = (
            ('none@ai-partner.local', 'Customer@123', 'NONE', '/owner-application'),
            ('pending@ai-partner.local', 'Customer@123', 'PENDING', '/owner-application/status'),
            ('approved@ai-partner.local', 'Owner@123456', 'APPROVED', '/management/dashboard'),
            ('rejected@ai-partner.local', 'Customer@123', 'REJECTED', '/owner-application'),
        )
        for email, password, status, route in cases:
            with self.subTest(status=status):
                payload = self.ask(email, password)
                self.assertEqual(payload['partner_application_status'], status)
                self.assertEqual(payload['action']['route'], route)

    def test_ai_does_not_change_role_or_application_status(self):
        with self.Session() as db:
            before_users = {user.email: user.role for user in db.scalars(select(User)).all()}
            before_apps = {item.customer_id: item.status for item in db.scalars(select(OwnerApplication)).all()}
        self.ask('rejected@ai-partner.local', 'Customer@123', 'Tôi muốn gửi lại hồ sơ.')
        self.ask('pending@ai-partner.local', 'Customer@123', 'Hãy duyệt hồ sơ của tôi.')
        with self.Session() as db:
            self.assertEqual(before_users, {user.email: user.role for user in db.scalars(select(User)).all()})
            self.assertEqual(before_apps, {item.customer_id: item.status for item in db.scalars(select(OwnerApplication)).all()})

    def test_frontend_uses_backend_action_without_rendering_status_enum(self):
        root = Path(__file__).resolve().parents[2]
        service = (root / 'Frontend/src/services/aiAssistantService.ts').read_text(encoding='utf-8')
        page = (root / 'Frontend/src/pages/AIAssistantPage.tsx').read_text(encoding='utf-8')
        self.assertIn("'PARTNER_APPLICATION_SUPPORT'", service)
        self.assertIn('if (response.action)', page)
        self.assertIn('response.action.route', page)
        self.assertNotIn('message.partner_application_status', page)


if __name__ == '__main__':
    unittest.main()
