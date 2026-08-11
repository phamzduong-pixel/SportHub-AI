import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from app.core.config import settings
from app.models.field import Booking
from app.models.payment import Payment
from tests import test_bookings as booking_tests


class BankQrPaymentTests(unittest.TestCase):
    def setUp(self):
        self.case = booking_tests.BookingWorkflowTests('test_adjacent_bookings_do_not_overlap')
        self.case.setUp()
        self.old_secret = settings.PAYMENT_WEBHOOK_SECRET
        self.old_mode = settings.PAYMENT_MODE
        settings.PAYMENT_WEBHOOK_SECRET = 'test-webhook-secret'

    def tearDown(self):
        settings.PAYMENT_WEBHOOK_SECRET = self.old_secret
        settings.PAYMENT_MODE = self.old_mode
        self.case.tearDown()

    def test_qr_is_unique_exact_and_requires_verified_payment(self):
        booking = self.case.create()
        intent = self.case.client.post('/payments/bank-intents', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_type': 'deposit',
        })
        self.assertEqual(intent.status_code, 201, intent.text)
        payment = intent.json()
        expires_at = datetime.fromisoformat(payment['expires_at'].replace('Z', '+00:00'))
        ttl = (expires_at - datetime.now(timezone.utc)).total_seconds()
        self.assertGreater(ttl, 14 * 60 + 50)
        self.assertLessEqual(ttl, 15 * 60 + 1)
        self.assertIsNotNone(expires_at.tzinfo)
        refreshed = self.case.client.get(f"/payments/{payment['id']}", headers=self.case.customer1).json()
        self.assertEqual(refreshed['expires_at'], payment['expires_at'])
        self.assertEqual(payment['amount'], booking['deposit_amount'])
        self.assertIn(booking['booking_code'].replace('-', ''), payment['transfer_content'])
        query = parse_qs(urlparse(payment['qr_url']).query)
        self.assertEqual(query['amount'][0], str(int(booking['deposit_amount'])))
        self.assertEqual(query['addInfo'][0], payment['transfer_content'])
        self.assertEqual(self.case.client.post('/payments/bank-intents', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_type': 'deposit',
        }).status_code, 409)
        self.assertEqual(self.case.client.patch(f"/payments/{payment['id']}/confirm", headers=self.case.customer1, json={}).status_code, 403)

        wrong = self.case.client.post('/payments/webhook/bank', headers={'X-Payment-Webhook-Secret': 'test-webhook-secret'}, json={
            'provider_reference': 'BANK-WRONG-AMOUNT', 'transfer_content': payment['transfer_content'],
            'amount': booking['deposit_amount'] - 1, 'status': 'success',
        })
        self.assertEqual(wrong.status_code, 422)
        self.assertEqual(self.case.client.get(f"/bookings/{booking['id']}", headers=self.case.customer1).json()['status'], 'pending_payment')

        paid = self.case.client.post(f"/payments/{payment['id']}/demo-confirm", headers=self.case.customer1)
        self.assertEqual(paid.status_code, 200, paid.text)
        duplicate = self.case.client.post(f"/payments/{payment['id']}/demo-confirm", headers=self.case.customer1)
        self.assertEqual(duplicate.json()['paid_amount'], paid.json()['paid_amount'])
        awaiting = self.case.client.get(f"/bookings/{booking['id']}", headers=self.case.customer1).json()
        self.assertEqual(awaiting['status'], 'pending_confirmation')
        self.assertEqual(awaiting['paid_amount'], awaiting['deposit_amount'])
        rejected = self.case.client.patch(f"/bookings/{booking['id']}/reject", headers=self.case.operator, json={'note': 'No court available'})
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(rejected.json()['status'], 'cancelled_by_owner')
        self.assertEqual(rejected.json()['refund_status'], 'refund_pending')
        self.assertEqual(rejected.json()['refundable_deposit_amount'], booking['deposit_amount'])
        refunded_payment = self.case.client.get(f"/payments/{payment['id']}", headers=self.case.customer1).json()
        self.assertEqual(refunded_payment['refund_status'], 'refund_pending')
        replacement = self.case.client.post('/bookings', headers=self.case.customer2, json=self.case.payload())
        self.assertEqual(replacement.status_code, 201, replacement.text)

    def test_expired_qr_fails_payment_and_releases_slot(self):
        booking = self.case.create()
        intent = self.case.client.post('/payments/bank-intents', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_type': 'deposit',
        }).json()
        with self.case.Session() as db:
            db.get(Payment, intent['id']).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.get(Booking, booking['id']).hold_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        expired = self.case.client.get(f"/payments/{intent['id']}", headers=self.case.customer1)
        self.assertEqual(expired.json()['status'], 'failed')
        detail = self.case.client.get(f"/bookings/{booking['id']}", headers=self.case.customer1).json()
        self.assertEqual(detail['status'], 'expired')
        replacement = self.case.client.post('/bookings', headers=self.case.customer2, json=self.case.payload())
        self.assertEqual(replacement.status_code, 201, replacement.text)

    def test_production_only_accepts_exact_idempotent_webhook(self):
        booking = self.case.create()
        intent = self.case.client.post('/payments/bank-intents', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'payment_type': 'deposit',
        }).json()
        settings.PAYMENT_MODE = 'production'
        self.assertEqual(self.case.client.post(f"/payments/{intent['id']}/demo-confirm", headers=self.case.customer1).status_code, 403)
        payload = {
            'provider_reference': 'BANK-PROVIDER-0001', 'transfer_content': intent['transfer_content'],
            'amount': intent['amount'], 'status': 'success',
        }
        paid = self.case.client.post('/payments/webhook/bank', headers={'X-Payment-Webhook-Secret': 'test-webhook-secret'}, json=payload)
        self.assertEqual(paid.status_code, 200, paid.text)
        duplicate = self.case.client.post('/payments/webhook/bank', headers={'X-Payment-Webhook-Secret': 'test-webhook-secret'}, json=payload)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()['paid_amount'], paid.json()['paid_amount'])
        self.assertEqual(duplicate.json()['verification_source'], 'bank_webhook')


if __name__ == '__main__':
    unittest.main()
