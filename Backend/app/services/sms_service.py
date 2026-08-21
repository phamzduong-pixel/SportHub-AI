"""SMS service for sending transactional SMS messages (e.g. OTP verification)."""

import logging
import re
import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


def normalize_vietnamese_phone_e164(phone: str) -> str:
    """Normalize Vietnamese phone number to E.164 format (+84...)."""
    cleaned = re.sub(r'[\s\-.]', '', phone.strip())
    if cleaned.startswith('+84'):
        return cleaned
    if cleaned.startswith('84') and len(cleaned) == 11:
        return f"+{cleaned}"
    if cleaned.startswith('0') and len(cleaned) == 10:
        return f"+84{cleaned[1:]}"
    return cleaned


def send_otp(phone: str, otp_code: str) -> None:
    """Send an OTP code to the given phone number via SMS.

    Raises RuntimeError when SMS is not enabled or credentials are missing.
    """
    provider = (settings.SMS_PROVIDER or 'demo').lower().strip()
    if provider in ('demo', 'mock', 'log'):
        logger.info('[DEMO SMS OTP] Gui OTP toi %s: Ma xac thuc la %s', phone, otp_code)
        return

    if not settings.SMS_ENABLED:
        raise RuntimeError(
            'Chức năng gửi SMS hiện đang bảo trì, vui lòng sử dụng Email'
        )

    message_body = f"[{settings.SMS_BRAND_NAME}] Ma OTP dat lai mat khau cua ban la: {otp_code}. Ma co hieu luc trong {settings.OTP_EXPIRE_MINUTES} phut."

    if provider == 'twilio':
        account_sid = settings.SMS_ACCOUNT_SID
        from_number = settings.SMS_FROM_NUMBER
        auth_token = settings.SMS_SECRET_KEY or settings.SMS_API_KEY
        if not account_sid or not from_number or not auth_token:
            raise RuntimeError('Thiếu cấu hình Twilio (SMS_ACCOUNT_SID, SMS_FROM_NUMBER, SMS_API_KEY/SMS_SECRET_KEY). Kiểm tra lại .env')

        to_number = normalize_vietnamese_phone_e164(phone)
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url,
                    data={'To': to_number, 'From': from_number, 'Body': message_body},
                    auth=(account_sid, auth_token),
                )
                response.raise_for_status()
                logger.info('Twilio SMS OTP sent successfully to %s', to_number)
        except Exception as exc:
            logger.exception('Failed to send SMS via Twilio to %s: %s', to_number, exc)
            raise RuntimeError(f'Không thể gửi SMS qua Twilio: {exc}') from exc

    elif provider == 'esms':
        api_key = settings.SMS_API_KEY
        secret_key = settings.SMS_SECRET_KEY
        if not api_key or not secret_key:
            raise RuntimeError('Thiếu cấu hình eSMS (SMS_API_KEY, SMS_SECRET_KEY). Kiểm tra lại .env')

        url = 'http://rest.esms.vn/MainService.svc/json/SendMultipleMessage_V4_post_json'
        payload = {
            'ApiKey': api_key,
            'SecretKey': secret_key,
            'Phone': phone.strip(),
            'Content': message_body,
            'SmsType': '2',  # OTP Brandname or normal
            'Brandname': settings.SMS_BRAND_NAME,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                res_data = response.json()
                if res_data.get('CodeResult') != '100':
                    error_msg = res_data.get('ErrorMessage') or 'Gửi SMS thất bại từ cổng eSMS'
                    raise RuntimeError(f'Lỗi eSMS: {error_msg}')
                logger.info('eSMS OTP sent successfully to %s', phone)
        except Exception as exc:
            logger.exception('Failed to send SMS via eSMS to %s: %s', phone, exc)
            raise RuntimeError(f'Không thể gửi SMS qua eSMS: {exc}') from exc

    else:
        raise RuntimeError(
            f'SMS_PROVIDER="{settings.SMS_PROVIDER}" không được hỗ trợ. '
            f'Các provider hỗ trợ: twilio, esms, demo. Kiểm tra lại .env'
        )

