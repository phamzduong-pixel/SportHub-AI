from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from ..core.datetime_utils import as_utc
from ..core.ownership import management_owner_id, owns_field
from ..models.field import Booking, Field
from ..models.payment import EscrowStatus, Payment, PaymentStatus
from ..models.refund import BookingActivity, RefundRequest, RefundStatus
from ..models.user import User
from .audit_service import record_audit
from .notification_service import NotificationService


class RefundService:
    def __init__(self, db: Session):
        self.db = db
        self.notifications = NotificationService(db)

    def list_my(self, user: User, *, status: str | None, page: int, page_size: int):
        return self._list(customer_id=user.id, owner_id=None, status=status, page=page, page_size=page_size)

    def list_manage(self, user: User, *, status: str | None, page: int, page_size: int):
        owner_id = management_owner_id(user, self.db)
        if owner_id is None:
            raise HTTPException(status_code=403, detail='Tài khoản quản lý chưa được gán cho OWNER')
        return self._list(customer_id=None, owner_id=owner_id, status=status, page=page, page_size=page_size)

    def get_for_user(self, refund_id: int, user: User):
        item = self._get(refund_id)
        self._authorize(item.booking, user)
        self._refresh_overdue(item)
        return self.response(self._get(refund_id))

    def mark_refunded(self, refund_id: int, payload, user: User):
        item = self._get(refund_id, lock=True)
        self._require_owner(item.booking, user)
        reference = payload.transaction_reference.strip()
        if item.status == RefundStatus.REFUNDED.value:
            if item.transaction_reference == reference:
                return self.response(item)
            raise HTTPException(status_code=409, detail='Yêu cầu này đã được hoàn tiền bằng giao dịch khác')
        if item.status == RefundStatus.DISPUTED.value:
            raise HTTPException(status_code=409, detail='Khiếu nại đang được xử lý; không được tự động hoàn thêm lần nữa')
        if item.status not in (RefundStatus.REFUND_PENDING.value, RefundStatus.REFUND_OVERDUE.value):
            raise HTTPException(status_code=409, detail='Trạng thái yêu cầu hoàn tiền không hợp lệ')
        duplicate = self.db.scalar(select(RefundRequest.id).where(
            RefundRequest.transaction_reference == reference, RefundRequest.id != item.id,
        ))
        if duplicate:
            raise HTTPException(status_code=409, detail='Mã giao dịch hoàn tiền đã được sử dụng')
        now = datetime.now(timezone.utc)
        old_status = item.status
        claimed = self.db.execute(update(RefundRequest).where(
            RefundRequest.id == item.id,
            RefundRequest.status.in_((RefundStatus.REFUND_PENDING.value, RefundStatus.REFUND_OVERDUE.value)),
        ).values(
            status=RefundStatus.REFUNDED.value, processed_by=user.id, refunded_at=now,
            transaction_reference=reference, evidence_url=payload.evidence_url,
        ).execution_options(synchronize_session=False))
        if claimed.rowcount != 1:
            self.db.rollback()
            current = self._get(refund_id)
            if current.status == RefundStatus.REFUNDED.value and current.transaction_reference == reference:
                return self.response(current)
            raise HTTPException(status_code=409, detail='Yêu cầu hoàn tiền vừa được một người khác xử lý')
        refund_payment = item.refund_payment
        refund_payment.status = PaymentStatus.REFUNDED.value
        refund_payment.escrow_status = EscrowStatus.REFUNDED.value
        refund_payment.payment_status = PaymentStatus.REFUNDED.value
        refund_payment.refund_status = RefundStatus.REFUNDED.value
        refund_payment.refunded_at = now
        refund_payment.confirmed_by = user.id
        refund_payment.provider_reference = reference
        refund_payment.verification_source = 'owner_confirmation'
        if payload.note:
            refund_payment.note = payload.note
        item.booking.refund_status = RefundStatus.REFUNDED.value
        item.booking.payment_status = PaymentStatus.REFUNDED.value
        item.booking.remaining_amount = Decimal(0)
        self.db.execute(update(Payment).where(
            Payment.booking_id == item.booking_id,
            Payment.payment_type != 'refund', Payment.status == PaymentStatus.PAID.value,
        ).values(refund_status=RefundStatus.REFUNDED.value, payment_status=PaymentStatus.REFUNDED.value, escrow_status=EscrowStatus.REFUNDED.value))
        self._activity(item.booking_id, user, 'refund_marked_paid', old_status, RefundStatus.REFUNDED.value, {
            'refund_id': item.id, 'amount': float(item.amount), 'transaction_reference': reference,
            'evidence_url': payload.evidence_url,
        })
        self.notifications.booking_event(item.booking, 'PAYMENT_REFUNDED')
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(status_code=409, detail='Yêu cầu hoàn tiền vừa được xử lý hoặc mã giao dịch đã tồn tại')
        return self.response(self._get(item.id))

    def confirm_received(self, refund_id: int, user: User):
        item = self._get(refund_id, lock=True)
        if item.booking.customer_id != user.id:
            raise HTTPException(status_code=403, detail='Chỉ khách đặt sân được xác nhận đã nhận tiền')
        if item.status != RefundStatus.REFUNDED.value:
            raise HTTPException(status_code=409, detail='Chủ sân chưa xác nhận đã hoàn tiền')
        if item.customer_confirmed_at:
            return self.response(item)
        now = datetime.now(timezone.utc)
        item.customer_confirmed_at = now
        item.customer_action_by = user.id
        self._activity(item.booking_id, user, 'customer_confirmed_refund', item.status, item.status, {
            'refund_id': item.id, 'amount': float(item.amount),
        })
        self.db.commit()
        return self.response(self._get(item.id))

    def dispute(self, refund_id: int, reason: str, user: User):
        item = self._get(refund_id, lock=True)
        if item.booking.customer_id != user.id:
            raise HTTPException(status_code=403, detail='Chỉ khách đặt sân được gửi khiếu nại')
        if item.customer_confirmed_at:
            raise HTTPException(status_code=409, detail='Khách đã xác nhận nhận tiền; không thể mở khiếu nại tự động')
        if item.status == RefundStatus.DISPUTED.value:
            return self.response(item)
        if item.status not in (
            RefundStatus.REFUND_PENDING.value, RefundStatus.REFUND_OVERDUE.value, RefundStatus.REFUNDED.value,
        ):
            raise HTTPException(status_code=409, detail='Trạng thái hiện tại không thể gửi khiếu nại')
        old_status = item.status
        item.status = RefundStatus.DISPUTED.value
        item.dispute_reason = reason.strip()
        item.disputed_at = datetime.now(timezone.utc)
        item.customer_action_by = user.id
        item.booking.refund_status = RefundStatus.DISPUTED.value
        self.db.execute(update(Payment).where(Payment.booking_id == item.booking_id).values(refund_status=RefundStatus.DISPUTED.value))
        self._activity(item.booking_id, user, 'refund_disputed', old_status, item.status, {
            'refund_id': item.id, 'reason': reason.strip(),
        })
        self.db.commit()
        return self.response(self._get(item.id))

    def reputation(self, user: User):
        owner_id = management_owner_id(user, self.db)
        if owner_id is None:
            raise HTTPException(status_code=403, detail='Tài khoản quản lý chưa được gán cho OWNER')
        booking_filter = Booking.field.has(or_(Field.owner_id == owner_id, Field.owner_id.is_(None)))
        total = self.db.scalar(select(func.count(Booking.id)).where(booking_filter)) or 0
        cancelled = self.db.scalar(select(func.count(Booking.id)).where(
            booking_filter, Booking.status == 'cancelled_by_owner',
        )) or 0
        refunds = list(self.db.scalars(select(RefundRequest).join(Booking).where(
            booking_filter, RefundRequest.refunded_at.is_not(None),
        )).all())
        on_time = sum(1 for item in refunds if self._aware(item.refunded_at) <= self._aware(item.due_at))
        return {
            'total_bookings': total, 'owner_cancelled_bookings': cancelled,
            'owner_cancellation_rate': round(cancelled * 100 / total, 2) if total else 0,
            'completed_refunds': len(refunds), 'on_time_refunds': on_time,
            'on_time_refund_rate': round(on_time * 100 / len(refunds), 2) if refunds else 100,
        }

    def _list(self, *, customer_id, owner_id, status, page, page_size):
        self._mark_all_overdue()
        filters = []
        if customer_id:
            filters.append(Booking.customer_id == customer_id)
        if owner_id is not None:
            filters.append(Booking.field.has(or_(Field.owner_id == owner_id, Field.owner_id.is_(None))))
        if status:
            filters.append(RefundRequest.status == status)
        total = self.db.scalar(select(func.count(RefundRequest.id)).join(Booking).where(*filters)) or 0
        items = list(self.db.scalars(self._query().join(Booking).where(*filters)
            .order_by(RefundRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all())
        return [self.response(item) for item in items], total

    def _get(self, refund_id: int, lock: bool = False):
        query = self._query().where(RefundRequest.id == refund_id)
        if lock:
            query = query.with_for_update()
        item = self.db.scalar(query)
        if item is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy yêu cầu hoàn tiền')
        return item

    @staticmethod
    def _query():
        booking_load = joinedload(RefundRequest.booking)
        return select(RefundRequest).options(
            booking_load.joinedload(Booking.customer),
            booking_load.joinedload(Booking.field),
            booking_load.selectinload(Booking.activities).joinedload(BookingActivity.actor),
            joinedload(RefundRequest.refund_payment), joinedload(RefundRequest.requester),
            joinedload(RefundRequest.processor),
        )

    def _refresh_overdue(self, item):
        if item.status == RefundStatus.REFUND_PENDING.value and self._aware(item.due_at) < datetime.now(timezone.utc):
            item.status = RefundStatus.REFUND_OVERDUE.value
            item.booking.refund_status = RefundStatus.REFUND_OVERDUE.value
            self.db.execute(update(Payment).where(Payment.booking_id == item.booking_id).values(refund_status=RefundStatus.REFUND_OVERDUE.value))
            self.db.commit()

    def _mark_all_overdue(self):
        now = datetime.now(timezone.utc)
        ids = list(self.db.scalars(select(RefundRequest.booking_id).where(
            RefundRequest.status == RefundStatus.REFUND_PENDING.value, RefundRequest.due_at < now,
        )).all())
        if not ids:
            return
        self.db.execute(update(RefundRequest).where(RefundRequest.booking_id.in_(ids)).values(status=RefundStatus.REFUND_OVERDUE.value))
        self.db.execute(update(Booking).where(Booking.id.in_(ids)).values(refund_status=RefundStatus.REFUND_OVERDUE.value))
        self.db.execute(update(Payment).where(Payment.booking_id.in_(ids)).values(refund_status=RefundStatus.REFUND_OVERDUE.value))
        self.db.commit()

    def _authorize(self, booking, user):
        if booking.customer_id != user.id and (not self._can_manage(user) or not owns_field(user, booking.field, self.db)):
            raise HTTPException(status_code=403, detail='Bạn không được xem yêu cầu hoàn tiền này')

    def _require_owner(self, booking, user):
        if not self._can_manage(user) or not owns_field(user, booking.field, self.db):
            raise HTTPException(status_code=403, detail='Bạn không được xử lý yêu cầu hoàn tiền này')

    def _activity(self, booking_id, user, action, from_status, to_status, details):
        self.db.add(BookingActivity(
            booking_id=booking_id, actor_id=user.id, actor_role=user.role, action=action,
            from_status=from_status, to_status=to_status, details=details,
        ))
        record_audit(self.db, user, 'refund', details.get('refund_id'), action, {'booking_id': booking_id, 'from_status': from_status, 'to_status': to_status, **details})

    @staticmethod
    def _can_manage(user):
        return user.role == 'OWNER'

    @staticmethod
    def _aware(value):
        return value.replace(tzinfo=value.tzinfo or timezone.utc)

    def response(self, item):
        booking = item.booking
        return {
            'id': item.id, 'booking_id': item.booking_id, 'booking_code': booking.booking_code,
            'customer_id': booking.customer_id, 'customer_name': booking.customer.full_name,
            'field_name': booking.field.name, 'amount': float(item.amount), 'status': item.status,
            'reason': item.reason, 'requested_by': item.requested_by,
            'requested_by_name': item.requester.full_name, 'processed_by': item.processed_by,
            'processed_by_name': item.processor.full_name if item.processor else None,
            'requested_at': as_utc(item.requested_at), 'due_at': as_utc(item.due_at),
            'refunded_at': as_utc(item.refunded_at), 'customer_confirmed_at': as_utc(item.customer_confirmed_at),
            'disputed_at': as_utc(item.disputed_at), 'transaction_reference': item.transaction_reference,
            'evidence_url': item.evidence_url, 'dispute_reason': item.dispute_reason,
            'is_overdue': item.status == RefundStatus.REFUND_OVERDUE.value,
            'activities': [{
                'id': activity.id, 'actor_id': activity.actor_id,
                'actor_name': activity.actor.full_name if activity.actor else None,
                'actor_role': activity.actor_role, 'action': activity.action,
                'from_status': activity.from_status, 'to_status': activity.to_status,
                'details': activity.details or {}, 'created_at': as_utc(activity.created_at),
            } for activity in booking.activities],
            'created_at': as_utc(item.created_at), 'updated_at': as_utc(item.updated_at),
        }
