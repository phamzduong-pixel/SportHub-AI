"""Email service using aiosmtplib for sending transactional emails (e.g. password reset)."""

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
<head><meta charset="UTF-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; padding: 40px 0;">
<div style="max-width: 480px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,.1);">
  <h2 style="color: #1e293b; margin: 0 0 16px;">Đặt lại mật khẩu</h2>
  <p style="color: #475569; font-size: 15px; line-height: 1.6;">
    Bạn (hoặc ai đó) đã yêu cầu đặt lại mật khẩu tài khoản SportHub AI. Bấm nút bên dưới để tạo mật khẩu mới:
  </p>
  <div style="text-align: center; margin: 28px 0;">
    <a href="{reset_link}" style="display: inline-block; background: #2563eb; color: #fff; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
      Đặt lại mật khẩu
    </a>
  </div>
  <p style="color: #94a3b8; font-size: 13px; line-height: 1.5;">
    Liên kết có hiệu lực trong <b>{expire_minutes} phút</b>. Nếu bạn không yêu cầu, hãy bỏ qua email này.
  </p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
  <p style="color: #cbd5e1; font-size: 12px; text-align: center;">SportHub AI — Nền tảng đặt sân thể thao</p>
</div>
</body>
</html>"""


async def _send_email_async(to_email: str, subject: str, html_body: str) -> None:
    """Send an email via SMTP. Raises on failure."""
    message = MIMEMultipart('alternative')
    message['From'] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message['To'] = to_email
    message['Subject'] = subject
    message.attach(MIMEText(html_body, 'html', 'utf-8'))

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=settings.SMTP_USE_TLS,
    )


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    """Build reset link, render HTML, and send the email synchronously.

    Raises RuntimeError when EMAIL_ENABLED is False or SMTP config is missing.
    Raises aiosmtplib errors on delivery failure.
    """
    if not settings.EMAIL_ENABLED:
        raise RuntimeError(
            'Gửi email chưa được bật. Hãy cấu hình EMAIL_ENABLED=true và các biến SMTP trong .env'
        )
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise RuntimeError(
            'Thiếu cấu hình SMTP (SMTP_HOST, SMTP_USER, SMTP_PASSWORD). Kiểm tra lại .env'
        )

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    html_body = _build_reset_email_html(reset_link, settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    logger.info('Sending password reset email to %s', to_email)
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_send_email_async(to_email, 'Đặt lại mật khẩu — SportHub AI', html_body))
        loop.close()
        logger.info('Password reset email sent successfully to %s', to_email)
    except Exception:
        logger.exception('Failed to send password reset email to %s', to_email)
        raise
