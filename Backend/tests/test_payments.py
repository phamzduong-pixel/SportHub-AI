import unittest
from datetime import date, time, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking, Field
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole


class PaymentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            field = Field(name='Sân thanh toán', sport_type='Bóng đá', location='Quận 1', capacity=10, base_price=1000000, status='available', amenities=[])
            db.add(field); db.flush()
            slot = TimeSlot(field_id=field.id, name='Ca chính', start_time=time(8), end_time=time(10), price=Decimal('1000000'), is_active=True)
            cheap_slot = TimeSlot(field_id=field.id, name='Ca rẻ', start_time=time(10), end_time=time(11), price=Decimal('200000'), is_active=True)
            owner = User(full_name='Owner', email='payowner@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value)
            system_admin = User(full_name='System Admin', email='payadmin@test.local', hashed_password=get_password_hash('Admin@123456'), role=UserRole.SYSTEM_ADMIN.value)
            operator = User(full_name='Owner', email='payoperator@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value)
            no_permission = User(full_name='No Payment', email='paynone@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value)
            customer1 = User(full_name='Customer One', email='paycustomer1@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value)
            customer2 = User(full_name='Customer Two', email='paycustomer2@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value)
            db.add_all([slot, cheap_slot, owner, system_admin, operator, no_permission, customer1, customer2]); db.flush()
            field.owner_id = owner.id
            booking = Booking(
                booking_code='SH-PAY-001', customer_id=customer1.id, field_id=field.id,
                time_slot_id=slot.id, booking_date=date.today() + timedelta(days=7),
                start_time_snapshot=slot.start_time, end_time_snapshot=slot.end_time,
                price_snapshot=slot.price, total_amount=slot.price, status='pending',
            )
            rejected = Booking(
                booking_code='SH-PAY-002', customer_id=customer1.id, field_id=field.id,
                time_slot_id=cheap_slot.id, booking_date=date.today() + timedelta(days=8),
                start_time_snapshot=cheap_slot.start_time, end_time_snapshot=cheap_slot.end_time,
                price_snapshot=cheap_slot.price, total_amount=cheap_slot.price, status='rejected',
            )
            db.add_all([booking, rejected]); db.commit()
            self.booking_id, self.rejected_id = booking.id, rejected.id
            self.field_id, self.cheap_slot_id = field.id, cheap_slot.id

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner = self.login('payowner@test.local', 'Owner@123456')
        self.system_admin = self.login('payadmin@test.local', 'Admin@123456')
        self.operator = self.owner
        self.no_permission = self.login('paynone@test.local', 'Operator@123')
        self.customer1 = self.login('paycustomer1@test.local', 'Customer@123')
        self.customer2 = self.login('paycustomer2@test.local', 'Customer@123')

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def create_payment(self, amount, method='mock_online', payment_type='deposit', headers=None, booking_id=None):
        return self.client.post('/payments', headers=headers or self.customer1, json={
            'booking_id': booking_id or self.booking_id, 'amount': amount,
            'payment_method': method, 'payment_type': payment_type, 'note': 'Kiểm thử',
        })

    def test_amount_limits_full_payment_and_summary(self):
        deposit = self.create_payment(300000)
        self.assertEqual(deposit.status_code, 201, deposit.text)
        self.assertEqual(self.create_payment(800000).status_code, 409)
        self.assertEqual(self.create_payment(700000, payment_type='full').status_code, 409)
        confirmed = self.client.patch(f"/payments/{deposit.json()['id']}/confirm", headers=self.customer1, json={})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()['status'], 'paid')
        self.assertIsNotNone(confirmed.json()['invoice'])
        owner_confirmed = self.client.patch(f"/bookings/{self.booking_id}/confirm", headers=self.owner, json={})
        self.assertEqual(owner_confirmed.status_code, 200, owner_confirmed.text)
        self.assertEqual(self.create_payment(600000, payment_type='full').status_code, 422)
        final = self.create_payment(700000, payment_type='full')
        self.assertEqual(final.status_code, 201, final.text)
        self.client.patch(f"/payments/{final.json()['id']}/confirm", headers=self.customer1, json={})
        summary = self.client.get(f'/bookings/{self.booking_id}/payment-summary', headers=self.customer1)
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()['paid_amount'], 1000000)
        self.assertEqual(summary.json()['remaining_amount'], 0)
        self.assertEqual(summary.json()['payment_status'], 'paid')
        self.assertEqual(self.create_payment(1).status_code, 409)

    def test_permissions_cash_confirmation_and_ownership(self):
        cash = self.create_payment(200000, method='cash')
        self.assertEqual(self.client.patch(f"/payments/{cash.json()['id']}/confirm", headers=self.customer1, json={}).status_code, 403)
        self.assertEqual(self.client.patch(f"/payments/{cash.json()['id']}/confirm", headers=self.no_permission, json={}).status_code, 403)
        paid = self.client.patch(f"/payments/{cash.json()['id']}/confirm", headers=self.operator, json={'note': 'Đã nhận tiền'})
        self.assertEqual(paid.status_code, 200, paid.text)
        self.assertEqual(paid.json()['confirmer_name'], 'Owner')
        self.assertEqual(self.client.get('/payments', headers=self.no_permission).status_code, 403)
        self.assertEqual(self.client.get('/payments', headers=self.operator).json()['total'], 1)
        self.assertEqual(self.client.get(f"/payments/{cash.json()['id']}", headers=self.customer2).status_code, 403)
        self.assertEqual(self.create_payment(100000, headers=self.customer2).status_code, 403)

    def test_booking_and_payment_status_rules(self):
        self.assertEqual(self.create_payment(100000, booking_id=self.rejected_id).status_code, 409)
        pending = self.create_payment(100000)
        cancelled = self.client.patch(f"/payments/{pending.json()['id']}/cancel", headers=self.customer1, json={})
        self.assertEqual(cancelled.json()['status'], 'cancelled')
        self.assertEqual(self.client.patch(f"/payments/{pending.json()['id']}/cancel", headers=self.customer1, json={}).status_code, 409)
        paid = self.create_payment(250000)
        self.client.patch(f"/payments/{paid.json()['id']}/confirm", headers=self.customer1, json={})
        self.assertEqual(self.client.patch(f"/payments/{paid.json()['id']}/cancel", headers=self.owner, json={}).status_code, 409)
        moved = self.client.put(f'/bookings/{self.booking_id}', headers=self.owner, json={
            'field_id': self.field_id, 'time_slot_id': self.cheap_slot_id,
            'booking_date': (date.today() + timedelta(days=9)).isoformat(), 'note': None,
        })
        self.assertEqual(moved.status_code, 409)

    def test_deposit_receipt_uses_backend_data_and_enforces_tenant_access(self):
        pending = self.create_payment(300000)
        self.assertEqual(pending.status_code, 201, pending.text)
        payment_id = pending.json()['id']
        paid = self.client.patch(f'/payments/{payment_id}/confirm', headers=self.customer1, json={})
        self.assertEqual(paid.status_code, 200, paid.text)

        receipt = self.client.get(f'/payments/{payment_id}/deposit-receipt', headers=self.customer1)
        self.assertEqual(receipt.status_code, 200, receipt.text)
        data = receipt.json()
        self.assertEqual(data['booking_code'], 'SH-PAY-001')
        self.assertEqual(data['deposit_paid'], 300000)
        self.assertEqual(data['remaining_amount'], 700000)
        self.assertEqual(data['start_time'], '08:00')
        self.assertEqual(data['end_time'], '10:00')
        self.assertEqual(data['deposit_status'], 'paid_pending_confirmation')
        self.assertEqual(data['status_message'], 'Đã thanh toán cọc – Đang chờ chủ sân xác nhận.')
        self.assertEqual(data['transaction_code'], paid.json()['transaction_code'])
        self.assertIsNotNone(data['paid_at'])

        self.assertEqual(self.client.get(f'/payments/{payment_id}/deposit-receipt', headers=self.customer2).status_code, 404)
        self.assertEqual(self.client.get(f'/payments/{payment_id}/deposit-receipt', headers=self.owner).status_code, 200)
        self.assertEqual(self.client.get(f'/payments/{payment_id}/deposit-receipt', headers=self.system_admin).status_code, 200)

        rejected = self.client.patch(f'/bookings/{self.booking_id}/reject', headers=self.owner, json={'note': 'Sân cần bảo trì'})
        self.assertEqual(rejected.status_code, 200, rejected.text)
        pending_refund_receipt = self.client.get(f'/payments/{payment_id}/deposit-receipt', headers=self.customer1).json()
        self.assertEqual(pending_refund_receipt['deposit_status'], 'refund_pending')

        refunds = self.client.get('/refunds', headers=self.owner)
        refund = next(item for item in refunds.json()['items'] if item['booking_id'] == self.booking_id)
        completed = self.client.patch(f"/refunds/{refund['id']}/mark-refunded", headers=self.owner, json={
            'transaction_reference': 'RECEIPT-REFUND-001',
        })
        self.assertEqual(completed.status_code, 200, completed.text)
        refunded_receipt = self.client.get(f'/payments/{payment_id}/deposit-receipt', headers=self.customer1).json()
        self.assertEqual(refunded_receipt['deposit_status'], 'refunded')
        self.assertEqual(refunded_receipt['refund_status'], 'refunded')
        self.assertEqual(refunded_receipt['refund_amount'], 300000)


if __name__ == '__main__':
    unittest.main()
