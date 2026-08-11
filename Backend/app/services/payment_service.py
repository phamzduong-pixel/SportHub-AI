from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from types import SimpleNamespace
from urllib.parse import quote, urlencode

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from ..core.config import settings
from ..core.datetime_utils import as_utc
from ..core.ownership import management_owner_id, owns_field
from ..models.field import BookingStatus
from ..models.payment import EscrowStatus, Payment, PaymentMethod, PaymentStatus, PaymentType
from ..models.refund import BookingActivity, RefundRequest, RefundStatus
from .audit_service import record_audit
from ..models.user import User
from ..repositories.payment_repository import PaymentRepository
from ..schemas.payment import DepositReceiptResponse, PaymentResponse, PaymentSummary


class PaymentService:
    def __init__(self, repository: PaymentRepository):
        self.repository = repository

    def create(self, payload, user: User) -> PaymentResponse:
        if payload.payment_method == PaymentMethod.MOCK_ONLINE and settings.PAYMENT_MODE != 'demo':
            raise HTTPException(status_code=403, detail='Mock online payments are disabled in production')
        booking = self._booking_or_404(payload.booking_id, lock=True)
        self._authorize_booking(booking, user)
        self._ensure_booking_payable(booking)
        now = datetime.now(timezone.utc)
        expires_at = booking.hold_expires_at
        if booking.status == BookingStatus.PENDING_PAYMENT.value and expires_at and expires_at.replace(tzinfo=expires_at.tzinfo or timezone.utc) <= now:
            self.repository.update_booking(booking, {'status': BookingStatus.EXPIRED.value, 'hold_expires_at': None})
            raise HTTPException(status_code=409, detail='Thời gian giữ chỗ đã hết. Vui lòng chọn lại khung giờ.')

        paid, pending = self.repository.totals(booking.id)
        total = Decimal(booking.total_amount).quantize(Decimal('0.01'))
        deposit = Decimal(booking.deposit_amount or 0).quantize(Decimal('0.01'))
        if pending > 0:
            raise HTTPException(status_code=409, detail='Booking đang có một giao dịch chờ xử lý')

        if payload.payment_type == PaymentType.REFUND:
            raise HTTPException(status_code=403, detail='CUSTOMER không thể tự tạo giao dịch hoàn tiền')
        requested_type = PaymentType.REMAINING if payload.payment_type == PaymentType.FULL else payload.payment_type

        if requested_type == PaymentType.DEPOSIT:
            if booking.status not in (BookingStatus.PENDING_PAYMENT.value, BookingStatus.PENDING_CONFIRMATION.value, 'pending') or paid > 0:
                raise HTTPException(status_code=409, detail='Tiền đặt cọc đã được thanh toán hoặc booking không còn chờ đặt cọc')
            # Compatibility for legacy rows created before deposit snapshots existed.
            amount = deposit or (payload.amount or Decimal(0)).quantize(Decimal('0.01'))
            if amount <= 0:
                raise HTTPException(status_code=409, detail='Booking chưa có mức đặt cọc hợp lệ')
        else:
            reschedule_due = Decimal(booking.additional_payment_required or 0)
            is_reschedule_payment = booking.status == BookingStatus.PENDING_PAYMENT.value and paid > 0 and reschedule_due > 0
            if not is_reschedule_payment and (paid < deposit or booking.status not in (BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value)):
                raise HTTPException(status_code=409, detail='Cần thanh toán tiền đặt cọc trước khi thanh toán số tiền còn lại')
            amount = reschedule_due if is_reschedule_payment else (total - paid)
            if amount <= 0:
                raise HTTPException(status_code=409, detail='Booking đã được thanh toán đầy đủ')

        if payload.amount is not None and payload.amount.quantize(Decimal('0.01')) != amount:
            raise HTTPException(status_code=422, detail=f'Số tiền phải thanh toán do hệ thống tính là {amount}')

        bank_values = {}
        if payload.payment_method == PaymentMethod.BANK_TRANSFER:
            suffix = '' if requested_type == PaymentType.DEPOSIT else ' FINAL'
            transfer_content = f"SPORTHUB {booking.booking_code.replace('-', '')}{suffix}"
            query = urlencode({
                'amount': str(int(amount)), 'addInfo': transfer_content,
                'accountName': settings.BANK_ACCOUNT_NAME,
            })
            bank_values = {
                'bank_id': settings.BANK_ID, 'bank_name': settings.BANK_NAME,
                'bank_account_no': settings.BANK_ACCOUNT_NO,
                'bank_account_name': settings.BANK_ACCOUNT_NAME,
                'transfer_content': transfer_content,
                'qr_url': f"https://img.vietqr.io/image/{quote(settings.BANK_ID)}-{quote(settings.BANK_ACCOUNT_NO)}-compact2.png?{query}",
                'expires_at': booking.hold_expires_at,
            }
        payment = Payment(
            booking_id=booking.id, customer_id=booking.customer_id, owner_id=self._owner_id(booking),
            transaction_code=self._transaction_code(), amount=amount,
            total_amount=total, deposit_amount=deposit, paid_amount=paid,
            remaining_amount=max(total - paid, Decimal(0)), payment_status=PaymentStatus.PENDING.value,
            payment_method=payload.payment_method.value, payment_type=requested_type.value,
            status=PaymentStatus.PENDING.value, provider='vietqr' if payload.payment_method == PaymentMethod.BANK_TRANSFER else payload.payment_method.value,
            note=payload.note, **bank_values,
        )
        try:
            return self.response(self.repository.create(payment))
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail='Không thể tạo mã giao dịch, vui lòng thử lại')

    def create_bank_intent(self, payload, user: User) -> PaymentResponse:
        request = SimpleNamespace(
            booking_id=payload.booking_id, amount=None,
            payment_method=PaymentMethod.BANK_TRANSFER,
            payment_type=payload.payment_type, note=None,
        )
        return self.create(request, user)

    def list_my(self, user: User, **filters):
        items, total = self.repository.list(customer_id=user.id, **filters)
        return [self.response(item) for item in items], total

    def list_manage(self, user: User, **filters):
        owner_id = management_owner_id(user, self.repository.db)
        if owner_id is None:
            raise HTTPException(status_code=403, detail='Tài khoản quản lý chưa được gán cho OWNER')
        items, total = self.repository.list(customer_id=None, owner_id=owner_id, **filters)
        return [self.response(item) for item in items], total

    def get_for_user(self, payment_id: int, user: User) -> PaymentResponse:
        payment = self._payment_or_404(payment_id)
        self._authorize_booking(payment.booking, user)
        payment = self._expire_if_needed(payment)
        return self.response(payment)

    def deposit_receipt(self, payment_id: int, user: User) -> DepositReceiptResponse:
        payment = self._payment_or_404(payment_id)
        booking = payment.booking
        is_customer = booking.customer_id == user.id and user.role in ('CUSTOMER', 'OWNER')
        is_owner = user.role == 'OWNER' and owns_field(user, booking.field, self.repository.db)
        is_admin = user.role == 'SYSTEM_ADMIN'
        if not (is_customer or is_owner or is_admin):
            # Do not reveal whether a payment ID belonging to another tenant exists.
            raise HTTPException(status_code=404, detail='Không tìm thấy biên lai đặt cọc')
        if payment.payment_type != PaymentType.DEPOSIT.value or payment.status != PaymentStatus.PAID.value or not payment.paid_at:
            raise HTTPException(status_code=409, detail='Giao dịch chưa có biên lai đặt cọc hợp lệ')

        refund_status = booking.refund_status or payment.refund_status or 'not_requested'
        refunded = refund_status == RefundStatus.REFUNDED.value
        if refunded:
            status_message = 'Tiền cọc đã được hoàn cho khách hàng.'
            deposit_status = 'refunded'
        elif booking.status == BookingStatus.PENDING_CONFIRMATION.value:
            status_message = 'Đã thanh toán cọc – Đang chờ chủ sân xác nhận.'
            deposit_status = 'paid_pending_confirmation'
        elif booking.status in (BookingStatus.REJECTED.value, BookingStatus.CANCELLED_BY_OWNER.value):
            status_message = 'Chủ sân đã từ chối – Tiền cọc đang chờ hoàn.'
            deposit_status = 'refund_pending'
        else:
            status_message = 'Đã thanh toán cọc.'
            deposit_status = 'paid'

        facility_name = booking.facility_name_snapshot or (
            booking.field.facility.name if booking.field.facility else booking.field.location
        )
        return DepositReceiptResponse.model_validate({
            'receipt_number': f'REC-{payment.transaction_code}',
            'booking_id': booking.id,
            'booking_code': booking.booking_code,
            'customer_name': booking.customer.full_name,
            'facility_name': facility_name,
            'facility_address': booking.field.location,
            'field_name': booking.field.name,
            'sport_type': booking.field.sport_type,
            'booking_date': booking.booking_date,
            'start_time': booking.start_time_snapshot.strftime('%H:%M'),
            'end_time': booking.end_time_snapshot.strftime('%H:%M'),
            'total_amount': payment.total_amount,
            'deposit_paid': payment.amount,
            'remaining_amount': max(Decimal(payment.total_amount) - Decimal(payment.amount), Decimal(0)),
            'transaction_code': payment.transaction_code,
            'payment_method': payment.payment_method,
            'bank_name': payment.bank_name,
            'paid_at': as_utc(payment.paid_at),
            'booking_status': booking.status,
            'deposit_status': deposit_status,
            'status_message': status_message,
            'refund_status': refund_status,
            'refund_amount': booking.refund_amount or 0,
            'refunded_at': as_utc(payment.refunded_at or (
                booking.refund_request.refunded_at if booking.refund_request else None
            )),
        })

    def confirm(self, payment_id: int, user: User, note: str | None) -> PaymentResponse:
        payment = self._payment_or_404(payment_id, lock=True)
        if payment.payment_method == PaymentMethod.BANK_TRANSFER.value and settings.PAYMENT_MODE == 'production':
            raise HTTPException(status_code=403, detail='Production bank transfers must be verified by webhook')
        self._authorize_confirmation(payment, user)
        return self._settle_verified(payment, confirmed_by=user.id, verification_source='manual', note=note)

    def demo_confirm(self, payment_id: int, user: User) -> PaymentResponse:
        if settings.PAYMENT_MODE != 'demo':
            raise HTTPException(status_code=403, detail='Demo payment simulation is disabled in production')
        payment = self._payment_or_404(payment_id, lock=True)
        if payment.payment_type == PaymentType.REFUND.value:
            raise HTTPException(status_code=403, detail='Hoàn tiền chỉ do OWNER xác nhận')
        self._authorize_booking(payment.booking, user)
        if payment.payment_method != PaymentMethod.BANK_TRANSFER.value:
            raise HTTPException(status_code=409, detail='Payment is not a bank QR intent')
        return self._settle_verified(
            payment, confirmed_by=None, verification_source='demo_simulator',
            provider_reference=f'DEMO-{payment.transaction_code}', note='DEMO bank transfer verified',
        )

    def confirm_webhook(self, payload) -> PaymentResponse:
        existing = self.repository.get_by_provider_reference(payload.provider_reference)
        if existing:
            if existing.transfer_content != payload.transfer_content or Decimal(existing.amount) != payload.amount:
                raise HTTPException(status_code=409, detail='Provider reference was already used for another payment')
            return self.response(existing)
        payment = self.repository.get_by_transfer_content(payload.transfer_content, lock=True)
        if payment is None:
            raise HTTPException(status_code=404, detail='No payment intent matches the transfer content')
        if Decimal(payment.amount) != payload.amount.quantize(Decimal('0.01')):
            raise HTTPException(status_code=422, detail='Received amount does not match the payment intent')
        return self._settle_verified(
            payment, confirmed_by=None, verification_source='bank_webhook',
            provider_reference=payload.provider_reference, note='Verified by bank webhook',
        )

    def _settle_verified(self, payment: Payment, *, confirmed_by: int | None, verification_source: str, note: str | None, provider_reference: str | None = None) -> PaymentResponse:
        if payment.payment_type == PaymentType.REFUND.value:
            return self._settle_refund(payment, confirmed_by, verification_source, note, provider_reference)
        payment = self._expire_if_needed(payment)
        if payment.status == PaymentStatus.PAID.value:
            return self.response(self.repository.get(payment.id))
        if payment.status != PaymentStatus.PENDING.value:
            raise HTTPException(status_code=409, detail='Chỉ giao dịch đang chờ mới có thể xác nhận')
        self._ensure_booking_payable(payment.booking)
        paid, _ = self.repository.totals(payment.booking_id, exclude_id=payment.id)
        new_paid = paid + Decimal(payment.amount)
        total = Decimal(payment.booking.total_amount)
        if new_paid > total:
            raise HTTPException(status_code=409, detail='Xác nhận sẽ làm tổng thanh toán vượt quá tiền đặt sân')
        remaining = max(total - new_paid, Decimal(0))
        state = 'paid' if remaining == 0 else 'partial'
        deposit = Decimal(payment.booking.deposit_amount or payment.amount)
        initial_statuses = (BookingStatus.PENDING_PAYMENT.value, 'pending')
        is_reschedule_payment = Decimal(payment.booking.additional_payment_required or 0) > 0
        if payment.booking.status in initial_statuses and not is_reschedule_payment and new_paid < deposit:
            raise HTTPException(status_code=409, detail='Giao dịch không đủ mức đặt cọc của booking')

        payment_data = {
            'status': PaymentStatus.PAID.value, 'payment_status': state,
            'escrow_status': EscrowStatus.HELD.value,
            'total_amount': total, 'deposit_amount': deposit,
            'paid_amount': new_paid, 'remaining_amount': remaining,
            'paid_at': datetime.now(timezone.utc), 'confirmed_by': confirmed_by,
            'provider_reference': provider_reference or payment.provider_reference,
            'verification_source': verification_source,
            **self._note_update(note),
        }
        booking_data = {
            'deposit_amount': deposit, 'paid_amount': new_paid,
            'remaining_amount': remaining, 'payment_status': state,
        }
        if payment.booking.status in initial_statuses:
            booking_data.update({
                'status': BookingStatus.PENDING_CONFIRMATION.value,
                'hold_expires_at': None,
                'additional_payment_required': Decimal(0),
            })
        activity_actor_id = confirmed_by or payment.booking.customer_id
        activity_actor = self.repository.db.get(User, activity_actor_id)
        self.repository.db.add(BookingActivity(
            booking_id=payment.booking_id, actor_id=activity_actor_id,
            actor_role=activity_actor.role if activity_actor else None,
            action='deposit_held' if payment.payment_type == PaymentType.DEPOSIT.value else 'remaining_payment_held',
            from_status=payment.booking.status, to_status=booking_data.get('status', payment.booking.status),
            details={'payment_id': payment.id, 'transaction_code': payment.transaction_code, 'amount': float(payment.amount), 'escrow_status': EscrowStatus.HELD.value},
        ))
        return self.response(self.repository.settle(payment, payment_data, payment.booking, booking_data))

    def _settle_refund(self, payment: Payment, confirmed_by: int | None, verification_source: str, note: str | None, provider_reference: str | None):
        if payment.status == PaymentStatus.REFUNDED.value:
            return self.response(self.repository.get(payment.id))
        if payment.status != PaymentStatus.PENDING.value:
            raise HTTPException(status_code=409, detail='Chỉ khoản hoàn đang chờ mới có thể xác nhận')
        if payment.booking.status not in (BookingStatus.CANCELLED.value, BookingStatus.REJECTED.value, BookingStatus.CANCELLED_BY_OWNER.value):
            raise HTTPException(status_code=409, detail='Chỉ booking đã hủy mới có thể hoàn tiền')
        now = datetime.now(timezone.utc)
        reference = provider_reference or payment.provider_reference or payment.transaction_code
        request = self.repository.db.scalar(select(RefundRequest).where(RefundRequest.booking_id == payment.booking_id).with_for_update())
        if request is not None:
            request.status = RefundStatus.REFUNDED.value
            request.processed_by = confirmed_by
            request.refunded_at = now
            request.transaction_reference = request.transaction_reference or reference
        self.repository.db.execute(update(Payment).where(
            Payment.booking_id == payment.booking_id, Payment.payment_type != PaymentType.REFUND.value,
            Payment.status == PaymentStatus.PAID.value,
        ).values(refund_status=RefundStatus.REFUNDED.value, payment_status=PaymentStatus.REFUNDED.value, escrow_status=EscrowStatus.REFUNDED.value))
        actor = self.repository.db.get(User, confirmed_by) if confirmed_by else payment.booking.customer
        self.repository.db.add(BookingActivity(
            booking_id=payment.booking_id, actor_id=confirmed_by, actor_role=actor.role if actor else None,
            action='refund_completed', from_status=payment.booking.refund_status,
            to_status=RefundStatus.REFUNDED.value,
            details={'payment_id': payment.id, 'refund_id': request.id if request else None, 'amount': float(payment.amount), 'transaction_reference': reference},
        ))
        if actor:
            record_audit(self.repository.db, actor, 'refund', request.id if request else payment.id, 'refund_completed', {'booking_id': payment.booking_id, 'amount': float(payment.amount), 'transaction_reference': reference})
        return self.response(self.repository.settle(payment, {
            'status': PaymentStatus.REFUNDED.value, 'payment_status': PaymentStatus.REFUNDED.value,
            'escrow_status': EscrowStatus.REFUNDED.value,
            'refunded_at': now, 'confirmed_by': confirmed_by,
            'provider_reference': reference,
            'verification_source': verification_source, **self._note_update(note),
        }, payment.booking, {'refund_status': 'refunded', 'payment_status': 'refunded'}))

    def cancel(self, payment_id: int, user: User, note: str | None) -> PaymentResponse:
        return self._stop_pending(payment_id, user, PaymentStatus.CANCELLED.value, note)

    def fail(self, payment_id: int, user: User, note: str | None) -> PaymentResponse:
        return self._stop_pending(payment_id, user, PaymentStatus.FAILED.value, note)

    def _stop_pending(self, payment_id: int, user: User, status: str, note: str | None) -> PaymentResponse:
        payment = self._payment_or_404(payment_id, lock=True)
        self._authorize_booking(payment.booking, user)
        if payment.status != PaymentStatus.PENDING.value:
            raise HTTPException(status_code=409, detail='Chỉ giao dịch đang chờ mới có thể cập nhật')
        updated = self.repository.update(payment, {
            'status': status, 'payment_status': status,
            'escrow_status': EscrowStatus.FAILED.value,
            'failed_reason': note or ('Giao dịch thất bại' if status == PaymentStatus.FAILED.value else None),
            **self._note_update(note),
        })
        if updated.booking.status == BookingStatus.PENDING_PAYMENT.value:
            self.repository.update_booking(updated.booking, {'status': BookingStatus.EXPIRED.value, 'hold_expires_at': None})
            updated = self.repository.get(updated.id)
        return self.response(updated)

    def summary(self, booking_id: int, user: User) -> PaymentSummary:
        booking = self._booking_or_404(booking_id)
        self._authorize_booking(booking, user)
        payments = [self._expire_if_needed(item) for item in self.repository.list_for_booking(booking_id)]
        paid, pending = self.repository.totals(booking_id)
        total = Decimal(booking.total_amount)
        deposit = Decimal(booking.deposit_amount or 0)
        remaining = max(total - paid, Decimal('0'))
        state = 'paid' if remaining == 0 else ('partial' if paid > 0 else 'unpaid')
        return PaymentSummary(
            booking_id=booking.id, booking_code=booking.booking_code,
            total_amount=float(total), deposit_amount=float(deposit),
            additional_paid_amount=float(max(paid - deposit, Decimal(0))),
            paid_amount=float(paid), pending_amount=float(pending),
            remaining_amount=float(remaining), payment_status=state,
            transactions=[self.response(item) for item in payments],
        )

    def _authorize_confirmation(self, payment: Payment, user: User):
        if payment.payment_method in (PaymentMethod.CASH.value, PaymentMethod.BANK_TRANSFER.value):
            if not self._can_manage(user):
                raise HTTPException(status_code=403, detail='Cần quyền payments.manage để xác nhận tiền mặt hoặc chuyển khoản')
            if not owns_field(user, payment.booking.field, self.repository.db):
                raise HTTPException(status_code=404, detail='Không tìm thấy giao dịch')
            return
        self._authorize_booking(payment.booking, user)

    def _authorize_booking(self, booking, user: User):
        if booking.customer_id != user.id and (not self._can_manage(user) or not owns_field(user, booking.field, self.repository.db)):
            raise HTTPException(status_code=403, detail='Bạn không được truy cập thanh toán của lịch đặt này')

    @staticmethod
    def _ensure_booking_payable(booking):
        if booking.status in (
            BookingStatus.CANCELLED.value, BookingStatus.CANCELLED_BY_CUSTOMER.value,
            BookingStatus.CANCELLED_BY_OWNER.value, BookingStatus.EXPIRED.value,
            BookingStatus.FAILED.value, 'rejected',
        ):
            raise HTTPException(status_code=409, detail='Không thể thanh toán cho lịch đã hủy hoặc hết hạn')

    def _booking_or_404(self, booking_id: int, lock: bool = False):
        booking = self.repository.get_booking(booking_id, lock=lock)
        if booking is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy lịch đặt')
        return booking

    def _payment_or_404(self, payment_id: int, lock: bool = False):
        payment = self.repository.get(payment_id, lock=lock)
        if payment is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy giao dịch')
        return payment

    def _expire_if_needed(self, payment: Payment) -> Payment:
        if payment.status != PaymentStatus.PENDING.value or not payment.expires_at:
            return payment
        expires_at = payment.expires_at.replace(tzinfo=payment.expires_at.tzinfo or timezone.utc)
        if expires_at > datetime.now(timezone.utc):
            return payment
        booking_data = {}
        if payment.booking.status == BookingStatus.PENDING_PAYMENT.value:
            booking_data = {'status': BookingStatus.EXPIRED.value, 'hold_expires_at': None}
        return self.repository.settle(
            payment, {
            'status': PaymentStatus.FAILED.value,
            'payment_status': PaymentStatus.FAILED.value,
            'escrow_status': EscrowStatus.FAILED.value,
                'failed_reason': 'Hết thời gian thanh toán',
            },
            payment.booking, booking_data,
        )

    def _owner_id(self, booking) -> int:
        if booking.field.owner_id:
            return booking.field.owner_id
        owner_ids = list(self.repository.db.scalars(
            select(User.id).where(User.role == 'OWNER').limit(2)
        ))
        if len(owner_ids) == 1:
            return owner_ids[0]
        raise HTTPException(status_code=409, detail='Sân chưa được gán cho chủ sở hữu hợp lệ')

    @staticmethod
    def _can_manage(user: User) -> bool:
        return user.role == 'OWNER'

    @staticmethod
    def _note_update(note: str | None):
        return {'note': note.strip() or None} if note is not None else {}

    @staticmethod
    def _transaction_code():
        return f'PAY-{datetime.now():%y%m%d}-{uuid4().hex[:8].upper()}'

    def response(self, payment: Payment) -> PaymentResponse:
        booking = payment.booking
        invoice = None
        if payment.status == PaymentStatus.PAID.value and payment.paid_at:
            invoice = {
                'invoice_number': f'INV-{payment.transaction_code}',
                'transaction_code': payment.transaction_code,
                'booking_code': booking.booking_code,
                'customer_name': booking.customer.full_name,
                'customer_email': booking.customer.email,
                'field_name': booking.field.name,
                'facility_name': booking.facility_name_snapshot or (
                    booking.field.facility.name if booking.field.facility else booking.field.location
                ),
                'booking_date': booking.booking_date,
                'total_amount': payment.total_amount,
                'deposit_amount': payment.deposit_amount,
                'remaining_payment_amount': max(Decimal(payment.paid_amount) - Decimal(payment.deposit_amount), Decimal(0)),
                'paid_amount': payment.paid_amount,
                'remaining_amount': payment.remaining_amount,
                'payment_method': payment.payment_method,
                'bank_name': payment.bank_name,
                'paid_at': as_utc(payment.paid_at),
            }
        return PaymentResponse.model_validate({
            'id': payment.id, 'booking_id': payment.booking_id,
            'booking_code': booking.booking_code,
            'customer_id': payment.customer_id or booking.customer_id,
            'owner_id': payment.owner_id or self._owner_id(booking),
            'customer_name': booking.customer.full_name, 'field_name': booking.field.name,
            'booking_date': booking.booking_date, 'booking_total': booking.total_amount,
            'transaction_code': payment.transaction_code, 'amount': payment.amount,
            'total_amount': payment.total_amount, 'deposit_amount': payment.deposit_amount,
            'remaining_amount': payment.remaining_amount, 'paid_amount': payment.paid_amount,
            'payment_status': payment.payment_status,
            'bank_id': payment.bank_id, 'bank_name': payment.bank_name,
            'bank_account_no': payment.bank_account_no,
            'bank_account_name': payment.bank_account_name,
            'transfer_content': payment.transfer_content, 'qr_url': payment.qr_url,
            'expires_at': as_utc(payment.expires_at),
            'provider_reference': payment.provider_reference,
            'provider': payment.provider,
            'verification_source': payment.verification_source,
            'failed_reason': payment.failed_reason,
            'refund_status': payment.refund_status,
            'payment_mode': settings.PAYMENT_MODE,
            'payment_method': payment.payment_method, 'payment_type': payment.payment_type,
            'status': payment.status, 'escrow_status': payment.escrow_status, 'paid_at': as_utc(payment.paid_at),
            'refunded_at': as_utc(payment.refunded_at),
            'confirmed_by': payment.confirmed_by,
            'confirmer_name': payment.confirmer.full_name if payment.confirmer else None,
            'note': payment.note, 'invoice': invoice,
            'created_at': as_utc(payment.created_at), 'updated_at': as_utc(payment.updated_at),
        })
