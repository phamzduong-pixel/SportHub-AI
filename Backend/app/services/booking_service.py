from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from ..core.config import settings
from ..core.datetime_utils import as_utc
from ..core.ownership import management_owner_id, owns_field
from ..models.field import Booking, BookingSlot, BookingStatus, Field
from ..models.invoice import Invoice
from ..models.payment import EscrowStatus, Payment, PaymentStatus, PaymentType
from ..models.product import BookingProductItem
from ..models.refund import BookingActivity, RefundRequest, RefundStatus
from ..models.time_slot import TimeSlot
from ..models.user import User
from ..repositories.booking_repository import BookingRepository
from ..schemas.booking import BookingInvoiceResponse, BookingQuote, BookingResponse
from .audit_service import record_audit
from .availability_service import AvailabilityService
from .notification_service import NotificationService
from .inventory_service import InventoryService

class BookingService:
    CONFLICT_MESSAGE = 'Một hoặc nhiều khung giờ vừa được người khác đặt. Danh sách giờ trống đã được cập nhật.'
    HOLD_DURATION = timedelta(minutes=15)
    REFUND_DEADLINE = timedelta(days=3)
    def __init__(self, repository: BookingRepository):
        self.repository = repository
        self.timezone = ZoneInfo(settings.TIMEZONE)
        self.availability_service = AvailabilityService(repository)
        self.notifications = NotificationService(repository.db)
        self.inventory = InventoryService(repository.db)

    def availability(self, *, booking_date: date, field_id: int | None, search: str | None, sport_type: str | None, location: str | None = None, start_time=None, max_price: float | None = None, sort_by: str = 'relevance'):
        return self.availability_service.list(
            booking_date=booking_date, field_id=field_id, search=search,
            sport_type=sport_type, location=location, start_time=start_time,
            max_price=max_price, sort_by=sort_by,
        )

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
        values = self._schedule_values(
            payload.field_id, payload.time_slot_ids, payload.booking_date,
            owner_user=current_user if owner_operator and not acting_as_customer else None,
        )
        slot_details = values.pop('_slot_details')
        field = self.repository.db.get(Field, payload.field_id)
        product_snapshots, service_amount = self.inventory.validate_selections(
            field, payload.product_items, lock=True,
        )
        self._apply_service_amount(values, service_amount)
        booking = Booking(
            booking_code=self._booking_code(), customer_id=customer.id,
            note=payload.note, status=BookingStatus.PENDING_PAYMENT.value,
            hold_expires_at=datetime.now(timezone.utc) + self.HOLD_DURATION, **values,
        )
        self._replace_booking_slots(booking, slot_details)
        booking.product_items = [BookingProductItem(
            product_id=item['product_id'], product_name_snapshot=item['name'],
            product_type_snapshot=item['product_type'], unit_snapshot=item['unit'],
            unit_price_snapshot=item['unit_price'], quantity=item['quantity'], line_total=item['subtotal'],
            source='CUSTOMER_BOOKING', added_by=current_user.id,
        ) for item in product_snapshots]
        try:
            created = self.repository.create(booking, commit=False)
            for item in created.product_items:
                self.inventory.reserve(item, actor_id=current_user.id)
            self._add_activity(created.id, current_user, 'booking_created', None, BookingStatus.PENDING_PAYMENT.value, {
                'booking_code': created.booking_code, 'hold_expires_at': created.hold_expires_at.isoformat() if created.hold_expires_at else None,
                'court_amount': float(created.court_amount), 'service_amount': float(created.service_amount),
            })
            self.repository.db.commit()
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail=self.CONFLICT_MESSAGE)
        except HTTPException:
            self.repository.db.rollback()
            raise
        except Exception:
            self.repository.db.rollback()
            raise
        return self.response(self.repository.get(created.id))

    def quote(self, *, field_id: int, time_slot_ids: list[int], booking_date: date, product_items=None) -> BookingQuote:
        values = self._schedule_values(field_id, time_slot_ids, booking_date)
        field = self.repository.lock_field(field_id)
        details = values['_slot_details']
        product_snapshots, service_amount = self.inventory.validate_selections(
            field, product_items or [], lock=False,
        )
        self._apply_service_amount(values, service_amount)
        total_amount = Decimal(values['total_amount'])
        deposit_amount = Decimal(values['deposit_amount'])
        remaining_after_deposit = max(total_amount - deposit_amount, Decimal('0')).quantize(Decimal('0.01'))
        return BookingQuote(
            venue_id=field.facility_id,
            venue_name=field.facility.name if field.facility else field.name,
            field_id=field_id, time_slot_id=details[0]['time_slot_id'], time_slot_ids=[item['time_slot_id'] for item in details], booking_date=booking_date,
            field_name=field.name, sport_type=field.sport_type,
            field_type=f'Sân {field.capacity}', location=field.location,
            time_slot_name='; '.join(item['name_snapshot'] for item in details), start_time=values['start_time_snapshot'],
            end_time=values['end_time_snapshot'], price=float(values['price_snapshot']),
            duration_minutes=sum((datetime.combine(date.min, item['end_time_snapshot']) - datetime.combine(date.min, item['start_time_snapshot'])).seconds // 60 for item in details),
            selected_slots=[{'time_slot_id': item['time_slot_id'], 'name': item['name_snapshot'], 'start_time': item['start_time_snapshot'], 'end_time': item['end_time_snapshot'], 'price': item['price_snapshot']} for item in details],
            court_amount=float(values['court_amount']), service_amount=float(values['service_amount']),
            product_items=product_snapshots,
            total_amount=float(total_amount), deposit_amount=float(deposit_amount),
            remaining_amount=float(remaining_after_deposit), deposit_type=values['deposit_type'],
            deposit_value=float(values['deposit_value']), hold_minutes=int(self.HOLD_DURATION.total_seconds() / 60),
            free_cancellation_minutes=values['free_cancellation_minutes'],
            cancellation_policy_summary=self._policy_summary(values['free_cancellation_minutes']),
        )

    def add_during_usage_product(self, booking_id: int, payload, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id, lock=True)
        self._require_owned_booking(booking, user)
        if booking.status not in (BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value):
            raise HTTPException(status_code=409, detail='Chỉ được thêm dịch vụ khi booking đã xác nhận hoặc đang diễn ra')
        snapshots, _ = self.inventory.validate_selections(booking.field, [payload], lock=True)
        snapshot = snapshots[0]
        item = BookingProductItem(
            booking=booking, product_id=snapshot['product_id'],
            product_name_snapshot=snapshot['name'], product_type_snapshot=snapshot['product_type'],
            unit_snapshot=snapshot['unit'], unit_price_snapshot=snapshot['unit_price'],
            quantity=snapshot['quantity'], line_total=snapshot['subtotal'],
            source='OWNER_DURING_USAGE', added_by=user.id,
        )
        try:
            self.repository.db.add(item); self.repository.db.flush()
            self.inventory.reserve(item, actor_id=user.id)
            before = self._amount_snapshot(booking)
            self._recalculate_product_amounts(booking)
            after = self._amount_snapshot(booking)
            self._add_activity(booking.id, user, 'owner_added_booking_product', booking.status, booking.status, {
                'item_id': item.id, 'product_id': item.product_id, 'product_name': item.product_name_snapshot,
                'quantity': item.quantity, 'unit_price': float(item.unit_price_snapshot),
                'subtotal': float(item.line_total), 'source': item.source,
                'amounts_before': before, 'amounts_after': after,
            })
            self.repository.db.commit()
        except HTTPException:
            self.repository.db.rollback(); raise
        except Exception:
            self.repository.db.rollback(); raise
        return self.response(self.repository.get(booking.id))

    def during_usage_product_options(self, booking_id: int, user: User):
        booking = self._booking_or_404(booking_id)
        self._require_owned_booking(booking, user)
        if booking.status not in (BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value):
            raise HTTPException(status_code=409, detail='Booking hiện không ở trạng thái có thể thêm dịch vụ')
        return self.inventory.owner_booking_options(booking, user)

    def update_during_usage_product(self, booking_id: int, item_id: int, payload, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id, lock=True)
        self._require_owned_booking(booking, user)
        if booking.status != BookingStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=409, detail='Chỉ được điều chỉnh phát sinh khi booking đang diễn ra')
        item = self._owner_added_item(booking, item_id)
        before = self._amount_snapshot(booking)
        old_quantity = int(item.quantity)
        try:
            self.inventory.release(item, actor_id=user.id)
            item.quantity = payload.quantity
            item.line_total = Decimal(item.unit_price_snapshot) * payload.quantity
            self.inventory.reserve(item, actor_id=user.id)
            self._recalculate_product_amounts(booking)
            after = self._amount_snapshot(booking)
            self._add_activity(booking.id, user, 'owner_updated_booking_product', booking.status, booking.status, {
                'item_id': item.id, 'product_id': item.product_id, 'product_name': item.product_name_snapshot,
                'quantity_before': old_quantity, 'quantity_after': item.quantity,
                'unit_price': float(item.unit_price_snapshot), 'subtotal_after': float(item.line_total),
                'amounts_before': before, 'amounts_after': after,
            })
            self.repository.db.commit()
        except HTTPException:
            self.repository.db.rollback(); raise
        except Exception:
            self.repository.db.rollback(); raise
        return self.response(self.repository.get(booking.id))

    def delete_during_usage_product(self, booking_id: int, item_id: int, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id, lock=True)
        self._require_owned_booking(booking, user)
        if booking.status != BookingStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=409, detail='Chỉ được xóa phát sinh khi booking đang diễn ra')
        item = self._owner_added_item(booking, item_id)
        before = self._amount_snapshot(booking)
        details = {
            'item_id': item.id, 'product_id': item.product_id, 'product_name': item.product_name_snapshot,
            'quantity': item.quantity, 'unit_price': float(item.unit_price_snapshot),
            'subtotal': float(item.line_total),
        }
        try:
            self.inventory.release(item, actor_id=user.id)
            booking.product_items.remove(item)
            self.repository.db.flush()
            self._recalculate_product_amounts(booking)
            details.update({'amounts_before': before, 'amounts_after': self._amount_snapshot(booking)})
            self._add_activity(booking.id, user, 'owner_deleted_booking_product', booking.status, booking.status, details)
            self.repository.db.commit()
        except HTTPException:
            self.repository.db.rollback(); raise
        except Exception:
            self.repository.db.rollback(); raise
        return self.response(self.repository.get(booking.id))

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
        invoice = booking.invoice
        detail = self.response(booking)
        return BookingInvoiceResponse.model_validate({
            'invoice_number': invoice.invoice_number, 'booking_id': invoice.booking_id,
            'booking_code': invoice.booking_code, 'customer_name': invoice.customer_name,
            'customer_email': invoice.customer_email, 'facility_name': invoice.facility_name,
            'field_name': invoice.field_name, 'booking_date': invoice.booking_date,
            'start_time': invoice.start_time, 'end_time': invoice.end_time,
            'duration_minutes': detail.duration_minutes, 'selected_slots': detail.selected_slots,
            'court_amount': invoice.court_amount, 'service_amount': invoice.service_amount,
            'product_items': detail.product_items,
            'total_amount': invoice.total_amount, 'deposit_amount': invoice.deposit_amount,
            'remaining_payment_amount': invoice.remaining_payment_amount,
            'refund_amount': invoice.refund_amount, 'net_received_amount': invoice.net_received_amount,
            'payment_methods': invoice.payment_methods, 'paid_at': invoice.paid_at,
            'issued_at': invoice.issued_at,
        })

    def update(self, booking_id: int, payload, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id)
        self._require_owned_booking(booking, user)
        if booking.status not in (BookingStatus.PENDING_PAYMENT.value, BookingStatus.PENDING_CONFIRMATION.value, BookingStatus.CONFIRMED.value):
            raise HTTPException(status_code=409, detail='Chỉ có thể đổi lịch đang chờ hoặc đã xác nhận')
        if self.repository.committed_payment_amount(booking.id) > 0:
            raise HTTPException(status_code=409, detail='Không thể đổi lịch sau khi đã phát sinh giao dịch thanh toán')
        values = self._schedule_values(
            payload.field_id, payload.time_slot_ids, payload.booking_date,
            exclude_id=booking.id, owner_user=user,
        )
        self._apply_service_amount(values, booking.service_amount or 0)
        slot_details = values.pop('_slot_details')
        if self.repository.committed_payment_amount(booking.id) > values['total_amount']:
            raise HTTPException(status_code=409, detail='Không thể đổi sang khung giờ có giá thấp hơn tổng giao dịch đã thanh toán hoặc đang chờ')
        values['note'] = payload.note
        self._replace_booking_slots(booking, slot_details)
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
            self.notifications.booking_event(booking, 'BOOKING_CANCELLED')
            self._release_product_inventory(booking, user.id)
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
        self.notifications.booking_event(booking, 'BOOKING_CANCELLED')
        self.notifications.notify_owner_for_booking(booking, 'CUSTOMER_CANCELLED_BOOKING')
        if refund > 0:
            self.notifications.booking_event(booking, 'PAYMENT_REFUNDED')
        self._release_product_inventory(booking, user.id)
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
        self.notifications.booking_event(
            booking, 'BOOKING_REJECTED' if action == 'owner_rejected_booking' else 'BOOKING_CANCELLED',
        )
        self._release_product_inventory(booking, user.id)
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
            payload.field_id, payload.time_slot_ids, payload.booking_date,
            exclude_id=booking.id, owner_user=user if user.role == 'OWNER' else None,
        )
        self._apply_service_amount(values, booking.service_amount or 0)
        if (booking.facility_id or booking.field_id) != (values['facility_id'] or values['field_id']):
            raise HTTPException(status_code=409, detail='Chỉ được đổi sang sân khác trong cùng cơ sở')
        target_field = self.repository.db.get(Field, payload.field_id)
        self.inventory.validate_reschedule(target_field, booking.product_items)
        old_total, new_total = Decimal(booking.total_amount), Decimal(values['total_amount'])
        difference = new_total - old_total
        paid = Decimal(booking.paid_amount or 0)
        additional = max(difference, Decimal(values['deposit_amount']) - paid, Decimal(0))
        return {
            'booking_id': booking.id, 'field_id': payload.field_id, 'time_slot_id': payload.time_slot_id,
            'time_slot_ids': payload.time_slot_ids,
            'booking_date': payload.booking_date, 'old_total_amount': float(old_total),
            'new_total_amount': float(new_total), 'price_difference': float(difference),
            'additional_payment_required': float(additional), 'credit_amount': float(max(-difference, Decimal(0))),
        }, values

    def reschedule(self, booking_id: int, payload, user: User) -> BookingResponse:
        quote, values = self.reschedule_quote(booking_id, payload, user)
        slot_details = values.pop('_slot_details')
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
        self._replace_booking_slots(booking, slot_details)
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
        self.notifications.booking_event(booking, 'BOOKING_RESCHEDULED')
        if user.id == booking.customer_id:
            self.notifications.notify_owner_for_booking(booking, 'CUSTOMER_RESCHEDULED_BOOKING')
        try:
            self.repository.flush_update(booking, values)
            self.repository.db.commit()
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail=self.CONFLICT_MESSAGE)
        return self.response(self.repository.get(booking.id))

    def start(self, booking_id: int, note: str | None, confirm_early: bool, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id)
        self._require_owned_booking(booking, user)
        if booking.status != BookingStatus.CONFIRMED.value:
            raise HTTPException(status_code=409, detail='Chỉ booking đã xác nhận mới có thể bắt đầu')
        
        now = datetime.now(self.timezone)
        # Verify slot bounds logic for early start. Find the specific slot we are trying to start early.
        # Actually, if we just rely on first slot scheduled_at
        scheduled_at = self._scheduled_at(booking)
        is_early = scheduled_at > now
        
        if is_early:
            if not confirm_early:
                raise HTTPException(status_code=400, detail='Chưa đến giờ sử dụng sân. Vui lòng xác nhận để bắt đầu sớm.')
            
            # Check for conflict with IN_PROGRESS bookings at the current time
            from sqlalchemy import select, and_, or_
            from ...models.field import BookingSlot, Booking
            from ...models.operations import FieldBlock
            
            current_time = now.time()
            current_date = now.date()
            
            conflict_booking = self.repository.db.scalar(
                select(Booking.id)
                .outerjoin(BookingSlot, BookingSlot.booking_id == Booking.id)
                .where(
                    Booking.field_id == booking.field_id,
                    Booking.booking_date == current_date,
                    Booking.status == BookingStatus.IN_PROGRESS.value,
                    Booking.id != booking.id,
                    or_(
                        and_(BookingSlot.start_time_snapshot <= current_time, BookingSlot.end_time_snapshot >= current_time),
                        and_(~Booking.booking_slots.any(), Booking.start_time_snapshot <= current_time, Booking.end_time_snapshot >= current_time)
                    )
                )
            )
            if conflict_booking:
                raise HTTPException(status_code=409, detail='Sân đang có khách sử dụng. Không thể bắt đầu sớm.')
                
            conflict_block = self.repository.db.scalar(
                select(FieldBlock.id).where(
                    FieldBlock.field_id == booking.field_id,
                    FieldBlock.block_date == current_date,
                    FieldBlock.start_time <= current_time,
                    FieldBlock.end_time >= current_time
                )
            )
            if conflict_block:
                raise HTTPException(status_code=409, detail='Sân đang được bảo trì/khóa. Không thể bắt đầu sớm.')

        res = self._transition(booking_id, {BookingStatus.CONFIRMED.value}, BookingStatus.IN_PROGRESS.value, note, user)
        if is_early:
            self._add_activity(booking_id, user, 'booking_started_early', BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value, {
                'actual_started_at': now.isoformat(),
                'started_early': True,
                'started_by_owner_id': user.id
            })
            self.repository.db.commit()
        return res

    def no_show(self, booking_id: int, note: str | None, user: User) -> BookingResponse:
        booking = self._booking_or_404(booking_id)
        self._require_owned_booking(booking, user)
        if booking.status != BookingStatus.CONFIRMED.value:
            raise HTTPException(status_code=409, detail='Chỉ booking đã xác nhận mới có thể đánh dấu no-show')
        grace_period = timedelta(minutes=15)
        if self._scheduled_at(booking) + grace_period > datetime.now(self.timezone):
            raise HTTPException(status_code=409, detail='Chưa đến giờ no-show hợp lệ (sau giờ bắt đầu 15 phút)')
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
        self._complete_product_inventory(booking, user.id)
        self.repository.db.commit()
        booking = self.repository.get(booking.id)
        self._ensure_invoice(booking, user)
        return self.response(self.repository.get(booking.id))

    def _schedule_values(self, field_id: int, time_slot_ids: list[int], booking_date: date, exclude_id: int | None = None, owner_user: User | None = None):
        self.repository.release_expired_holds()
        self.repository.begin_booking_write_lock()
        field = self.repository.lock_field(field_id)
        if field is None or field.status != 'available' or (field.facility is not None and (not field.facility.is_active or field.facility.status != 'APPROVED')):
            raise HTTPException(status_code=409, detail='Sân không tồn tại hoặc đang ngừng hoạt động')
        if owner_user is not None and not owns_field(owner_user, field, self.repository.db):
            raise HTTPException(status_code=404, detail='Không tìm thấy sân')
        slots = [self.repository.db.get(TimeSlot, slot_id) for slot_id in time_slot_ids]
        if any(slot is None or slot.field_id != field_id or not slot.is_active for slot in slots):
            raise HTTPException(status_code=409, detail='Khung giờ không tồn tại, đã khóa hoặc không thuộc sân đã chọn')
        slots.sort(key=lambda item: (item.start_time, item.end_time, item.id))
        start_time, end_time = slots[0].start_time, slots[-1].end_time
        scheduled_at = datetime.combine(booking_date, start_time, tzinfo=self.timezone)
        if scheduled_at <= datetime.now(self.timezone):
            raise HTTPException(status_code=409, detail='Không thể đặt thời gian trong quá khứ')
        conflict = self.repository.find_conflict(
            field_id=field_id, booking_date=booking_date,
            ranges=[(slot.start_time, slot.end_time) for slot in slots], exclude_id=exclude_id,
        )
        if conflict:
            raise HTTPException(status_code=409, detail=self.CONFLICT_MESSAGE)
        if any(self.repository.find_block(field_id=field_id, booking_date=booking_date, start_time=slot.start_time, end_time=slot.end_time) for slot in slots):
            raise HTTPException(status_code=409, detail='Sân đã bị khóa hoặc bảo trì trong khoảng thời gian này')
        if any(self.repository.find_maintenance(field_id=field_id, booking_date=booking_date, start_time=slot.start_time, end_time=slot.end_time) for slot in slots):
            raise HTTPException(status_code=409, detail='Khung giờ đang bảo trì và không khả dụng')
        prices = []
        slot_details = []
        for position, slot in enumerate(slots):
            special_price = slot.weekend_price if booking_date.weekday() >= 5 else slot.weekday_price
            price = Decimal(special_price if special_price is not None else slot.price)
            prices.append(price)
            slot_details.append({
                'time_slot_id': slot.id, 'position': position, 'name_snapshot': slot.name,
                'start_time_snapshot': slot.start_time, 'end_time_snapshot': slot.end_time,
                'price_snapshot': price,
            })
        total = sum(prices, Decimal('0'))
        deposit_value = Decimal(field.deposit_value or 0)
        deposit = total * deposit_value / Decimal(100) if field.deposit_type == 'percentage' else deposit_value
        deposit = min(total, deposit).quantize(Decimal('0.01'))
        return {
            'facility_id': field.facility_id,
            'facility_name_snapshot': field.facility.name if field.facility else field.name,
            'field_id': field_id, 'time_slot_id': slots[0].id, 'booking_date': booking_date,
            'start_time_snapshot': start_time, 'end_time_snapshot': end_time,
            'price_snapshot': prices[0], 'court_amount': total, 'service_amount': Decimal('0'), 'total_amount': total,
            'deposit_type': field.deposit_type, 'deposit_value': deposit_value,
            'deposit_amount': deposit, 'paid_amount': Decimal('0'),
            'remaining_amount': total, 'payment_status': 'unpaid',
            'cancellation_policy': field.cancellation_policy,
            'cancellation_refund_percent': field.cancellation_refund_percent,
            'free_cancellation_minutes': int(field.facility.free_cancellation_minutes if field.facility else 360),
            '_slot_details': slot_details,
        }

    @staticmethod
    def _apply_service_amount(values: dict, service_amount):
        court_amount = Decimal(values.get('court_amount', values['total_amount']))
        service_amount = Decimal(service_amount or 0)
        total = court_amount + service_amount
        # The deposit policy belongs to the court schedule. Add-ons are paid in
        # the remaining payment and must never increase the initial deposit.
        deposit = min(court_amount, Decimal(values['deposit_amount'] or 0)).quantize(Decimal('0.01'))
        values.update({
            'court_amount': court_amount, 'service_amount': service_amount, 'total_amount': total,
            'deposit_amount': deposit, 'remaining_amount': total,
        })

    def _replace_booking_slots(self, booking: Booking, slot_details: list[dict]):
        # Delete old snapshots before inserting positions 0..n again. Without
        # this flush, databases can insert the new rows before deleting the old
        # ones and violate uq_booking_slot_position during reschedule.
        booking.booking_slots.clear()
        self.repository.db.flush()
        booking.booking_slots.extend(BookingSlot(**item) for item in slot_details)

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
            self._release_product_inventory(booking, user.id)
        self._add_activity(booking.id, user, f'booking_{status}', old_status, status, details)
        if status == BookingStatus.CONFIRMED.value:
            self.notifications.booking_event(booking, 'BOOKING_CONFIRMED')
        self.repository.db.commit()
        return self.response(self.repository.get(booking.id))

    def _release_product_inventory(self, booking: Booking, actor_id: int | None):
        for item in booking.product_items:
            self.inventory.release(item, actor_id=actor_id)

    @staticmethod
    def _owner_added_item(booking: Booking, item_id: int):
        item = next((value for value in booking.product_items if value.id == item_id), None)
        if item is None or item.source != 'OWNER_DURING_USAGE':
            raise HTTPException(status_code=404, detail='Không tìm thấy khoản phát sinh của booking')
        return item

    @staticmethod
    def _amount_snapshot(booking: Booking):
        return {
            'court_amount': float(booking.court_amount or 0),
            'service_amount': float(booking.service_amount or 0),
            'total_amount': float(booking.total_amount or 0),
            'paid_amount': float(booking.paid_amount or 0),
            'remaining_amount': float(booking.remaining_amount or 0),
        }

    @staticmethod
    def _recalculate_product_amounts(booking: Booking):
        court = Decimal(booking.court_amount or 0)
        if court == 0 and Decimal(booking.service_amount or 0) == 0:
            court = Decimal(booking.total_amount or 0)
        service = sum((Decimal(item.line_total or 0) for item in booking.product_items), Decimal('0'))
        total = court + service
        paid = Decimal(booking.paid_amount or 0)
        booking.court_amount = court
        booking.service_amount = service
        booking.total_amount = total
        booking.remaining_amount = max(total - paid, Decimal('0'))
        booking.credit_amount = max(paid - total, Decimal('0'))
        booking.payment_status = 'paid' if paid >= total else 'partial' if paid > 0 else 'unpaid'

    def _complete_product_inventory(self, booking: Booking, actor_id: int | None):
        for item in booking.product_items:
            if item.product_type_snapshot == 'RENT':
                self.inventory.release(item, actor_id=actor_id, returned=True)
            else:
                self.inventory.fulfill(item, actor_id=actor_id)

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
            court_amount=booking.court_amount, service_amount=booking.service_amount,
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
        slot_snapshots = booking.booking_slots or []
        selected_slots = [{
            'time_slot_id': item.time_slot_id, 'name': item.name_snapshot,
            'start_time': item.start_time_snapshot, 'end_time': item.end_time_snapshot,
            'price': item.price_snapshot,
        } for item in slot_snapshots] or [{
            'time_slot_id': booking.time_slot_id, 'name': booking.time_slot.name,
            'start_time': booking.start_time_snapshot, 'end_time': booking.end_time_snapshot,
            'price': booking.price_snapshot,
        }]
        duration = sum(
            (datetime.combine(date.min, item['end_time']) - datetime.combine(date.min, item['start_time'])).seconds // 60
            for item in selected_slots
        )
        product_items = [{
            'item_id': item.id, 'product_id': item.product_id, 'name': item.product_name_snapshot,
            'product_type': item.product_type_snapshot, 'unit': item.unit_snapshot,
            'quantity': item.quantity, 'unit_price': item.unit_price_snapshot,
            'subtotal': item.line_total, 'inventory_status': item.inventory_status,
            'source': item.source, 'added_by': item.added_by,
            'added_by_name': item.added_by_user.full_name if item.added_by_user else None,
            'added_at': item.created_at,
        } for item in booking.product_items]
        return BookingResponse.model_validate({
            'id': booking.id, 'booking_code': booking.booking_code,
            'customer_id': booking.customer_id, 'customer_name': booking.customer.full_name,
            'customer_email': booking.customer.email, 'customer_phone': booking.customer.phone,
            'facility_id': booking.facility_id,
            'facility_name': booking.facility_name_snapshot or (booking.facility.name if booking.facility else booking.field.name),
            'facility_hotline': booking.facility.contact_phone if booking.facility else None,
            'field_id': booking.field_id,
            'field_name': booking.field.name, 'sport_type': booking.field.sport_type,
            'field_capacity': booking.field.capacity,
            'location': booking.field.location, 'time_slot_id': booking.time_slot_id,
            'time_slot_ids': [item['time_slot_id'] for item in selected_slots],
            'selected_slots': selected_slots,
            'time_slot_name': '; '.join(item['name'] for item in selected_slots), 'booking_date': booking.booking_date,
            'start_time_snapshot': booking.start_time_snapshot,
            'end_time_snapshot': booking.end_time_snapshot,
            'price_snapshot': booking.price_snapshot,
            'court_amount': booking.court_amount, 'service_amount': booking.service_amount,
            'product_items': product_items, 'total_amount': total,
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
