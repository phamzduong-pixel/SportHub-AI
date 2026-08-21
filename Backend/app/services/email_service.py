"""Email service using aiosmtplib for sending transactional emails (e.g. password reset OTP)."""

import asyncio
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from ..core.config import settings

logger = logging.getLogger(__name__)


def _build_reset_email_html(reset_link: str, expire_minutes: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Đặt lại mật khẩu - SportHub AI</title>
</head>
<body style="margin: 0; padding: 40px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc; color: #334155;">
  <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0;">
    <div style="background: linear-gradient(135deg, #1d4ed8, #2563eb); padding: 32px 24px; text-align: center;">
      <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">SportHub AI</h1>
      <p style="color: #bfdbfe; margin: 6px 0 0 0; font-size: 14px;">Nền tảng đặt sân thể thao thông minh</p>
    </div>
    <div style="padding: 32px 28px;">
      <h2 style="color: #1e293b; margin: 0 0 16px; font-size: 20px; font-weight: 600;">Yêu cầu đặt lại mật khẩu</h2>
      <p style="color: #475569; font-size: 15px; line-height: 1.6; margin: 0 0 24px;">
        Bạn (hoặc ai đó) đã gửi yêu cầu đặt lại mật khẩu cho tài khoản SportHub AI. Nhấn vào nút bên dưới để tiến hành tạo mật khẩu mới:
      </p>
      <div style="text-align: center; margin: 32px 0;">
        <a href="{reset_link}" style="display: inline-block; background: #2563eb; color: #ffffff; padding: 14px 32px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 15px; box-shadow: 0 2px 4px rgba(37, 99, 235, 0.3);">
          Đặt lại mật khẩu
        </a>
      </div>
      <p style="color: #64748b; font-size: 13px; line-height: 1.5; margin: 0 0 12px; background: #f1f5f9; padding: 12px 16px; border-radius: 8px;">
        ⏱ Liên kết này có hiệu lực trong <b>{expire_minutes} phút</b>. Nếu bạn không gửi yêu cầu này, vui lòng bỏ qua email này. Tài khoản của bạn vẫn an toàn.
      </p>
    </div>
    <div style="border-top: 1px solid #f1f5f9; padding: 20px 28px; background: #fafafa; text-align: center;">
      <p style="color: #94a3b8; font-size: 12px; margin: 0;">SportHub AI — Đặt sân thể thao nhanh chóng & tiện lợi</p>
    </div>
  </div>
</body>
</html>"""


def _build_reset_otp_html(otp_code: str, expire_minutes: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mã xác nhận OTP - SportHub AI</title>
</head>
<body style="margin: 0; padding: 40px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc; color: #334155;">
  <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0;">
    <div style="background: linear-gradient(135deg, #1d4ed8, #2563eb); padding: 32px 24px; text-align: center;">
      <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">SportHub AI</h1>
      <p style="color: #bfdbfe; margin: 6px 0 0 0; font-size: 14px;">Nền tảng đặt sân thể thao thông minh</p>
    </div>
    <div style="padding: 32px 28px;">
      <h2 style="color: #1e293b; margin: 0 0 16px; font-size: 20px; font-weight: 600;">Mã xác thực đặt lại mật khẩu</h2>
      <p style="color: #475569; font-size: 15px; line-height: 1.6; margin: 0 0 24px;">
        Dưới đây là mã OTP 6 chữ số để khôi phục mật khẩu tài khoản SportHub AI của bạn:
      </p>
      <div style="text-align: center; margin: 28px 0;">
        <div style="display: inline-block; background: #eff6ff; border: 2px dashed #3b82f6; border-radius: 12px; padding: 16px 36px;">
          <span style="font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #1d4ed8; font-family: monospace;">{otp_code}</span>
        </div>
      </div>
      <p style="color: #64748b; font-size: 13px; line-height: 1.5; margin: 0 0 12px; background: #f1f5f9; padding: 12px 16px; border-radius: 8px;">
        ⏱ Mã xác thực này có hiệu lực trong <b>{expire_minutes} phút</b>. Tuyệt đối không chia sẻ mã này cho bất kỳ ai.
      </p>
    </div>
    <div style="border-top: 1px solid #f1f5f9; padding: 20px 28px; background: #fafafa; text-align: center;">
      <p style="color: #94a3b8; font-size: 12px; margin: 0;">SportHub AI — Đặt sân thể thao nhanh chóng & tiện lợi</p>
    </div>
  </div>
</body>
</html>"""


async def _send_email_async(to_email: str, subject: str, html_body: str) -> None:
    """Send an email via SMTP. Raises on failure."""
    message = MIMEMultipart('alternative')
    from_header = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>" if settings.SMTP_FROM_NAME else settings.SMTP_FROM_EMAIL
    message['From'] = from_header
    message['To'] = to_email
    message['Subject'] = subject
    message.attach(MIMEText(html_body, 'html', 'utf-8'))

    send_kwargs = {
        'hostname': settings.SMTP_HOST,
        'port': settings.SMTP_PORT,
        'username': settings.SMTP_USER or None,
        'password': settings.SMTP_PASSWORD or None,
    }

    if settings.SMTP_USE_SSL:
        send_kwargs['use_tls'] = True
    elif settings.SMTP_USE_TLS:
        send_kwargs['start_tls'] = True

    await aiosmtplib.send(message, **send_kwargs)


def _check_smtp_configured() -> None:
    if not settings.EMAIL_ENABLED:
        raise RuntimeError('Gửi email chưa được bật. Hãy cấu hình EMAIL_ENABLED=true và các biến SMTP trong .env')
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise RuntimeError('Thiếu cấu hình SMTP (SMTP_HOST, SMTP_USER, SMTP_PASSWORD). Hãy kiểm tra lại file .env')


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    """Build reset link, render HTML, and send the email synchronously."""
    if settings.EMAIL_PROVIDER == 'demo':
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        logger.info('[DEMO EMAIL] Gui link dat lai mat khau toi %s: %s', to_email, reset_link)
        return

    _check_smtp_configured()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    html_body = _build_reset_email_html(reset_link, settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    logger.info('Sending password reset email to %s', to_email)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_send_email_async(to_email, 'Đặt lại mật khẩu — SportHub AI', html_body))
        logger.info('Password reset email sent successfully to %s', to_email)
    except aiosmtplib.SMTPAuthenticationError as exc:
        logger.exception('SMTP Authentication failed for %s: %s', to_email, exc)
        raise RuntimeError('Tài khoản hoặc mật khẩu SMTP không chính xác. Vui lòng kiểm tra lại cấu hình .env.') from exc
    except (aiosmtplib.SMTPConnectError, aiosmtplib.SMTPServerDisconnected, TimeoutError, asyncio.TimeoutError) as exc:
        logger.exception('SMTP Connection failed for %s: %s', to_email, exc)
        raise RuntimeError('Không thể kết nối đến máy chủ gửi email. Vui lòng kiểm tra lại kết nối mạng hoặc SMTP_HOST.') from exc
    except Exception as exc:
        logger.exception('Failed to send password reset email to %s: %s', to_email, exc)
        raise RuntimeError(f'Lỗi khi gửi email: {exc}') from exc
    finally:
        loop.close()


def send_password_reset_otp(to_email: str, otp_code: str) -> None:
    """Send a 6-digit OTP code to the given email address synchronously."""
    if settings.EMAIL_PROVIDER == 'demo':
        logger.info('[DEMO EMAIL OTP] Gui OTP toi %s: Ma xac thuc la %s', to_email, otp_code)
        return

    _check_smtp_configured()

    html_body = _build_reset_otp_html(otp_code, settings.OTP_EXPIRE_MINUTES)

    logger.info('Sending password reset OTP to %s', to_email)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_send_email_async(to_email, 'Mã xác thực đặt lại mật khẩu — SportHub AI', html_body))
        logger.info('Password reset OTP email sent successfully to %s', to_email)
    except aiosmtplib.SMTPAuthenticationError as exc:
        logger.exception('SMTP Authentication failed for %s: %s', to_email, exc)
        raise RuntimeError('Tài khoản hoặc mật khẩu SMTP không chính xác. Vui lòng kiểm tra lại cấu hình .env.') from exc
    except (aiosmtplib.SMTPConnectError, aiosmtplib.SMTPServerDisconnected, TimeoutError, asyncio.TimeoutError) as exc:
        logger.exception('SMTP Connection failed for %s: %s', to_email, exc)
        raise RuntimeError('Không thể kết nối đến máy chủ gửi email. Vui lòng kiểm tra lại kết nối mạng hoặc SMTP_HOST.') from exc
    except Exception as exc:
        logger.exception('Failed to send password reset OTP to %s: %s', to_email, exc)
        raise RuntimeError(f'Lỗi khi gửi email: {exc}') from exc
    finally:
        loop.close()