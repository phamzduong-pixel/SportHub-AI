import unittest
from datetime import date, timedelta

from tests import test_bookings as booking_tests


class PlatformOperationsTests(unittest.TestCase):
    def setUp(self):
        self.case = booking_tests.BookingWorkflowTests('test_adjacent_bookings_do_not_overlap')
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def test_field_block_removes_availability_and_is_audited(self):
        block_date = date.today() + timedelta(days=12)
        created = self.case.client.post('/field-blocks', headers=self.case.owner, json={
            'field_id': self.case.field_id, 'block_date': block_date.isoformat(),
            'start_time': '08:30', 'end_time': '09:30', 'reason': 'Bảo trì hệ thống chiếu sáng',
        })
        self.assertEqual(created.status_code, 201, created.text)
        availability = self.case.client.get(f'/availability?date={block_date.isoformat()}&field_id={self.case.field_id}')
        self.assertEqual(availability.status_code, 200, availability.text)
        returned_slots = [slot['id'] for item in availability.json() for slot in item['available_slots']]
        self.assertNotIn(self.case.slot_id, returned_slots)
        booking = self.case.client.post('/bookings', headers=self.case.customer1, json=self.case.payload(booking_date=block_date.isoformat()))
        self.assertEqual(booking.status_code, 409)
        logs = self.case.client.get('/audit-logs', headers=self.case.owner)
        self.assertEqual(logs.status_code, 200, logs.text)
        self.assertTrue(any(item['action'] == 'field_block_created' for item in logs.json()))

    def test_escrow_held_complaint_and_owner_processing(self):
        booking = self.case.create()
        payment = self.case.client.post('/payments', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_method': 'mock_online', 'payment_type': 'deposit',
        }).json()
        held = self.case.client.patch(f"/payments/{payment['id']}/confirm", headers=self.case.customer1, json={})
        self.assertEqual(held.status_code, 200, held.text)
        self.assertEqual(held.json()['escrow_status'], 'held')
        detail = self.case.client.get(f"/bookings/{booking['id']}", headers=self.case.customer1).json()
        self.assertTrue(any(item['action'] == 'booking_created' for item in detail['timeline']))
        self.assertTrue(any(item['action'] == 'deposit_held' for item in detail['timeline']))

        complaint = self.case.client.post('/complaints', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'category': 'payment',
            'description': 'Tôi cần kiểm tra trạng thái khoản tiền cọc mô phỏng.',
        })
        self.assertEqual(complaint.status_code, 201, complaint.text)
        self.assertEqual(self.case.client.post('/complaints', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'category': 'payment', 'description': 'Gửi trùng khiếu nại',
        }).status_code, 409)
        managed = self.case.client.get('/complaints', headers=self.case.operator)
        self.assertEqual(managed.status_code, 200, managed.text)
        updated = self.case.client.patch(f"/complaints/{complaint.json()['id']}", headers=self.case.operator, json={
            'status': 'resolved', 'resolution': 'Đã kiểm tra: tiền đang được giữ trung gian an toàn.',
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['status'], 'resolved')

    def test_refresh_token_rotation_and_type_validation(self):
        login = self.case.client.post('/auth/login', json={'email': 'customer1@test.local', 'password': 'Customer@123'})
        self.assertEqual(login.status_code, 200, login.text)
        refreshed = self.case.client.post('/auth/refresh', json={'refresh_token': login.json()['refresh_token']})
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertIn('refresh_token', refreshed.json())
        wrong_type = self.case.client.post('/auth/refresh', json={'refresh_token': login.json()['access_token']})
        self.assertEqual(wrong_type.status_code, 401)


if __name__ == '__main__':
    unittest.main()
