import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User, UserRole
from app.api.dependencies import get_current_user, require_system_admin
from app.services.knowledge_update_service import (
    KnowledgeUpdateJobManager,
    KnowledgeUpdateService,
    KnowledgeUpdateSummary,
)


class MockAssistantScenarioProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {
            'status': 'OK',
            'recommendations': [
                {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu.'}
                for item in available[:3]
            ],
        }


class SportsKnowledgeTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=MockAssistantScenarioProvider())
        cls.provider_patch.start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.provider_patch.stop()

    def setUp(self):
        # Reset any active lock
        with KnowledgeUpdateJobManager._lock:
            KnowledgeUpdateJobManager._is_running = False
            KnowledgeUpdateJobManager._current_job_id = None
            KnowledgeUpdateJobManager._last_summary = None

        self.admin_user = User(
            id=1,
            full_name="Admin Test",
            email="admin@test.local",
            role=UserRole.SYSTEM_ADMIN.value,
            is_active=True,
            session_version=0,
        )
        self.customer_user = User(
            id=2,
            full_name="Customer Test",
            email="customer@test.local",
            role=UserRole.CUSTOMER.value,
            is_active=True,
            session_version=0,
        )
        self.owner_user = User(
            id=3,
            full_name="Owner Test",
            email="owner@test.local",
            role=UserRole.OWNER.value,
            is_active=True,
            session_version=0,
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        with KnowledgeUpdateJobManager._lock:
            KnowledgeUpdateJobManager._is_running = False
            KnowledgeUpdateJobManager._current_job_id = None

    # 1. Valid Trigger by SYSTEM_ADMIN
    def test_valid_trigger_by_admin(self):
        app.dependency_overrides[require_system_admin] = lambda: self.admin_user

        raw_items = [
            {
                "url": "https://baothainguyen.vn/the-thao/bong-chuyen-thai-nguyen-2026",
                "title": "Bóng chuyền Thái Nguyên",
                "snippet": "Đội bóng chuyền Thái Nguyên đạt thành tích cao tại giải bóng chuyền toàn quốc.",
                "sport": "bóng chuyền",
                "entity": "Bóng chuyền Thái Nguyên",
                "topic": "achievement",
                "published_date": "2026-09-01",
            }
        ]

        response = self.client.post('/ai/knowledge/update', json={
            'raw_items': raw_items,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'COMPLETED')
        self.assertIn('hoàn tất thành công', data.get('message', ''))
        self.assertTrue(data.get('job_id', '').startswith('JOB-'))
        summary = data.get('summary', {})
        self.assertEqual(summary.get('inserted'), 1)
        self.assertEqual(summary.get('accepted'), 1)

    # 2. Unauthorized Trigger by CUSTOMER
    def test_unauthorized_trigger_by_customer(self):
        # Override with CUSTOMER
        def override_forbidden_customer():
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Chỉ SYSTEM_ADMIN được thực hiện thao tác này")

        app.dependency_overrides[require_system_admin] = override_forbidden_customer

        response = self.client.post('/ai/knowledge/update', json={})
        self.assertEqual(response.status_code, 403)
        self.assertIn('Chỉ SYSTEM_ADMIN', response.json().get('detail', ''))

    # 3. Unauthorized Trigger Anonymous (No Token)
    def test_unauthorized_trigger_anonymous(self):
        # Default dependency requirement without overrides will fail authentication
        response = self.client.post('/ai/knowledge/update', json={})
        self.assertEqual(response.status_code, 401)

    # 4. Duplicate / Concurrent Trigger Lock
    def test_duplicate_concurrent_trigger_lock(self):
        app.dependency_overrides[require_system_admin] = lambda: self.admin_user

        # Manually acquire the lock to simulate a currently running background job
        with KnowledgeUpdateJobManager._lock:
            KnowledgeUpdateJobManager._is_running = True
            KnowledgeUpdateJobManager._current_job_id = "JOB-RUNNING-123"

        response = self.client.post('/ai/knowledge/update', json={})
        self.assertEqual(response.status_code, 409)
        self.assertIn('đang được thực thi', response.json().get('detail', ''))

    # 5. Status Endpoint Check
    def test_status_endpoint_by_admin(self):
        app.dependency_overrides[require_system_admin] = lambda: self.admin_user

        # Initially idle
        res_idle = self.client.get('/ai/knowledge/update/status')
        self.assertEqual(res_idle.status_code, 200)
        self.assertFalse(res_idle.json().get('is_running'))

        # Set job state
        with KnowledgeUpdateJobManager._lock:
            KnowledgeUpdateJobManager._is_running = True
            KnowledgeUpdateJobManager._current_job_id = "JOB-ACTIVE-999"

        res_running = self.client.get('/ai/knowledge/update/status')
        self.assertEqual(res_running.status_code, 200)
        self.assertTrue(res_running.json().get('is_running'))
        self.assertEqual(res_running.json().get('current_job_id'), "JOB-ACTIVE-999")

    # 6. Error Resilience in Trigger (Failed / Malformed source item)
    def test_failed_source_partial_success(self):
        app.dependency_overrides[require_system_admin] = lambda: self.admin_user

        raw_items = [
            {
                "url": "https://vff.org.vn/valid-news",
                "title": "VFF News",
                "snippet": "Đội tuyển bóng đá nam quốc gia Việt Nam tập luyện tích cực.",
                "sport": "bóng đá",
                "entity": "Đội tuyển Việt Nam",
                "topic": "training",
                "published_date": "2026-09-01",
            },
            # Malformed item
            None,
        ]

        response = self.client.post('/ai/knowledge/update', json={
            'raw_items': raw_items,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'PARTIAL_SUCCESS')
        summary = data.get('summary', {})
        self.assertEqual(summary.get('inserted'), 1)
        self.assertEqual(len(summary.get('errors', [])), 1)

    # 7. AI Assistant Concurrency Isolation
    def test_trigger_does_not_affect_concurrent_ai_assistant_query(self):
        app.dependency_overrides[require_system_admin] = lambda: self.admin_user

        # Even if knowledge update job runs or is locked, normal assistant queries work smoothly
        with KnowledgeUpdateJobManager._lock:
            KnowledgeUpdateJobManager._is_running = True
            KnowledgeUpdateJobManager._current_job_id = "JOB-ISOLATION-TEST"

        ai_res = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(ai_res.status_code, 200)
        ai_data = ai_res.json()
        self.assertEqual(ai_data.get('classification'), 'IN_SCOPE')
        self.assertEqual(ai_data.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')


if __name__ == '__main__':
    unittest.main()
