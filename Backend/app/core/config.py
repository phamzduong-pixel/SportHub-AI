import os
import secrets
import warnings
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / '.env')
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

class Settings:
    PROJECT_NAME = os.getenv('PROJECT_NAME', 'SportHub AI')
    SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_urlsafe(48)
    API_KEY_ENCRYPTION_KEY = os.getenv('API_KEY_ENCRYPTION_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.6')
    AI_PROVIDER_TIMEOUT_SECONDS = float(os.getenv('AI_PROVIDER_TIMEOUT_SECONDS', '8'))
    AI_PROVIDER_MAX_RETRIES = int(os.getenv('AI_PROVIDER_MAX_RETRIES', '1'))
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '1440'))
    ALGORITHM = 'HS256'
    DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{DATA_DIR / 'sporthub.db'}")
    OWNER_EMAIL = os.getenv('OWNER_EMAIL')
    OWNER_PASSWORD = os.getenv('OWNER_PASSWORD')
    OWNER_FULL_NAME = os.getenv('OWNER_FULL_NAME', 'SportHub Owner')
    CUSTOMER_EMAIL = os.getenv('CUSTOMER_EMAIL')
    CUSTOMER_PASSWORD = os.getenv('CUSTOMER_PASSWORD')
    SYSTEM_ADMIN_EMAIL = os.getenv('SYSTEM_ADMIN_EMAIL')
    SYSTEM_ADMIN_PASSWORD = os.getenv('SYSTEM_ADMIN_PASSWORD')
    SYSTEM_ADMIN_FULL_NAME = os.getenv('SYSTEM_ADMIN_FULL_NAME', 'SportHub System Admin')
    SEED_DEMO_DATA = os.getenv('SEED_DEMO_DATA', 'false').lower() in ('1', 'true', 'yes')
    SYNC_DEMO_PASSWORDS = os.getenv('SYNC_DEMO_PASSWORDS', 'false').lower() in ('1', 'true', 'yes')
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Ho_Chi_Minh')
    PAYMENT_MODE = os.getenv('PAYMENT_MODE', 'demo').lower()
    PAYMENT_WEBHOOK_SECRET = os.getenv('PAYMENT_WEBHOOK_SECRET')
    BANK_ID = os.getenv('BANK_ID', 'MB')
    BANK_NAME = os.getenv('BANK_NAME', 'MB Bank')
    BANK_ACCOUNT_NO = os.getenv('BANK_ACCOUNT_NO', '0000000000')
    BANK_ACCOUNT_NAME = os.getenv('BANK_ACCOUNT_NAME', 'SPORTHUB AI DEMO')
    CORS_ORIGINS = [item.strip() for item in os.getenv(
        'CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173',
    ).split(',') if item.strip()]
    AVATAR_DIR = Path(os.getenv('AVATAR_DIR', str(DATA_DIR / 'public' / 'avatars'))).resolve()
    AVATAR_MAX_BYTES = int(os.getenv('AVATAR_MAX_BYTES', str(5 * 1024 * 1024)))
    FACILITY_IMAGE_DIR = Path(os.getenv('FACILITY_IMAGE_DIR', str(DATA_DIR / 'public' / 'facility_images'))).resolve()
    FACILITY_PRIVATE_DIR = Path(os.getenv('FACILITY_PRIVATE_DIR', str(DATA_DIR / 'private' / 'facility_documents'))).resolve()
    FACILITY_IMAGE_MAX_BYTES = int(os.getenv('FACILITY_IMAGE_MAX_BYTES', str(5 * 1024 * 1024)))
    FACILITY_DOCUMENT_MAX_BYTES = int(os.getenv('FACILITY_DOCUMENT_MAX_BYTES', str(10 * 1024 * 1024)))

    # Email / SMTP
    EMAIL_ENABLED = os.getenv('EMAIL_ENABLED', 'false').lower() in ('1', 'true', 'yes')
    EMAIL_PROVIDER = os.getenv('EMAIL_PROVIDER', 'smtp').lower()
    SMTP_HOST = os.getenv('SMTP_HOST', '')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD') or os.getenv('SMTP_PASS', '')
    SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL') or os.getenv('SMTP_USER', 'noreply@sporthub.vn')
    SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', 'SportHub AI')
    SMTP_CRYPTO = os.getenv('SMTP_CRYPTO', '').lower()
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'true').lower() in ('1', 'true', 'yes') or SMTP_CRYPTO in ('tls', 'starttls')
    SMTP_USE_SSL = os.getenv('SMTP_USE_SSL', 'false').lower() in ('1', 'true', 'yes') or SMTP_CRYPTO == 'ssl' or SMTP_PORT == 465

    # SMS
    SMS_ENABLED = os.getenv('SMS_ENABLED', 'false').lower() in ('1', 'true', 'yes')
    SMS_PROVIDER = os.getenv('SMS_PROVIDER', 'demo').lower()
    SMS_API_KEY = os.getenv('SMS_API_KEY', '')
    SMS_SECRET_KEY = os.getenv('SMS_SECRET_KEY', '')
    SMS_ACCOUNT_SID = os.getenv('SMS_ACCOUNT_SID', '')
    SMS_FROM_NUMBER = os.getenv('SMS_FROM_NUMBER', '')
    SMS_BRAND_NAME = os.getenv('SMS_BRAND_NAME', 'SportHub')

    # Frontend URL (for email reset links)
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')

    # Password reset & OTP
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv('PASSWORD_RESET_TOKEN_EXPIRE_MINUTES', '15'))
    OTP_EXPIRE_MINUTES = int(os.getenv('OTP_EXPIRE_MINUTES', '5'))
    OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', '5'))
    OTP_MAX_RESENDS = int(os.getenv('OTP_MAX_RESENDS', '3'))

    def __init__(self):
        if not os.getenv('SECRET_KEY'):
            warnings.warn(
                'SECRET_KEY chưa được cấu hình; khóa tạm thời được tạo cho tiến trình này. '
                'Token sẽ hết hiệu lực sau khi restart. Hãy đặt SECRET_KEY khi demo/production.',
                RuntimeWarning,
                stacklevel=2,
            )
        elif len(self.SECRET_KEY) < 32:
            raise RuntimeError('SECRET_KEY phải có ít nhất 32 ký tự')
        if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            raise RuntimeError('ACCESS_TOKEN_EXPIRE_MINUTES phải lớn hơn 0')

        if self.PAYMENT_MODE not in ('demo', 'production'):
            raise RuntimeError('PAYMENT_MODE must be demo or production')
        if self.PAYMENT_MODE == 'production' and not self.PAYMENT_WEBHOOK_SECRET:
            raise RuntimeError('PAYMENT_WEBHOOK_SECRET is required in production')

settings = Settings()
