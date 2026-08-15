import re

from fastapi import HTTPException

from ..repositories.booking_repository import BookingRepository
from ..schemas.ai import BookingMessageEvent
from .ai_provider import AIProviderError, OpenAIProvider
from .booking_service import BookingService


class BookingMessageService:
    """Builds immutable booking facts in the backend; AI may only add safe prose."""

    LEGACY_EVENTS = {
        BookingMessageEvent.DEPOSIT_SUCCEEDED: BookingMessageEvent.DEPOSIT_PAID,
        BookingMessageEvent.OWNER_CONFIRMED: BookingMessageEvent.BOOKING_CONFIRMED,
        BookingMessageEvent.REMINDER: BookingMessageEvent.BOOKING_REMINDER,
        BookingMessageEvent.RESCHEDULED: BookingMessageEvent.BOOKING_RESCHEDULED,
        BookingMessageEvent.CANCELLED: BookingMessageEvent.BOOKING_CANCELLED,
        BookingMessageEvent.REFUNDED: BookingMessageEvent.PAYMENT_REFUNDED,
    }

    def __init__(self, db, provider=None):
        self.db = db
        self.provider = provider or OpenAIProvider()

    def generate(self, payload, user):
        booking = BookingService(BookingRepository(self.db)).get_for_user(payload.booking_id, user)
        event = self.LEGACY_EVENTS.get(payload.event, payload.event)
        self._validate_event(event, booking)
        facts = self._facts(event, booking)
        fact_line = self._fact_line(facts)
        fallback = f'{self._event_label(event)} {fact_line} Vui lòng kiểm tra chi tiết trong SportHub.'
        schema = {
            'type': 'object', 'additionalProperties': False,
            'properties': {'lead': {'type': 'string'}, 'closing': {'type': 'string'}},
            'required': ['lead', 'closing'],
        }
        try:
            result = self.provider.generate_json(
                task='write_booking_message_copy',
                system_data={
                    'event': event.value,
                    'instruction': (
                        'Write only a short greeting and closing without booking facts. '
                        'Do not mention codes, venues, courts, dates, times, amounts, deposits, or statuses.'
                    ),
                },
                schema=schema,
            )
            lead = str(result.get('lead', '')).strip()
            closing = str(result.get('closing', '')).strip()
            if not self._safe_copy(lead) or not self._safe_copy(closing):
                raise AIProviderError('AI attempted to alter locked booking facts')
            message = ' '.join(part for part in (lead[:180], fact_line, closing[:180]) if part)
            return {'event': payload.event, 'message': message, 'booking_facts': facts, 'source': 'ai_validated'}
        except (AIProviderError, AttributeError, TypeError, ValueError):
            return {'event': payload.event, 'message': fallback, 'booking_facts': facts, 'source': 'fallback'}

    @staticmethod
    def _facts(event, booking):
        if event == BookingMessageEvent.DEPOSIT_PAID:
            amount = float(booking.deposit_amount)
        elif event == BookingMessageEvent.PAYMENT_REFUNDED:
            amount = float(booking.refund_amount)
        elif event == BookingMessageEvent.PAYMENT_COMPLETED:
            amount = float(booking.total_amount)
        else:
            amount = float(booking.paid_amount)
        return {
            'booking_code': booking.booking_code,
            'court_name': booking.field_name,
            'venue_name': booking.facility_name,
            'date': booking.booking_date,
            'start_time': booking.start_time_snapshot,
            'end_time': booking.end_time_snapshot,
            'amount': amount,
            'deposit_amount': float(booking.deposit_amount),
            'status': booking.status.value if hasattr(booking.status, 'value') else booking.status,
        }

    @staticmethod
    def _fact_line(facts):
        return (
            f'Booking {facts["booking_code"]} · Cơ sở: {facts["venue_name"]} · '
            f'Sân: {facts["court_name"]} · Ngày: {facts["date"]:%d/%m/%Y} · '
            f'Giờ: {facts["start_time"]:%H:%M}-{facts["end_time"]:%H:%M} · '
            f'Số tiền: {facts["amount"]:,.0f}đ · Tiền cọc: {facts["deposit_amount"]:,.0f}đ · '
            f'Trạng thái: {facts["status"]}.'
        ).replace(',', '.')

    @staticmethod
    def _safe_copy(value: str) -> bool:
        forbidden = (
            'sân', 'cơ sở', 'ngày', 'giờ', 'tiền', 'trạng thái', 'booking',
            'thanh toán', 'hoàn tiền', 'đặt cọc',
        )
        lowered = value.casefold()
        return bool(value) and not re.search(r'\d|[$€£₫]', value) and not any(term in lowered for term in forbidden)

    @staticmethod
    def _validate_event(event, booking):
        cancelled = {'cancelled', 'cancelled_by_customer', 'cancelled_by_owner', 'rejected'}
        valid = {
            BookingMessageEvent.DEPOSIT_PAID: float(booking.paid_amount) >= float(booking.deposit_amount) > 0,
            BookingMessageEvent.WAITING_OWNER_CONFIRM: booking.status == 'pending_confirmation',
            BookingMessageEvent.BOOKING_CONFIRMED: booking.status in {'confirmed', 'in_progress', 'completed'},
            BookingMessageEvent.BOOKING_REMINDER: booking.status in {'confirmed', 'in_progress'},
            BookingMessageEvent.BOOKING_RESCHEDULED: bool(booking.rescheduled_at),
            BookingMessageEvent.BOOKING_CANCELLED: booking.status in cancelled,
            BookingMessageEvent.PAYMENT_COMPLETED: booking.payment_status == 'paid',
            BookingMessageEvent.PAYMENT_REFUNDED: booking.refund_status == 'refunded' or booking.payment_status == 'refunded',
        }
        if not valid.get(event, False):
            raise HTTPException(status_code=409, detail='Trạng thái booking trong DB không phù hợp với sự kiện tin nhắn đã chọn')

    @staticmethod
    def _event_label(event):
        return {
            BookingMessageEvent.DEPOSIT_PAID: 'SportHub đã ghi nhận đặt cọc thành công.',
            BookingMessageEvent.WAITING_OWNER_CONFIRM: 'Booking đang chờ OWNER xác nhận.',
            BookingMessageEvent.BOOKING_CONFIRMED: 'OWNER đã xác nhận lịch đặt của bạn.',
            BookingMessageEvent.BOOKING_REMINDER: 'SportHub nhắc bạn về lịch chơi sắp tới.',
            BookingMessageEvent.BOOKING_RESCHEDULED: 'Lịch đặt sân của bạn đã được đổi.',
            BookingMessageEvent.BOOKING_CANCELLED: 'Lịch đặt sân của bạn đã được hủy.',
            BookingMessageEvent.PAYMENT_COMPLETED: 'Thanh toán cho lịch đặt đã hoàn tất.',
            BookingMessageEvent.PAYMENT_REFUNDED: 'Khoản hoàn tiền đã được ghi nhận.',
        }[event]
