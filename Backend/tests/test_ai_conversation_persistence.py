from datetime import date, time, timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.field import Field
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole


class AIConversationPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)

        with self.Session() as db:
            user_a = User(full_name='User A', email='usera@test.local', hashed_password=get_password_hash('Password@123'), role=UserRole.CUSTOMER.value)
            user_b = User(full_name='User B', email='userb@test.local', hashed_password=get_password_hash('Password@123'), role=UserRole.CUSTOMER.value)
            db.add_all([user_a, user_b])
            db.flush()

            field = Field(name='Sân Thử Nghiệm', sport_type='bóng đá', location='Quận 1', capacity=10, base_price=300000, status='available', amenities=[])
            db.add(field)
            db.flush()

            slot = TimeSlot(field_id=field.id, name='Ca 18h', start_time=time(18), end_time=time(20), price=Decimal('350000'), is_active=True)
            db.add(slot)
            db.commit()

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

        self.user_a_headers = self.login('usera@test.local', 'Password@123')
        self.user_b_headers = self.login('userb@test.local', 'Password@123')

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def test_save_user_and_assistant_message_and_retrieve(self):
        # 1. User sends a message
        msg_text = 'Tìm sân bóng đá Quận 1'
        response = self.client.post(
            '/ai/assistant',
            json={'message': msg_text},
            headers=self.user_a_headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        conv_id = data.get('conversation_id')
        self.assertTrue(conv_id, 'conversation_id must be returned in response')
        self.assertTrue(data.get('reply'))

        # 2. Check DB directly
        with self.Session() as db:
            conv = db.query(AIConversation).filter(AIConversation.conversation_id == conv_id).first()
            self.assertIsNotNone(conv)
            self.assertIsNotNone(conv.user_id)
            self.assertEqual(len(conv.messages), 2)
            self.assertEqual(conv.messages[0].role, 'user')
            self.assertEqual(conv.messages[0].content, msg_text)
            self.assertEqual(conv.messages[1].role, 'assistant')
            self.assertEqual(conv.messages[1].content, data['reply'])
            self.assertIsNotNone(conv.messages[1].payload)

        # 3. Retrieve conversation via GET API (page reload simulation)
        get_res = self.client.get(f'/ai/conversations/{conv_id}', headers=self.user_a_headers)
        self.assertEqual(get_res.status_code, 200, get_res.text)
        detail = get_res.json()
        self.assertEqual(detail['conversation_id'], conv_id)
        self.assertEqual(len(detail['messages']), 2)
        self.assertEqual(detail['messages'][0]['role'], 'user')
        self.assertEqual(detail['messages'][0]['content'], msg_text)
        self.assertEqual(detail['messages'][1]['role'], 'assistant')
        self.assertEqual(detail['messages'][1]['content'], data['reply'])

    def test_continue_conversation_does_not_create_duplicate(self):
        # First turn
        res1 = self.client.post(
            '/ai/assistant',
            json={'message': 'Tìm sân bóng đá'},
            headers=self.user_a_headers,
        )
        self.assertEqual(res1.status_code, 200)
        conv_id = res1.json()['conversation_id']

        # Second turn with the same conversation_id
        res2 = self.client.post(
            '/ai/assistant',
            json={'message': 'Còn sân nào khác không?', 'conversation_id': conv_id},
            headers=self.user_a_headers,
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()['conversation_id'], conv_id)

        # Verify only 1 conversation exists in DB with 4 messages
        with self.Session() as db:
            conv_count = db.query(AIConversation).filter(AIConversation.conversation_id == conv_id).count()
            self.assertEqual(conv_count, 1)

            conv = db.query(AIConversation).filter(AIConversation.conversation_id == conv_id).first()
            self.assertEqual(len(conv.messages), 4)
            self.assertEqual([m.role for m in conv.messages], ['user', 'assistant', 'user', 'assistant'])

    def test_user_b_cannot_access_user_a_conversation(self):
        # User A creates a conversation
        res = self.client.post(
            '/ai/assistant',
            json={'message': 'Tìm sân bóng đá cho User A'},
            headers=self.user_a_headers,
        )
        conv_id = res.json()['conversation_id']

        # User B attempts to view User A's conversation -> 403 Forbidden
        get_res = self.client.get(f'/ai/conversations/{conv_id}', headers=self.user_b_headers)
        self.assertEqual(get_res.status_code, 403)
        self.assertIn('Bạn không có quyền truy cập', get_res.json()['detail'])

        # User B attempts to post to User A's conversation -> 403 Forbidden
        post_res = self.client.post(
            '/ai/assistant',
            json={'message': 'Tin nhắn từ User B', 'conversation_id': conv_id},
            headers=self.user_b_headers,
        )
        self.assertEqual(post_res.status_code, 403)

    def test_list_conversations_isolated_by_user(self):
        # User A creates 2 conversations
        self.client.post('/ai/assistant', json={'message': 'Conv 1 A'}, headers=self.user_a_headers)
        self.client.post('/ai/assistant', json={'message': 'Conv 2 A'}, headers=self.user_a_headers)

        # User B creates 1 conversation
        self.client.post('/ai/assistant', json={'message': 'Conv 1 B'}, headers=self.user_b_headers)

        # Check User A's conversation list
        res_a = self.client.get('/ai/conversations', headers=self.user_a_headers)
        self.assertEqual(res_a.status_code, 200)
        items_a = res_a.json()['items']
        self.assertEqual(len(items_a), 2)
        self.assertTrue(all(item['message_count'] == 2 for item in items_a))

        # Check User B's conversation list
        res_b = self.client.get('/ai/conversations', headers=self.user_b_headers)
        self.assertEqual(res_b.status_code, 200)
        items_b = res_b.json()['items']
        self.assertEqual(len(items_b), 1)

    def test_user_message_persisted_even_if_assistant_service_fails(self):
        with patch('app.api.routes.ai.AIAssistantService.ask', side_effect=RuntimeError('Simulated AI engine error')):
            response = self.client.post(
                '/ai/assistant',
                json={'message': 'Tin nhắn gây lỗi hệ thống'},
                headers=self.user_a_headers,
            )
            self.assertEqual(response.status_code, 500)

        # Verify that user message was still committed before the exception
        with self.Session() as db:
            user_msg = db.query(AIMessage).filter(AIMessage.content == 'Tin nhắn gây lỗi hệ thống').first()
            self.assertIsNotNone(user_msg, 'User message must be committed immediately upon arrival')
            self.assertEqual(user_msg.role, 'user')
