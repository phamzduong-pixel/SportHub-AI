"""SMS service placeholder.

This module defines a clear interface for sending SMS messages (e.g. OTPs).
Until a real SMS provider (eSMS, Twilio, etc.) is configured, calling send_otp()
will raise a descriptive error so the frontend can display an honest message
instead of pretending the SMS was sent.
"""

import logging

from ..core.config import settings

logger = logging.getLogger(__name__)


def send_otp(phone: str, otp_code: str) -> None:
    """Send an OTP code to the given phone number via SMS.

    Raises RuntimeError when SMS is not enabled or no provider is configured.
    When a real provider is integrated, implement the actual HTTP call here.
    """
    if not settings.SMS_ENABLED:
        raise RuntimeError(
            'Chức năng gửi SMS chưa được bật. Cấu hình SMS_ENABLED=true và SMS provider trong .env'
        )

    provider = settings.SMS_PROVIDER.lower()

    if provider == 'twilio':
        # TODO: Implement Twilio SMS sending
        # from twilio.rest import Client
        # client = Client(settings.SMS_API_KEY, settings.SMS_SECRET_KEY)
        # client.messages.create(body=f'Mã OTP SportHub: {otp_code}', from_=settings.SMS_BRAND_NAME, to=phone)
        raise NotImplementedError('Twilio SMS chưa được tích hợp. Hãy implement send logic tại sms_service.py')

    elif provider == 'esms':
        # TODO: Implement eSMS (Vietnam) sending
        # import httpx
        # httpx.post('https://rest.esms.vn/MainService.svc/json/SendMultipleMessage_V4_post', json={...})
        raise NotImplementedError('eSMS chưa được tích hợp. Hãy implement send logic tại sms_service.py')

    else:
        raise RuntimeError(
            f'SMS_PROVIDER="{settings.SMS_PROVIDER}" không được hỗ trợ. '
            f'Các provider hỗ trợ: twilio, esms. Kiểm tra lại .env'
        )
