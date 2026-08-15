import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select, update

from ..models.field import Booking
from ..models.notification import Notification
from ..models.user import User, UserRole
from ..core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Single write/read boundary for user-scoped notifications."""

    def __init__(self, db, message_renderer=None):
        self.db = db
        self.message_renderer = message_renderer

    def create(self, *, user_id: int, type: str, title: str, message: str,
               reference_type: str | None = None, reference_id: int | None = None):
        item = Notification(
            user_id=user_id, type=type, title=title, message=message,
            reference_type=reference_type, reference_id=reference_id,
        )
        self.db.add(item)
        return item

    def booking_event(self, booking: Booking, event: str, *, recipient_id: int | None = None):
        recipient_id = recipient_id or booking.customer_id
        title, fallback = self._booking_template(booking, event)
        message = fallback
        if self.message_renderer is not None:
            try:
                rendered = self.message_renderer(booking=booking, event=event, fallback=fallback)
                if isinstance(rendered, str) and rendered.strip():
                    message = rendered.strip()
            except Exception as exc:  # Notification delivery must never depend on AI.
                logger.warning('Notification AI fallback event=%s error=%s', event, type(exc).__name__)
        return self.create(
            user_id=recipient_id, type=event, title=title, message=message,
            reference_type='booking', reference_id=booking.id,
        )

    def notify_owner_for_booking(self, booking: Booking, event: str):
        owner_id = booking.field.owner_id
        if owner_id and owner_id != booking.customer_id:
            return self.booking_event(booking, event, recipient_id=owner_id)
        return None

    def partner_result(self, user_id: int, application_id: int, approved: bool, reason: str | None = None):
        if approved:
            title = 'Hồ sơ đối tác đã được phê duyệt'
            message = 'Hồ sơ Trở thành chủ sân của bạn đã được phê duyệt. Bạn có thể bắt đầu quản lý cơ sở.'
            event = 'PARTNER_APPLICATION_APPROVED'
        else:
            title = 'Hồ sơ đối tác chưa được phê duyệt'
            suffix = f' Lý do: {reason.strip()}.' if reason and reason.strip() else ''
            message = f'Hồ sơ Trở thành chủ sân của bạn đã bị từ chối.{suffix}'
            event = 'PARTNER_APPLICATION_REJECTED'
        return self.create(
            user_id=user_id, type=event, title=title, message=message,
            reference_type='partner_application', reference_id=application_id,
        )

    def partner_submitted(self, application_id: int, customer_name: str):
        admins = self.db.scalars(select(User).where(
            User.role == UserRole.SYSTEM_ADMIN.value, User.is_active.is_(True),
        )).all()
        for admin in admins:
            self.create(
                user_id=admin.id, type='PARTNER_APPLICATION_SUBMITTED',
                title='Có hồ sơ đối tác mới cần duyệt',
                message=f'{customer_name} vừa gửi hồ sơ đăng ký trở thành chủ sân.',
                reference_type='partner_application', reference_id=application_id,
            )

    def facility_submitted(self, facility_id: int, facility_name: str, owner_name: str):
        admins = self.db.scalars(select(User).where(
            User.role == UserRole.SYSTEM_ADMIN.value, User.is_active.is_(True),
        )).all()
        for admin in admins:
            self.create(
                user_id=admin.id, type='FACILITY_APPLICATION_SUBMITTED',
                title='Có hồ sơ cơ sở mới cần xét duyệt',
                message=f'{owner_name} vừa gửi hồ sơ cơ sở {facility_name}.',
                reference_type='facility', reference_id=facility_id,
            )

    def facility_result(self, owner_id: int, facility_id: int, facility_name: str, approved: bool, reason: str | None = None):
        if approved:
            title = 'Cơ sở đã được phê duyệt'
            message = 'Cơ sở đã được phê duyệt.'
            event = 'FACILITY_APPROVED'
        else:
            clean_reason = (reason or '').strip()
            title = 'Cơ sở bị từ chối'
            message = f'Cơ sở bị từ chối: {clean_reason}.'
            event = 'FACILITY_REJECTED'
        return self.create(
            user_id=owner_id, type=event, title=title,
            message=f'{facility_name}: {message}',
            reference_type='facility', reference_id=facility_id,
        )

    def list_for_user(self, user_id: int, *, page: int, page_size: int):
        base = Notification.user_id == user_id
        total = int(self.db.scalar(select(func.count(Notification.id)).where(base)) or 0)
        unread = int(self.db.scalar(select(func.count(Notification.id)).where(
            base, Notification.is_read.is_(False),
        )) or 0)
        items = self.db.scalars(select(Notification).where(base).order_by(
            Notification.created_at.desc(), Notification.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size)).all()
        return {'items': items, 'total': total, 'unread_count': unread, 'page': page, 'page_size': page_size}

    def unread_count(self, user_id: int) -> int:
        return int(self.db.scalar(select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.is_read.is_(False),
        )) or 0)

    def create_due_reminders(self, user_id: int) -> int:
        now = datetime.now(ZoneInfo(settings.TIMEZONE))
        tomorrow = (now + timedelta(hours=24)).date()
        bookings = self.db.scalars(select(Booking).where(
            Booking.customer_id == user_id,
            Booking.status == 'confirmed',
            Booking.booking_date.between(now.date(), tomorrow),
        )).all()
        created = 0
        for booking in bookings:
            scheduled = datetime.combine(
                booking.booking_date, booking.start_time_snapshot, tzinfo=now.tzinfo,
            )
            if not now < scheduled <= now + timedelta(hours=24):
                continue
            exists = self.db.scalar(select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.type == 'BOOKING_REMINDER',
                Notification.reference_type == 'booking',
                Notification.reference_id == booking.id,
            ))
            if exists is None:
                self.booking_event(booking, 'BOOKING_REMINDER')
                created += 1
        if created:
            self.db.commit()
        return created

    def mark_read(self, notification_id: int, user_id: int):
        item = self.db.scalar(select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id,
        ))
        if item is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy thông báo')
        if not item.is_read:
            item.is_read = True
            item.read_at = datetime.now(timezone.utc)
            self.db.commit(); self.db.refresh(item)
        return item

    def mark_all_read(self, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        result = self.db.execute(update(Notification).where(
            Notification.user_id == user_id, Notification.is_read.is_(False),
        ).values(is_read=True, read_at=now))
        self.db.commit()
        return int(result.rowcount or 0)

    @staticmethod
    def _booking_template(booking: Booking, event: str):
        code = booking.booking_code
        field = booking.field.name
        venue = booking.facility_name_snapshot or (booking.facility.name if booking.facility else field)
        slots = booking.booking_slots or []
        schedule_times = ', '.join(
            f'{item.start_time_snapshot:%H:%M}–{item.end_time_snapshot:%H:%M}' for item in slots
        ) or f'{booking.start_time_snapshot:%H:%M}–{booking.end_time_snapshot:%H:%M}'
        schedule = f'{schedule_times} ngày {booking.booking_date:%d/%m/%Y}'
        amount = lambda value: f'{float(value or 0):,.0f}đ'.replace(',', '.')
        templates = {
            'DEPOSIT_PAID': ('Đặt cọc thành công', f'Đã ghi nhận tiền cọc {amount(booking.deposit_amount)} cho booking {code}.'),
            'WAITING_OWNER_CONFIRM': ('Booking đang chờ chủ sân xác nhận', f'Booking {code} tại {venue}, {field}, {schedule} đang chờ chủ sân xác nhận.'),
            'BOOKING_CONFIRMED': ('Đặt sân đã được xác nhận', f'Booking {code} tại {venue}, {field}, {schedule} đã được chủ sân xác nhận.'),
            'BOOKING_REJECTED': ('Chủ sân đã từ chối booking', f'Booking {code} tại {venue}, {field} đã bị chủ sân từ chối. Vui lòng theo dõi trạng thái hoàn tiền.'),
            'BOOKING_RESCHEDULED': ('Lịch đặt sân đã được đổi', f'Booking {code} đã được đổi sang {field}, {schedule}.'),
            'BOOKING_CANCELLED': ('Lịch đặt sân đã bị hủy', f'Booking {code} tại {venue}, {field} đã bị hủy.'),
            'PAYMENT_COMPLETED': ('Thanh toán đã hoàn tất', f'Đã ghi nhận thanh toán đầy đủ {amount(booking.total_amount)} cho booking {code}.'),
            'PAYMENT_UPDATED': ('Thanh toán booking được cập nhật', f'Thanh toán của booking {code} vừa được cập nhật.'),
            'PAYMENT_REFUNDED': ('Hoàn tiền thành công', f'Đã hoàn {amount(booking.refund_amount)} cho booking {code}.'),
            'BOOKING_REMINDER': ('Sắp đến giờ chơi', f'Nhắc lịch booking {code} tại {venue}, {field}, {schedule}.'),
            'OWNER_NEW_BOOKING': ('Có booking mới chờ xác nhận', f'Booking {code} cho {field}, {schedule} đã đặt cọc và đang chờ bạn xác nhận.'),
            'CUSTOMER_CANCELLED_BOOKING': ('Khách hàng đã hủy booking', f'Khách hàng đã hủy booking {code} cho {field}, {schedule}.'),
            'CUSTOMER_RESCHEDULED_BOOKING': ('Khách hàng đã đổi lịch', f'Booking {code} vừa được khách đổi sang {field}, {schedule}. Vui lòng kiểm tra lịch mới.'),
        }
        return templates[event]
