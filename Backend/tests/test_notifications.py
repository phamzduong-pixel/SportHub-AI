import unittest

from app.models.field import Booking
from app.models.notification import Notification
from app.models.field import Field
from app.models.user import User
from app.services.notification_service import NotificationService
from tests import test_bookings as booking_tests


class NotificationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case = booking_tests.BookingWorkflowTests('test_adjacent_bookings_do_not_overlap')
        self.case.setUp()
        with self.case.Session() as db:
            owner = db.query(User).filter_by(email='bookingowner@test.local').one()
            db.query(Field).update({'owner_id': owner.id})
            db.commit()

    def tearDown(self):
        self.case.tearDown()

    def pay_deposit(self, booking):
        created = self.case.client.post('/payments', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_method': 'mock_online', 'payment_type': 'deposit',
        })
        self.assertEqual(created.status_code, 201, created.text)
        settled = self.case.client.patch(
            f"/payments/{created.json()['id']}/confirm", headers=self.case.customer1, json={},
        )
        self.assertEqual(settled.status_code, 200, settled.text)
        return settled.json()

    def types(self, headers):
        response = self.case.client.get('/notifications?page_size=100', headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        return [item['type'] for item in response.json()['items']]

    def test_owner_receives_new_booking_notification(self):
        booking = self.case.create()
        self.pay_deposit(booking)
        self.assertIn('OWNER_NEW_BOOKING', self.types(self.case.owner))

    def test_customer_receives_booking_confirmed_notification(self):
        booking = self.case.create()
        self.pay_deposit(booking)
        response = self.case.client.patch(f"/bookings/{booking['id']}/confirm", headers=self.case.owner, json={})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('BOOKING_CONFIRMED', self.types(self.case.customer1))

    def test_customer_receives_booking_rejected_notification(self):
        booking = self.case.create()
        self.pay_deposit(booking)
        response = self.case.client.patch(
            f"/bookings/{booking['id']}/reject", headers=self.case.owner,
            json={'note': 'Sân cần xử lý sự cố'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('BOOKING_REJECTED', self.types(self.case.customer1))

    def test_customer_receives_refund_notification(self):
        booking = self.case.create()
        self.pay_deposit(booking)
        response = self.case.client.patch(
            f"/bookings/{booking['id']}/cancel", headers=self.case.customer1,
            json={'reason': 'Thay đổi kế hoạch thi đấu'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('PAYMENT_REFUNDED', self.types(self.case.customer1))

    def test_user_cannot_read_other_user_notification(self):
        booking = self.case.create()
        self.pay_deposit(booking)
        item = self.case.client.get('/notifications', headers=self.case.customer1).json()['items'][0]
        response = self.case.client.patch(
            f"/notifications/{item['id']}/read", headers=self.case.customer2,
        )
        self.assertEqual(response.status_code, 404)

    def test_mark_notification_as_read(self):
        booking = self.case.create()
        self.pay_deposit(booking)
        item = self.case.client.get('/notifications', headers=self.case.customer1).json()['items'][0]
        response = self.case.client.patch(
            f"/notifications/{item['id']}/read", headers=self.case.customer1,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['is_read'])
        self.assertIsNotNone(response.json()['read_at'])

    def test_mark_all_notifications_as_read(self):
        booking = self.case.create()
        self.pay_deposit(booking)
        response = self.case.client.patch('/notifications/read-all', headers=self.case.customer1)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreaterEqual(response.json()['updated_count'], 2)
        self.assertEqual(self.case.client.get('/notifications/unread-count', headers=self.case.customer1).json()['unread_count'], 0)

    def test_notification_ai_fallback(self):
        booking_data = self.case.create()
        with self.case.Session() as db:
            booking = db.get(Booking, booking_data['id'])
            service = NotificationService(
                db, message_renderer=lambda **_: (_ for _ in ()).throw(TimeoutError()),
            )
            item = service.booking_event(booking, 'BOOKING_CANCELLED')
            db.commit()
            self.assertIn(booking.booking_code, item.message)
            self.assertEqual(db.query(Notification).filter_by(user_id=booking.customer_id).count(), 1)


if __name__ == '__main__':
    unittest.main()
