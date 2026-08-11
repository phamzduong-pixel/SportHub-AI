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
    PARTNER_DOCUMENT_DIR = Path(os.getenv('PARTNER_DOCUMENT_DIR', str(DATA_DIR / 'private' / 'partner_documents'))).resolve()
    PARTNER_DOCUMENT_MAX_BYTES = int(os.getenv('PARTNER_DOCUMENT_MAX_BYTES', str(5 * 1024 * 1024)))
    AVATAR_DIR = Path(os.getenv('AVATAR_DIR', str(DATA_DIR / 'public' / 'avatars'))).resolve()
    AVATAR_MAX_BYTES = int(os.getenv('AVATAR_MAX_BYTES', str(5 * 1024 * 1024)))

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
