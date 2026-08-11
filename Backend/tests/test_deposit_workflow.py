import unittest

from tests import test_bookings as booking_tests


class DepositWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case = booking_tests.BookingWorkflowTests('test_adjacent_bookings_do_not_overlap')
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def test_deposit_confirms_then_only_remaining_is_collected_idempotently(self):
        booking = self.case.create()
        self.assertEqual(booking['deposit_amount'], booking['total_amount'] * 0.30)
        self.assertEqual(booking['remaining_amount'], booking['total_amount'])

        created = self.case.client.post('/payments', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_method': 'mock_online', 'payment_type': 'deposit',
        })
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()['amount'], booking['deposit_amount'])
        paid_deposit = self.case.client.patch(f"/payments/{created.json()['id']}/confirm", headers=self.case.customer1, json={})
        self.assertEqual(paid_deposit.status_code, 200, paid_deposit.text)

        held = self.case.client.get(f"/bookings/{booking['id']}", headers=self.case.customer1).json()
        self.assertEqual(held['status'], 'pending_confirmation')
        self.assertEqual(held['paid_amount'], held['deposit_amount'])
        self.assertEqual(held['deposit_amount'] + held['remaining_amount'], held['total_amount'])
        self.assertEqual(self.case.client.post('/bookings', headers=self.case.customer2, json=self.case.payload()).status_code, 409)
        owner_confirmed = self.case.client.patch(f"/bookings/{booking['id']}/confirm", headers=self.case.operator, json={})
        self.assertEqual(owner_confirmed.status_code, 200, owner_confirmed.text)
        self.assertEqual(owner_confirmed.json()['status'], 'confirmed')

        final = self.case.client.post('/payments', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_method': 'mock_online', 'payment_type': 'full',
        })
        self.assertEqual(final.json()['amount'], held['remaining_amount'])
        settled = self.case.client.patch(f"/payments/{final.json()['id']}/confirm", headers=self.case.customer1, json={})
        duplicate = self.case.client.patch(f"/payments/{final.json()['id']}/confirm", headers=self.case.customer1, json={})
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()['paid_amount'], settled.json()['paid_amount'])

        summary = self.case.client.get(f"/bookings/{booking['id']}/payment-summary", headers=self.case.customer1).json()
        self.assertEqual(summary['paid_amount'], summary['total_amount'])
        self.assertEqual(summary['remaining_amount'], 0)
        self.assertEqual(len(summary['transactions']), 2)
        self.assertEqual({item['transaction_code'] for item in summary['transactions']}, {
            created.json()['transaction_code'], final.json()['transaction_code'],
        })
        for source in (created.json(), final.json()):
            payment_detail = self.case.client.get(f"/payments/{source['id']}", headers=self.case.customer1)
            self.assertEqual(payment_detail.status_code, 200, payment_detail.text)
            self.assertEqual(payment_detail.json()['transaction_code'], source['transaction_code'])
            self.assertEqual(payment_detail.json()['booking_id'], booking['id'])
        self.assertEqual(
            self.case.client.get(f"/payments/{created.json()['id']}", headers=self.case.customer2).status_code,
            403,
        )
        self.assertEqual(settled.json()['invoice']['total_amount'], summary['total_amount'])
        detail = self.case.client.get(f"/bookings/{booking['id']}", headers=self.case.operator).json()
        self.assertEqual(detail['status'], 'confirmed')
        self.assertEqual(detail['payment_status'], 'paid')
        self.assertEqual(detail['remaining_amount'], 0)
        charged_twice = self.case.client.post('/payments', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_method': 'mock_online', 'payment_type': 'remaining',
        })
        self.assertEqual(charged_twice.status_code, 409, charged_twice.text)
