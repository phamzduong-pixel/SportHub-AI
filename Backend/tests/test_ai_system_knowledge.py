import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.services.ai_system_knowledge import match_system_knowledge


class SystemKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.context = cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        finally:
            cls.client.close()

    # 1. GENERAL SYSTEM / PLATFORM TESTS
    def test_sporthub_overview_question(self):
        res = self.client.post('/ai/assistant', json={'message': 'SportHub là gì?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SYSTEM_GUIDE')
        self.assertIn('nền tảng quản lý và đặt sân thể thao thông minh', data['reply'])

    def test_sporthub_features_question(self):
        res = self.client.post('/ai/assistant', json={'message': 'SportHub có những chức năng gì?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SYSTEM_GUIDE')
        self.assertIn('CUSTOMER', data['reply'])
        self.assertIn('OWNER', data['reply'])
        self.assertIn('SYSTEM_ADMIN', data['reply'])

    def test_user_roles_question(self):
        res = self.client.post('/ai/assistant', json={'message': 'Hệ thống có những vai trò nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SYSTEM_GUIDE')
        self.assertIn('CUSTOMER', data['reply'])
        self.assertIn('OWNER', data['reply'])
        self.assertIn('SYSTEM_ADMIN', data['reply'])

    # 2. CUSTOMER GUIDE TESTS
    def test_customer_register_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để đăng ký tài khoản?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Cách đăng ký tài khoản', data['reply'])
        self.assertEqual(data['action']['route'], '/register')

    def test_customer_login_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để đăng nhập?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Cách đăng nhập vào SportHub AI', data['reply'])
        self.assertEqual(data['action']['route'], '/login')

    def test_customer_search_fields_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để tìm sân?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Cách tìm sân', data['reply'])
        self.assertEqual(data['action']['route'], '/venues')

    def test_customer_booking_process_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để đặt sân?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Quy trình đặt sân', data['reply'])
        self.assertIn('khung giờ', data['reply'])

    def test_customer_payment_workflow_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Thanh toán đặt sân hoạt động như thế nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Cơ chế thanh toán đặt sân tại SportHub AI', data['reply'])
        self.assertIn('tiền cọc', data['reply'])

    def test_customer_view_bookings_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để xem booking?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Lịch đặt của tôi', data['reply'])
        self.assertEqual(data['action']['route'], '/my-bookings')

    def test_customer_cancel_booking_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để hủy booking?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Hướng dẫn hủy booking', data['reply'])
        self.assertIn('mốc hủy miễn phí', data['reply'])

    def test_customer_reschedule_booking_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để đổi lịch booking?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Hướng dẫn đổi lịch đặt sân', data['reply'])
        self.assertIn('khung giờ mới', data['reply'])

    def test_customer_review_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để đánh giá sân?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Cách đánh giá sân', data['reply'])
        self.assertIn('COMPLETED', data['reply'])

    def test_customer_profile_edit_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để sửa thông tin cá nhân?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Cách chỉnh sửa thông tin cá nhân', data['reply'])
        self.assertEqual(data['action']['route'], '/profile')

    # 3. OWNER / PARTNER GUIDE TESTS
    def test_owner_apply_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Làm thế nào để đăng ký làm chủ sân?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Quy trình đăng ký trở thành chủ sân (OWNER)', data['reply'])
        self.assertEqual(data['action']['route'], '/owner-application')

    def test_owner_requirements_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Điều kiện đăng ký chủ sân là gì?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('chưa yêu cầu tải lên ngay giấy phép kinh doanh', data['reply'])

    def test_owner_view_status_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Xem trạng thái hồ sơ chủ sân ở đâu?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('/owner-application/status', data['reply'])

    def test_owner_rejection_reapply_guide(self):
        res = self.client.post('/ai/assistant', json={'message': 'Hồ sơ bị từ chối thì sao?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('hoàn toàn ĐƯỢC PHÉP chỉnh sửa và cập nhật lại', data['reply'])

    # 4. ROLE SECURITY CHECKS (CUSTOMER vs OWNER / ADMIN)
    def test_customer_asking_owner_management_gets_role_alert(self):
        # When unauthenticated or customer role
        res = self.client.post('/ai/assistant', json={'message': 'Chủ sân được quản lý những gì?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Chủ sân (OWNER)', data['reply'])

    def test_customer_asking_add_field_gets_role_restricted_notice(self):
        entry, reply, action = match_system_knowledge("Chủ sân thêm sân mới như thế nào?", current_role="CUSTOMER")
        self.assertIsNotNone(entry)
        self.assertIn('chỉ dành cho tài khoản Chủ sân (OWNER)', reply)

    def test_owner_asking_add_field_gets_instructions(self):
        entry, reply, action = match_system_knowledge("Chủ sân thêm sân mới như thế nào?", current_role="OWNER")
        self.assertIsNotNone(entry)
        self.assertIn('Cách thêm cơ sở và sân mới', reply)

    def test_customer_asking_admin_user_management_restricted(self):
        entry, reply, action = match_system_knowledge("Admin quản lý người dùng như thế nào?", current_role="CUSTOMER")
        self.assertIsNotNone(entry)
        self.assertIn('quyền hạn riêng biệt của Quản trị viên (SYSTEM_ADMIN)', reply)

    def test_admin_asking_admin_user_management_gets_instructions(self):
        entry, reply, action = match_system_knowledge("Admin quản lý người dùng như thế nào?", current_role="SYSTEM_ADMIN")
        self.assertIsNotNone(entry)
        self.assertIn('Chức năng quản lý người dùng của SYSTEM_ADMIN', reply)

    # 5. UNKNOWN POLICIES & BOUNDARIES (Anti-Hallucination)
    def test_approval_sla_does_not_hallucinate(self):
        res = self.client.post('/ai/assistant', json={'message': 'Bao lâu thì duyệt hồ sơ chủ sân?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('chưa quy định cam kết thời gian duyệt cố định (SLA)', data['reply'])

    def test_owner_fee_does_not_hallucinate(self):
        res = self.client.post('/ai/assistant', json={'message': 'Phí đăng ký chủ sân là bao nhiêu?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('hoàn toàn miễn phí', data['reply'])

    # 6. DYNAMIC DATA SAFETY
    def test_specific_booking_code_query_does_not_hit_static_faq(self):
        entry, reply, action = match_system_knowledge("Kiểm tra booking SH-ABC123")
        self.assertIsNone(entry)
        self.assertIsNone(reply)

    def test_availability_query_does_not_hit_static_faq(self):
        entry, reply, action = match_system_knowledge("Ngày mai còn sân cầu lông nào trống không?")
        self.assertIsNone(entry)
        self.assertIsNone(reply)


if __name__ == '__main__':
    unittest.main()
