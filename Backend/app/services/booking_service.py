from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from ..core.config import settings
from ..core.datetime_utils import as_utc
from ..core.ownership import management_owner_id, owns_field
from ..models.field import Booking, BookingStatus, Field
from ..models.invoice import Invoice
from ..models.payment import EscrowStatus, Payment, PaymentStatus, PaymentType
from ..models.refund import BookingActivity, RefundRequest, RefundStatus
from ..models.time_slot import TimeSlot
from ..models.user import User
from ..repositories.booking_repository import BookingRepository
from ..schemas.booking import BookingQuote, BookingResponse
from .audit_service import record_audit

class BookingService:
    CONFLICT_MESSAGE = 'Khung giờ này vừa được người khác đặt. Vui lòng chọn thời gian khác.'
    HOLD_DURATION = timedelta(minutes=15)
    REFUND_DEADLINE = timedelta(days=3)
    def __init__(self, repository: BookingRepository):
        self.repository = repository
        self.timezone = ZoneInfo(settings.TIMEZONE)

    def availability(self, *, booking_date: date, field_id: int | None, search: str | None, sport_type: str | None, location: str | None = None, start_time=None, max_price: float | None = None, sort_by: str = 'relevance'):
        self.repository.release_expired_holds()
        now = datetime.now(self.timezone)
        if booking_date < now.date():
            raise HTTPException(status_code=422, detail='Không thể tìm lịch trống trong quá khứ')
        result = self.repository.availability(booking_date=booking_date, field_id=field_id, search=search, sport_type=sport_type, location=location)
        if not result:
            return []
        fields, slots, bookings, blocks, maintenances = result
        response = []
        for field in fields:
            available = []
            for slot in slots:
                if slot.field_id != field.id:
                    continue
                if booking_date == now.date() and slot.start_time <= now.time().replace(tzinfo=None):
                    continue
                if start_time is not None and slot.start_time < start_time:
                    continue
                effective_price = slot.weekend_price if booking_date.weekday() >= 5 else slot.weekday_price
                effective_price = effective_price if effective_price is not None else slot.price
                if max_price is not None and Decimal(effective_price) > Decimal(str(max_price)):
                    continue
                occupied = any(
                    booking.field_id == field.id
                    and booking.start_time_snapshot < slot.end_time
                    and booking.end_time_snapshot > slot.start_time
                    for booking in bookings
                )
                blocked = any(block.field_id == field.id and block.start_time < slot.end_time and block.end_time > slot.start_time for block in blocks)
                maintained = any(
                    maintenance.field_id == field.id
                    and as_utc(maintenance.starts_at) < datetime.combine(booking_date, slot.end_time, tzinfo=self.timezone).astimezone(timezone.utc)
                    and as_utc(maintenance.ends_at) > datetime.combine(booking_date, slot.start_time, tzinfo=self.timezone).astimezone(timezone.utc)
                    for maintenance in maintenances
                )
                if not occupied and not blocked and not maintained:
                    available.append(slot)
            if available:
                response.append({'field': field, 'available_slots': available})
        if sort_by == 'price':
            response.sort(key=lambda item: min(float(slot.weekend_price if booking_date.weekday() >= 5 and slot.weekend_price is not None else slot.weekday_price if booking_date.weekday() < 5 and slot.weekday_price is not None else slot.price) for slot in item['available_slots']))
        elif sort_by == 'rating':
            response.sort(key=lambda item: (-float(item['field'].rating or 0), -int(item['field'].review_count or 0)))
        return response

    def create(self, payload, current_user: User) -> BookingResponse:
        owner_operator = self._can_manage(current_user)
        acting_as_customer = current_user.role == 'CUSTOMER' or (
            owner_operator and payload.customer_id is None and payload.customer_email is None
        )
        if acting_as_customer:
            if payload.customer_id and payload.customer_id != current_user.id:
                raise HTTPException(status_code=403, detail='CUSTOMER không thể đặt sân cho tài khoản khác')
            customer = current_user
        elif owner_operator:
            if payload.customer_id is None and payload.customer_email is None:
                # An approved partner keeps CUSTOMER capabilities on the same account.
                customer = current_user
            else:
                customer = self.repository.get_customer(payload.customer_id, payload.customer_email)
                if customer is None:
                    raise HTTPException(status_code=422, detail='Cần cung cấp CUSTOMER đang hoạt động bằng customer_id hoặc customer_email')
        else:
            raise HTTPException(status_code=403, detail='Bạn không có quyền tạo lịch đặt')
        values = self._schedule_values(payload.field_id, payload.time_slot_id, payload.booking_date, owner_user=current_user if owner_operator and not acting_as_customer else None)
        booking = Booking(
            booking_code=self._booking_code(), customer_id=customer.id,
            note=payload.note, status=BookingStatus.PENDING_PAYMENT.value,
            hold_expires_at=datetime.now(timezone.utc) + self.HOLD_DURATION, **values,
        )
        try:
            created = self.repository.create(booking)
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail=self.CONFLICT_MESSAGE)
        self._add_activity(created.id, current_user, 'booking_created', None, BookingStatus.PENDING_PAYMENT.value, {
            'booking_code': created.booking_code, 'hold_expires_at': created.hold_expires_at.isoformat() if created.hold_expires_at else None,
        })
        self.repository.db.commit()
        return self.response(self.repository.get(created.id))

    def quote(self, *, field_id: int, time_slot_id: int, booking_date: date) -> BookingQuote:
        values = self._schedule_values(field_id, time_slot_id, booking_date)
        return BookingQuote(
            field_id=field_id, time_slot_id=time_slot_id, booking_date=booking_date,
            total_amount=float(values['total_amount']), deposit_amount=float(values['deposit_amount']),
            remaining_amount=float(values['remaining_amount']), deposit_type=values['deposit_type'],
            deposit_value=float(values['deposit_value']), hold_minutes=int(self.HOLD_DURATION.total_seconds() / 60),
            free_cancellation_minutes=values['free_cancellation_minutes'],
            cancellation_policy_summary=self._policy_summary(values['free_cancellation_minutes']),
        )

    def list_my(self, user: User, **filters):
        self.repository.release_expired_holds()
        items, total = self.repository.list(customer_id=user.id, **filters)
        return [self.response(item) for item in items], total

    def list_manage(self, user: User, **filters):
        self.repository.release_expired_holds()
        owner_id = management_owner_id(user, self.repository.db)
        if owner_id is None:
            raise HTTPException(status_code=403, detail='Tài khoản quản lý chưa được gán cho OWNER')
        items, total = self.repository.list(customer_id=None, owner_id=owner_id, **filters)
        return [self.response(item) for item in items], total

    def get_for_user(self, booking_id: int, user: User) -> BookingResponse:
        self.repository.release_expired_holds()
        booking = self._booking_or_404(booking_id)
        if booking.customer_id != user.id and (not self._can_manage(user) or not owns_field(user, booking.field, self.repository.db)):
            raise HTTPException(status_code=403, detail='Bạn không được xem lịch đặt này')
        return self.response(booking)

    def invoice_for_user(self, booking_id: int, user: User):
        booking = self._booking_or_404(booking_id)
        if booking.customer_id != user.id and (not self._can_manage(user) or not owns_field(user, booking.field, self.repository.db)):
            raise HTTPException(status_code=403, detail='Bạn không được xem hóa đơn này')
        if booking.invoice is None and booking.status == BookingStatus.COMPLETED.value:
            self._ensure_invoice(booking, user)
            booking = self._booking_or_404(booking_id)
        if booking.invoice is None:
            raise HTTPException(status_code=404, detail='Booking chưa hoàn thành hoặc chưa có hóa đơn')
        return booking.invoice

    def update(self, booking_id: int, payload, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id)
        self._require_owned_booking(booking, user)
        if booking.status not in (BookingStatus.PENDING_PAYMENT.value, BookingStatus.PENDING_CONFIRMATION.value, BookingStatus.CONFIRMED.value):
            raise HTTPException(status_code=409, detail='Chỉ có thể đổi lịch đang chờ hoặc đã xác nhận')
        if self.repository.committed_payment_amount(booking.id) > 0:
            raise HTTPException(status_code=409, detail='Không thể đổi lịch sau khi đã phát sinh giao dịch thanh toán')
        values = self._schedule_values(payload.field_id, payload.time_slot_id, payload.booking_date, exclude_id=booking.id, owner_user=user)
        if self.repository.committed_payment_amount(booking.id) > values['total_amount']:
            raise HTTPException(status_code=409, detail='Không thể đổi sang khung giờ có giá thấp hơn tổng giao dịch đã thanh toán hoặc đang chờ')
        values['note'] = payload.note
        try:
            return self.response(self.repository.update(booking, values))
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail=self.CONFLICT_MESSAGE)

    def confirm(self, booking_id: int, note: str | None, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id)
        self._require_owned_booking(booking, user)
        if Decimal(booking.paid_amount or 0) < Decimal(booking.deposit_amount or 0):
            raise HTTPException(status_code=409, detail='Booking chưa thanh toán đủ tiền đặt cọc')
        return self._transition(booking_id, {BookingStatus.PENDING_CONFIRMATION.value}, BookingStatus.CONFIRMED.value, note, user)

    def reject(self, booking_id: int, note: str | None, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id, lock=True)
        self._require_owned_booking(booking, user)
        reason = (note or '').strip()
        if len(reason) < 3:
            raise HTTPException(status_code=422, detail='OWNER phải nhập lý do từ chối booking')
        if booking.status != BookingStatus.PENDING_CONFIRMATION.value:
            raise HTTPException(status_code=409, detail='Chỉ booking đang chờ chủ sân xác nhận mới có thể bị từ chối')
        paid = Decimal(booking.paid_amount or 0)
        if paid <= 0:
            raise HTTPException(status_code=409, detail='Booking chưa có tiền cọc để chuyển sang chờ hoàn')
        return self._cancel_by_owner(booking, reason, user, action='owner_rejected_booking')

    def cancellation_quote(self, booking_id: int, user: User):
        booking = self._booking_or_404(booking_id)
        if booking.customer_id != user.id and (not self._can_manage(user) or not owns_field(user, booking.field, self.repository.db)):
            raise HTTPException(status_code=403, detail='Bạn không được hủy lịch đặt này')
        if booking.status not in (BookingStatus.PENDING_PAYMENT.value, BookingStatus.PENDING_CONFIRMATION.value, BookingStatus.CONFIRMED.value):
            raise HTTPException(status_code=409, detail='Trạng thái hiện tại không thể hủy')
        return self._customer_cancellation_quote(booking)

    def cancel(self, booking_id: int, user: User, reason: str | None) -> BookingResponse:
        booking = self._booking_or_404(booking_id, lock=True)
        is_owner = self._can_manage(user) and owns_field(user, booking.field, self.repository.db)
        normalized_reason = (reason or '').strip()
        if is_owner:
            if len(normalized_reason) < 3:
                raise HTTPException(status_code=422, detail='OWNER phải nhập lý do hủy booking')
            if booking.status not in (
                BookingStatus.PENDING_PAYMENT.value, BookingStatus.PENDING_CONFIRMATION.value,
                BookingStatus.CONFIRMED.value,
            ):
                raise HTTPException(status_code=409, detail='Trạng thái hiện tại không thể bị chủ sân hủy')
            paid = Decimal(booking.paid_amount or 0)
            if paid > 0:
                return self._cancel_by_owner(booking, normalized_reason, user, action='owner_cancelled_booking')
            old_status = booking.status
            self.repository.flush_update(booking, {
                'status': BookingStatus.CANCELLED_BY_OWNER.value, 'hold_expires_at': None,
                'cancellation_reason': normalized_reason, 'cancelled_at': datetime.now(timezone.utc),
                'cancelled_by': user.id, 'refund_status': 'not_required', 'remaining_amount': Decimal(0),
            })
            self._add_activity(booking.id, user, 'owner_cancelled_booking', old_status, BookingStatus.CANCELLED_BY_OWNER.value, {'reason': normalized_reason, 'refund_amount': 0})
            self.repository.db.commit()
            return self.response(self.repository.get(booking.id))
        if user.role not in ('CUSTOMER', 'OWNER') or booking.customer_id != user.id:
            raise HTTPException(status_code=403, detail='Bạn không được hủy lịch đặt này')
        if len(normalized_reason) < 3:
            raise HTTPException(status_code=422, detail='Khách hàng phải nhập lý do hủy booking')
        if booking.status not in (
            BookingStatus.PENDING_PAYMENT.value, BookingStatus.PENDING_CONFIRMATION.value,
            BookingStatus.CONFIRMED.value,
        ):
            raise HTTPException(status_code=409, detail='Booking đã được xử lý hoặc không thể hủy')
        if booking.refund_request is not None:
            raise HTTPException(status_code=409, detail='Booking đã có yêu cầu hoàn tiền; không thể xử lý lần hai')
        quote = self._customer_cancellation_quote(booking)
        old_status = booking.status
        refund = Decimal(str(quote['refund_amount']))
        forfeited = Decimal(str(quote['forfeited_deposit_amount']))
        now = datetime.now(timezone.utc)
        for payment in booking.payments:
            if payment.status == PaymentStatus.PENDING.value:
                payment.status = PaymentStatus.FAILED.value
                payment.payment_status = PaymentStatus.FAILED.value
                payment.failed_reason = 'Booking đã bị hủy'
        if refund > 0:
            for paid_payment in booking.payments:
                if paid_payment.status == PaymentStatus.PAID.value and paid_payment.payment_type in (PaymentType.DEPOSIT.value, PaymentType.FULL.value):
                    paid_payment.refund_status = RefundStatus.REFUNDED.value
                    paid_payment.payment_status = PaymentStatus.REFUNDED.value
                    paid_payment.escrow_status = EscrowStatus.REFUNDED.value
                    paid_payment.refunded_at = now
            reference = f'SIM-REF-{datetime.now():%y%m%d}-{uuid4().hex[:8].upper()}'
            refund_payment = Payment(
                booking_id=booking.id, customer_id=booking.customer_id,
                owner_id=booking.field.owner_id, transaction_code=f'REF-{datetime.now():%y%m%d}-{uuid4().hex[:8].upper()}',
                amount=refund, total_amount=booking.total_amount, deposit_amount=booking.deposit_amount,
                remaining_amount=0, paid_amount=booking.paid_amount,
                payment_status=PaymentStatus.REFUNDED.value, payment_method='mock_online',
                payment_type=PaymentType.REFUND.value, status=PaymentStatus.REFUNDED.value,
                escrow_status=EscrowStatus.REFUNDED.value, provider='mock_refund',
                provider_reference=reference, verification_source='system_simulation',
                note='Hoàn 100% tiền cọc do khách hủy đúng hạn',
                refund_status=RefundStatus.REFUNDED.value, refunded_at=now,
            )
            self.repository.db.add(refund_payment)
            self.repository.db.flush()
            self.repository.db.add(RefundRequest(
                booking_id=booking.id, refund_payment_id=refund_payment.id, amount=refund,
                status=RefundStatus.REFUNDED.value, reason=normalized_reason, requested_by=user.id,
                requested_at=now, due_at=now, refunded_at=now, customer_confirmed_at=now,
                customer_action_by=user.id, transaction_reference=reference,
            ))
        elif forfeited > 0:
            for paid_payment in booking.payments:
                if paid_payment.status == PaymentStatus.PAID.value and paid_payment.payment_type in (PaymentType.DEPOSIT.value, PaymentType.FULL.value):
                    paid_payment.escrow_status = EscrowStatus.RELEASED.value
        self.repository.flush_update(booking, {
            'status': BookingStatus.CANCELLED_BY_CUSTOMER.value, 'hold_expires_at': None,
            'refundable_deposit_amount': refund, 'refund_amount': refund,
            'refund_status': 'not_required' if refund == 0 else RefundStatus.REFUNDED.value,
            'payment_status': PaymentStatus.REFUNDED.value if refund > 0 else booking.payment_status,
            'remaining_amount': Decimal(0), 'additional_payment_required': Decimal(0),
            'cancellation_reason': normalized_reason, 'cancelled_at': now, 'cancelled_by': user.id,
        })
        self._add_activity(booking.id, user, 'customer_cancelled_booking', old_status, BookingStatus.CANCELLED_BY_CUSTOMER.value, {
            'reason': normalized_reason, 'refund_amount': float(refund),
            'forfeited_deposit_amount': float(forfeited),
            'free_cancellation_minutes': quote['free_cancellation_minutes'],
            'is_late_cancellation': quote['is_late_cancellation'],
        })
        try:
            self.repository.db.commit()
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail='Booking vừa được hủy hoặc hoàn tiền; không thể xử lý lần hai')
        return self.response(self.repository.get(booking.id))

    def _customer_cancellation_quote(self, booking: Booking):
        scheduled_at = self._scheduled_at(booking)
        now = datetime.now(self.timezone)
        if scheduled_at <= now:
            raise HTTPException(status_code=409, detail='Không thể hủy lịch đã bắt đầu hoặc đã qua')
        deposit_paid = min(Decimal(booking.paid_amount or 0), Decimal(booking.deposit_amount or 0)).quantize(Decimal('0.01'))
        minutes = max(0, int((scheduled_at - now).total_seconds() // 60))
        free_minutes = int(booking.free_cancellation_minutes or 360)
        deadline = scheduled_at - timedelta(minutes=free_minutes)
        is_late = now > deadline
        refund = Decimal(0) if is_late else deposit_paid
        forfeited = deposit_paid if is_late else Decimal(0)
        return {
            'booking_id': booking.id, 'cancellable': True, 'minutes_before_start': minutes,
            'refund_percent': 0 if is_late else 100,
            'paid_deposit_amount': float(deposit_paid), 'refund_amount': float(refund),
            'forfeited_deposit_amount': float(forfeited),
            'free_cancellation_minutes': free_minutes,
            'free_cancellation_deadline': deadline,
            'is_late_cancellation': is_late,
            'warning_message': 'Bạn đã quá thời hạn hủy miễn phí. Nếu tiếp tục hủy, tiền đặt cọc sẽ không được hoàn lại.' if is_late and deposit_paid > 0 else None,
            'reason_required': True,
        }

    def _cancel_by_owner(self, booking: Booking, reason: str, user: User, *, action: str) -> BookingResponse:
        if booking.refund_request is not None:
            raise HTTPException(status_code=409, detail='Booking đã có yêu cầu hoàn tiền; không thể tạo yêu cầu lần hai')
        refund_amount = Decimal(booking.paid_amount or 0).quantize(Decimal('0.01'))
        if refund_amount <= 0:
            raise HTTPException(status_code=409, detail='Booking chưa phát sinh khoản tiền cần hoàn')
        now = datetime.now(timezone.utc)
        old_status = booking.status
        for payment in booking.payments:
            if payment.status == PaymentStatus.PENDING.value:
                payment.status = PaymentStatus.FAILED.value
                payment.payment_status = PaymentStatus.FAILED.value
                payment.failed_reason = 'Booking đã bị chủ sân hủy'
            elif payment.status == PaymentStatus.PAID.value and payment.payment_type != PaymentType.REFUND.value:
                payment.refund_status = RefundStatus.REFUND_PENDING.value
                payment.payment_status = RefundStatus.REFUND_PENDING.value
        self.repository.db.flush()
        refund_payment = Payment(
            booking_id=booking.id, customer_id=booking.customer_id,
            owner_id=booking.field.owner_id or user.id,
            transaction_code=f'REF-{datetime.now():%y%m%d}-{uuid4().hex[:8].upper()}',
            amount=refund_amount, total_amount=booking.total_amount,
            deposit_amount=booking.deposit_amount, remaining_amount=0,
            paid_amount=booking.paid_amount, payment_status=RefundStatus.REFUND_PENDING.value,
            payment_method='bank_transfer', payment_type=PaymentType.REFUND.value,
            status=PaymentStatus.PENDING.value, provider='manual_refund', refund_status=RefundStatus.REFUND_PENDING.value,
            note=reason,
        )
        self.repository.db.add(refund_payment)
        self.repository.db.flush()
        self.repository.db.add(RefundRequest(
            booking_id=booking.id, refund_payment_id=refund_payment.id, amount=refund_amount,
            status=RefundStatus.REFUND_PENDING.value, reason=reason, requested_by=user.id,
            requested_at=now, due_at=now + self.REFUND_DEADLINE,
        ))
        self.repository.flush_update(booking, {
            'status': BookingStatus.CANCELLED_BY_OWNER.value, 'hold_expires_at': None,
            'refundable_deposit_amount': refund_amount, 'refund_amount': refund_amount,
            'refund_status': RefundStatus.REFUND_PENDING.value,
            'payment_status': RefundStatus.REFUND_PENDING.value,
            'remaining_amount': Decimal(0), 'additional_payment_required': Decimal(0),
            'cancellation_reason': reason, 'cancelled_at': now, 'cancelled_by': user.id,
        })
        self._add_activity(booking.id, user, action, old_status, BookingStatus.CANCELLED_BY_OWNER.value, {
            'reason': reason, 'refund_amount': float(refund_amount), 'refund_due_at': (now + self.REFUND_DEADLINE).isoformat(),
        })
        try:
            self.repository.db.commit()
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail='Booking vừa được hủy hoặc đã có yêu cầu hoàn tiền')
        return self.response(self.repository.get(booking.id))

    def _add_activity(self, booking_id: int, user: User, action: str, from_status: str | None, to_status: str | None, details: dict):
        self.repository.db.add(BookingActivity(
            booking_id=booking_id, actor_id=user.id, actor_role=user.role,
            action=action, from_status=from_status, to_status=to_status, details=details,
        ))
        record_audit(self.repository.db, user, 'booking', booking_id, action, {'from_status': from_status, 'to_status': to_status, **details})

    def reschedule_quote(self, booking_id: int, payload, user: User):
        booking = self._booking_or_404(booking_id)
        self._authorize_reschedule(booking, user)
        values = self._schedule_values(
            payload.field_id, payload.time_slot_id, payload.booking_date,
            exclude_id=booking.id, owner_user=user if user.role == 'OWNER' else None,
        )
        if (booking.facility_id or booking.field_id) != (values['facility_id'] or values['field_id']):
            raise HTTPException(status_code=409, detail='Chỉ được đổi sang sân khác trong cùng cơ sở')
        old_total, new_total = Decimal(booking.total_amount), Decimal(values['total_amount'])
        difference = new_total - old_total
        paid = Decimal(booking.paid_amount or 0)
        additional = max(difference, Decimal(values['deposit_amount']) - paid, Decimal(0))
        return {
            'booking_id': booking.id, 'field_id': payload.field_id, 'time_slot_id': payload.time_slot_id,
            'booking_date': payload.booking_date, 'old_total_amount': float(old_total),
            'new_total_amount': float(new_total), 'price_difference': float(difference),
            'additional_payment_required': float(additional), 'credit_amount': float(max(-difference, Decimal(0))),
        }, values

    def reschedule(self, booking_id: int, payload, user: User) -> BookingResponse:
        quote, values = self.reschedule_quote(booking_id, payload, user)
        booking = self._booking_or_404(booking_id, lock=True)
        self._authorize_reschedule(booking, user)
        old_schedule = {
            'field_id': booking.field_id, 'field_name': booking.field.name,
            'booking_date': booking.booking_date.isoformat(),
            'start_time': booking.start_time_snapshot.isoformat(),
            'end_time': booking.end_time_snapshot.isoformat(),
            'total_amount': float(booking.total_amount),
        }
        paid = sum((Decimal(payment.amount) for payment in booking.payments if payment.status == 'paid' and payment.payment_type != 'refund'), Decimal(0))
        new_total = Decimal(values['total_amount'])
        status = BookingStatus.PENDING_PAYMENT.value if Decimal(str(quote['additional_payment_required'])) > 0 else BookingStatus.PENDING_CONFIRMATION.value
        values.update({
            'paid_amount': paid, 'remaining_amount': max(new_total - paid, Decimal(0)),
            'payment_status': 'paid' if paid >= new_total else 'partial' if paid > 0 else 'unpaid',
            # A lower price is an accounting credit for manual policy handling. It
            # must not fabricate a refund transaction or mutate old payments.
            'credit_amount': Decimal(str(quote['credit_amount'])),
            'additional_payment_required': Decimal(str(quote['additional_payment_required'])),
            'status': status, 'rescheduled_at': datetime.now(timezone.utc),
            'hold_expires_at': datetime.now(timezone.utc) + self.HOLD_DURATION if status == BookingStatus.PENDING_PAYMENT.value else None,
        })
        for payment in booking.payments:
            if payment.status == PaymentStatus.PENDING.value:
                payment.status = PaymentStatus.FAILED.value
                payment.payment_status = PaymentStatus.FAILED.value
                payment.failed_reason = 'Lịch đặt đã được đổi; cần tạo giao dịch theo giá mới'
        self._add_activity(booking.id, user, 'booking_rescheduled', booking.status, status, {
            'old_schedule': old_schedule,
            'new_schedule': {
                'field_id': values['field_id'], 'booking_date': values['booking_date'].isoformat(),
                'start_time': values['start_time_snapshot'].isoformat(),
                'end_time': values['end_time_snapshot'].isoformat(),
                'total_amount': float(new_total),
            },
            'price_difference': quote['price_difference'],
            'additional_payment_required': quote['additional_payment_required'],
            'credit_amount': quote['credit_amount'],
        })
        try:
            self.repository.flush_update(booking, values)
            self.repository.db.commit()
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail=self.CONFLICT_MESSAGE)
        return self.response(self.repository.get(booking.id))

    def start(self, booking_id: int, note: str | None, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id)
        self._require_owned_booking(booking, user)
        if booking.status != BookingStatus.CONFIRMED.value:
            raise HTTPException(status_code=409, detail='Chỉ booking đã xác nhận mới có thể bắt đầu')
        if self._scheduled_at(booking) > datetime.now(self.timezone):
            raise HTTPException(status_code=409, detail='Chưa đến giờ sử dụng sân')
        return self._transition(booking_id, {BookingStatus.CONFIRMED.value}, BookingStatus.IN_PROGRESS.value, note, user)

    def no_show(self, booking_id: int, note: str | None, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id)
        self._require_owned_booking(booking, user)
        if booking.status != BookingStatus.CONFIRMED.value:
            raise HTTPException(status_code=409, detail='Chỉ booking đã xác nhận mới có thể đánh dấu no-show')
        if self._scheduled_at(booking) > datetime.now(self.timezone):
            raise HTTPException(status_code=409, detail='Chưa đến giờ booking')
        return self._transition(booking_id, {BookingStatus.CONFIRMED.value}, BookingStatus.NO_SHOW.value, note, user)

    def complete(self, booking_id: int, note: str | None, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id)
        self._require_owned_booking(booking, user)
        if booking.status not in (BookingStatus.IN_PROGRESS.value, BookingStatus.CONFIRMED.value):
            raise HTTPException(status_code=409, detail='Chỉ lịch đang sử dụng mới có thể hoàn thành')
        scheduled_end = datetime.combine(booking.booking_date, booking.end_time_snapshot, tzinfo=self.timezone)
        if scheduled_end > datetime.now(self.timezone):
            raise HTTPException(status_code=409, detail='Chưa thể hoàn thành lịch chưa kết thúc')
        if Decimal(booking.remaining_amount or 0) > 0:
            raise HTTPException(status_code=409, detail='Cần thanh toán đủ số tiền còn lại trước khi hoàn tất booking')
        old_status = booking.status
        for payment in booking.payments:
            if payment.status == PaymentStatus.PAID.value and payment.payment_type != PaymentType.REFUND.value:
                payment.escrow_status = EscrowStatus.RELEASED.value
        self.repository.flush_update(booking, {'status': BookingStatus.COMPLETED.value, **self._note_update(note)})
        self._add_activity(booking.id, user, 'booking_completed_funds_released', old_status, BookingStatus.COMPLETED.value, {
            'released_amount': float(booking.paid_amount or 0), 'escrow_status': EscrowStatus.RELEASED.value,
        })
        self.repository.db.commit()
        booking = self.repository.get(booking.id)
        self._ensure_invoice(booking, user)
        return self.response(self.repository.get(booking.id))

    def _schedule_values(self, field_id: int, time_slot_id: int, booking_date: date, exclude_id: int | None = None, owner_user: User | None = None):
        self.repository.release_expired_holds()
        self.repository.begin_booking_write_lock()
        field = self.repository.lock_field(field_id)
        if field is None or field.status != 'available' or (field.facility is not None and not field.facility.is_active):
            raise HTTPException(status_code=409, detail='Sân không tồn tại hoặc đang ngừng hoạt động')
        if owner_user is not None and not owns_field(owner_user, field, self.repository.db):
            raise HTTPException(status_code=404, detail='Không tìm thấy sân')
        slot = self.repository.db.get(TimeSlot, time_slot_id)
        if slot is None or slot.field_id != field_id or not slot.is_active:
            raise HTTPException(status_code=409, detail='Khung giờ không tồn tại, đã khóa hoặc không thuộc sân đã chọn')
        scheduled_at = datetime.combine(booking_date, slot.start_time, tzinfo=self.timezone)
        if scheduled_at <= datetime.now(self.timezone):
            raise HTTPException(status_code=409, detail='Không thể đặt thời gian trong quá khứ')
        conflict = self.repository.find_conflict(
            field_id=field_id, booking_date=booking_date,
            start_time=slot.start_time, end_time=slot.end_time, exclude_id=exclude_id,
        )
        if conflict:
            raise HTTPException(status_code=409, detail=self.CONFLICT_MESSAGE)
        if self.repository.find_block(field_id=field_id, booking_date=booking_date, start_time=slot.start_time, end_time=slot.end_time):
            raise HTTPException(status_code=409, detail='Sân đã bị khóa hoặc bảo trì trong khoảng thời gian này')
        if self.repository.find_maintenance(field_id=field_id, booking_date=booking_date, start_time=slot.start_time, end_time=slot.end_time):
            raise HTTPException(status_code=409, detail='Khung giờ đang bảo trì và không khả dụng')
        special_price = slot.weekend_price if booking_date.weekday() >= 5 else slot.weekday_price
        price = Decimal(special_price if special_price is not None else slot.price)
        deposit_value = Decimal(field.deposit_value or 0)
        deposit = price * deposit_value / Decimal(100) if field.deposit_type == 'percentage' else deposit_value
        deposit = min(price, deposit).quantize(Decimal('0.01'))
        return {
            'facility_id': field.facility_id,
            'facility_name_snapshot': field.facility.name if field.facility else field.name,
            'field_id': field_id, 'time_slot_id': time_slot_id, 'booking_date': booking_date,
            'start_time_snapshot': slot.start_time, 'end_time_snapshot': slot.end_time,
            'price_snapshot': price, 'total_amount': price,
            'deposit_type': field.deposit_type, 'deposit_value': deposit_value,
            'deposit_amount': deposit, 'paid_amount': Decimal('0'),
            'remaining_amount': price, 'payment_status': 'unpaid',
            'cancellation_policy': field.cancellation_policy,
            'cancellation_refund_percent': field.cancellation_refund_percent,
            'free_cancellation_minutes': int(field.facility.free_cancellation_minutes if field.facility else 360),
        }

    def _transition(self, booking_id: int, allowed: set[str], status: str, note: str | None, user: User):
        booking = self._booking_or_404(booking_id)
        if booking.status not in allowed:
            raise HTTPException(status_code=409, detail='Chuyển trạng thái không hợp lệ')
        old_status = booking.status
        self.repository.flush_update(booking, {'status': status, 'hold_expires_at': None, **self._note_update(note)})
        details = {'note': note}
        if status == BookingStatus.NO_SHOW.value:
            released = Decimal(0)
            for payment in booking.payments:
                if payment.status == PaymentStatus.PAID.value and payment.payment_type != PaymentType.REFUND.value:
                    payment.escrow_status = EscrowStatus.RELEASED.value
                    released += Decimal(payment.amount)
            details.update({'released_amount': float(released), 'escrow_status': EscrowStatus.RELEASED.value})
        self._add_activity(booking.id, user, f'booking_{status}', old_status, status, details)
        self.repository.db.commit()
        return self.response(self.repository.get(booking.id))

    def _booking_or_404(self, booking_id: int, lock: bool = False) -> Booking:
        booking = self.repository.get(booking_id, lock=lock)
        if booking is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy lịch đặt')
        return booking

    def _authorize_reschedule(self, booking: Booking, user: User):
        if user.role not in ('CUSTOMER', 'OWNER') or booking.customer_id != user.id:
            raise HTTPException(status_code=403, detail='Bạn không được đổi lịch booking này')
        if booking.status not in (
            BookingStatus.PENDING_CONFIRMATION.value, BookingStatus.CONFIRMED.value,
        ):
            raise HTTPException(status_code=409, detail='Chỉ booking chờ xác nhận hoặc đã xác nhận mới có thể đổi lịch')
        if self._scheduled_at(booking) <= datetime.now(self.timezone):
            raise HTTPException(status_code=409, detail='Không thể đổi lịch đã bắt đầu hoặc đã qua')
        minutes_before_start = int((self._scheduled_at(booking) - datetime.now(self.timezone)).total_seconds() // 60)
        if minutes_before_start < int(booking.free_cancellation_minutes or 0):
            raise HTTPException(
                status_code=409,
                detail=f'Chỉ được đổi lịch trước giờ bắt đầu ít nhất {int(booking.free_cancellation_minutes or 0)} phút',
            )

    def _ensure_invoice(self, booking: Booking, user: User):
        if booking.invoice is not None:
            return booking.invoice
        paid_payments = [
            payment for payment in booking.payments
            if payment.status == PaymentStatus.PAID.value and payment.payment_type != PaymentType.REFUND.value
        ]
        deposit_paid = sum((Decimal(payment.amount) for payment in paid_payments if payment.payment_type == PaymentType.DEPOSIT.value), Decimal(0))
        remaining_paid = sum((Decimal(payment.amount) for payment in paid_payments if payment.payment_type == PaymentType.REMAINING.value), Decimal(0))
        refund = Decimal(booking.refund_amount or 0)
        total_received = deposit_paid + remaining_paid
        invoice = Invoice(
            invoice_number=f'INV-{datetime.now():%y%m%d}-{uuid4().hex[:8].upper()}',
            booking_id=booking.id, customer_id=booking.customer_id,
            owner_id=booking.field.owner_id or management_owner_id(user, self.repository.db), booking_code=booking.booking_code,
            customer_name=booking.customer.full_name, customer_email=booking.customer.email,
            facility_name=booking.facility_name_snapshot or booking.field.name,
            field_name=booking.field.name, booking_date=booking.booking_date,
            start_time=booking.start_time_snapshot, end_time=booking.end_time_snapshot,
            total_amount=booking.total_amount, deposit_amount=deposit_paid,
            remaining_payment_amount=remaining_paid, refund_amount=refund,
            net_received_amount=max(total_received - refund, Decimal(0)),
            payment_methods=', '.join(sorted({payment.payment_method for payment in paid_payments})) or 'legacy',
            paid_at=max((payment.paid_at for payment in paid_payments if payment.paid_at), default=None),
        )
        self.repository.db.add(invoice); self.repository.db.commit()
        return invoice

    def _require_owned_booking(self, booking: Booking, user: User):
        if not owns_field(user, booking.field, self.repository.db):
            raise HTTPException(status_code=404, detail='Không tìm thấy lịch đặt')

    @staticmethod
    def _can_manage(user: User) -> bool:
        return user.role == 'OWNER'

    def _scheduled_at(self, booking: Booking):
        return datetime.combine(booking.booking_date, booking.start_time_snapshot, tzinfo=self.timezone)

    @staticmethod
    def _note_update(note: str | None):
        return {'note': note.strip() or None} if note is not None else {}

    @staticmethod
    def _policy_summary(minutes: int):
        hours = minutes / 60
        label = f'{int(hours)} giờ' if hours.is_integer() else f'{minutes} phút'
        return f'Hủy trước giờ chơi ít nhất {label}: hoàn 100% tiền cọc. Hủy muộn hơn: không hoàn tiền cọc.'

    @staticmethod
    def _booking_code():
        return f'SH-{datetime.now():%y%m%d}-{uuid4().hex[:6].upper()}'

    @staticmethod
    def response(booking: Booking) -> BookingResponse:
        paid = sum((Decimal(payment.amount) for payment in booking.payments if payment.status == 'paid' and payment.payment_type != 'refund'), Decimal(0))
        pending = any(payment.status == 'pending' and payment.payment_type != 'refund' for payment in booking.payments)
        refund_states = {'refund_pending', 'refund_overdue', 'refunded', 'disputed'}
        payment_status = booking.refund_status if booking.refund_status in refund_states else 'paid' if paid >= Decimal(booking.total_amount) else 'partial' if paid > 0 else 'pending' if pending else 'unpaid'
        total = Decimal(booking.total_amount)
        deposit = Decimal(booking.deposit_amount or 0)
        remaining = Decimal(0) if booking.status in (
            BookingStatus.CANCELLED_BY_OWNER.value, BookingStatus.CANCELLED_BY_CUSTOMER.value,
            BookingStatus.CANCELLED.value,
        ) else max(total - paid, Decimal(0))
        duration = (datetime.combine(date.min, booking.end_time_snapshot) - datetime.combine(date.min, booking.start_time_snapshot)).seconds // 60
        return BookingResponse.model_validate({
            'id': booking.id, 'booking_code': booking.booking_code,
            'customer_id': booking.customer_id, 'customer_name': booking.customer.full_name,
            'customer_email': booking.customer.email, 'customer_phone': booking.customer.phone,
            'facility_id': booking.facility_id,
            'facility_name': booking.facility_name_snapshot or (booking.facility.name if booking.facility else booking.field.name),
            'facility_hotline': (booking.facility.contact_phone or '0901 234 567') if booking.facility else '0901 234 567',
            'field_id': booking.field_id,
            'field_name': booking.field.name, 'sport_type': booking.field.sport_type,
            'location': booking.field.location, 'time_slot_id': booking.time_slot_id,
            'time_slot_name': booking.time_slot.name, 'booking_date': booking.booking_date,
            'start_time_snapshot': booking.start_time_snapshot,
            'end_time_snapshot': booking.end_time_snapshot,
            'price_snapshot': booking.price_snapshot, 'total_amount': total,
            'deposit_type': booking.deposit_type, 'deposit_value': booking.deposit_value,
            'deposit_amount': deposit, 'paid_amount': paid,
            'additional_paid_amount': max(paid - deposit, Decimal(0)),
            'remaining_amount': remaining, 'payment_status': payment_status,
            'status': booking.status, 'note': booking.note,
            'hold_expires_at': as_utc(booking.hold_expires_at),
            'created_at': as_utc(booking.created_at), 'updated_at': as_utc(booking.updated_at),
            'duration_minutes': duration, 'cancellation_policy': booking.cancellation_policy,
            'cancellation_refund_percent': booking.cancellation_refund_percent,
            'free_cancellation_minutes': booking.free_cancellation_minutes,
            'refundable_deposit_amount': booking.refundable_deposit_amount,
            'refund_amount': booking.refund_amount or 0, 'credit_amount': booking.credit_amount or 0,
            'additional_payment_required': booking.additional_payment_required or 0,
            'refund_status': booking.refund_status,
            'cancellation_reason': booking.cancellation_reason,
            'cancelled_at': as_utc(booking.cancelled_at),
            'cancelled_by': booking.cancelled_by,
            'rescheduled_at': as_utc(booking.rescheduled_at),
            'reviewed': booking.review is not None,
            'timeline': [{
                'id': activity.id, 'action': activity.action, 'actor_id': activity.actor_id,
                'actor_name': activity.actor.full_name if activity.actor else 'Hệ thống',
                'actor_role': activity.actor_role, 'from_status': activity.from_status,
                'to_status': activity.to_status, 'details': activity.details or {},
                'created_at': as_utc(activity.created_at),
            } for activity in booking.activities],
        })
