import unittest

from tests import test_bookings as booking_tests


class RefundWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case = booking_tests.BookingWorkflowTests('test_adjacent_bookings_do_not_overlap')
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def paid_booking(self):
        booking = self.case.create()
        payment = self.case.client.post('/payments', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_method': 'mock_online', 'payment_type': 'deposit',
        })
        self.assertEqual(payment.status_code, 201, payment.text)
        confirmed = self.case.client.patch(f"/payments/{payment.json()['id']}/confirm", headers=self.case.customer1, json={})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        return booking, payment.json()

    def test_owner_rejection_requires_reason_and_refund_is_idempotent(self):
        booking, deposit = self.paid_booking()
        missing_reason = self.case.client.patch(f"/bookings/{booking['id']}/reject", headers=self.case.operator, json={})
        self.assertEqual(missing_reason.status_code, 422)

        cancelled = self.case.client.patch(f"/bookings/{booking['id']}/reject", headers=self.case.operator, json={
            'note': 'Sân cần bảo trì khẩn cấp',
        })
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        detail = cancelled.json()
        self.assertEqual(detail['status'], 'cancelled_by_owner')
        self.assertEqual(detail['refund_status'], 'refund_pending')
        self.assertEqual(detail['refund_amount'], booking['deposit_amount'])
        self.assertEqual(detail['remaining_amount'], 0)

        cannot_pay = self.case.client.post('/payments', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_method': 'mock_online', 'payment_type': 'remaining',
        })
        self.assertEqual(cannot_pay.status_code, 409)

        refunds = self.case.client.get('/refunds', headers=self.case.owner)
        self.assertEqual(refunds.status_code, 200, refunds.text)
        refund = next(item for item in refunds.json()['items'] if item['booking_id'] == booking['id'])
        self.assertEqual(refund['status'], 'refund_pending')
        self.assertTrue(any(item['action'] == 'owner_rejected_booking' for item in refund['activities']))

        payload = {'transaction_reference': 'OWNER-REFUND-0001', 'evidence_url': 'https://example.com/proof/1'}
        completed = self.case.client.patch(f"/refunds/{refund['id']}/mark-refunded", headers=self.case.owner, json=payload)
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()['status'], 'refunded')
        duplicate = self.case.client.patch(f"/refunds/{refund['id']}/mark-refunded", headers=self.case.owner, json=payload)
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        conflicting = self.case.client.patch(f"/refunds/{refund['id']}/mark-refunded", headers=self.case.owner, json={
            'transaction_reference': 'OWNER-REFUND-0002',
        })
        self.assertEqual(conflicting.status_code, 409)

        customer_confirmed = self.case.client.patch(f"/refunds/{refund['id']}/confirm-received", headers=self.case.customer1, json={})
        self.assertEqual(customer_confirmed.status_code, 200, customer_confirmed.text)
        self.assertIsNotNone(customer_confirmed.json()['customer_confirmed_at'])
        self.assertEqual(self.case.client.patch(f"/refunds/{refund['id']}/confirm-received", headers=self.case.customer1, json={}).status_code, 200)

        original_payment = self.case.client.get(f"/payments/{deposit['id']}", headers=self.case.customer1).json()
        booking_after = self.case.client.get(f"/bookings/{booking['id']}", headers=self.case.customer1).json()
        self.assertEqual(original_payment['refund_status'], 'refunded')
        self.assertEqual(booking_after['payment_status'], 'refunded')

    def test_customer_can_dispute_missing_refund(self):
        booking, _ = self.paid_booking()
        self.case.client.patch(f"/bookings/{booking['id']}/reject", headers=self.case.operator, json={'note': 'Không thể phục vụ'})
        refund = self.case.client.get('/refunds/my', headers=self.case.customer1).json()['items'][0]
        disputed = self.case.client.patch(f"/refunds/{refund['id']}/dispute", headers=self.case.customer1, json={
            'reason': 'Tôi chưa nhận được tiền hoàn',
        })
        self.assertEqual(disputed.status_code, 200, disputed.text)
        self.assertEqual(disputed.json()['status'], 'disputed')
        self.assertEqual(self.case.client.patch(f"/refunds/{refund['id']}/mark-refunded", headers=self.case.owner, json={
            'transaction_reference': 'MUST-NOT-DOUBLE-REFUND',
        }).status_code, 409)


if __name__ == '__main__':
    unittest.main()
