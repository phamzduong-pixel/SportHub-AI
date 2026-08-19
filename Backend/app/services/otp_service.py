"""OTP (One-Time Password) service for phone-based password recovery.

OTPs are stored in-process memory. Each OTP expires after OTP_EXPIRE_MINUTES and
can only be verified up to OTP_MAX_ATTEMPTS times. A phone number can request
at most 3 OTPs within any 10-minute window to prevent abuse.
"""

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field

from ..core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class _OTPEntry:
    code: str
    created_at: float
    expires_at: float
    attempts: int = 0
    used: bool = False


# In-memory store keyed by hashed phone number
_store: dict[str, _OTPEntry] = {}
# Rate-limit tracker: phone_hash -> list of timestamps
_rate_limit: dict[str, list[float]] = {}

_RATE_WINDOW_SECONDS = 600  # 10 minutes
_RATE_MAX_REQUESTS = 3


def _phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def _cleanup_expired() -> None:
    """Remove expired entries from the store."""
    now = time.time()
    expired_keys = [k for k, v in _store.items() if v.expires_at < now]
    for k in expired_keys:
        del _store[k]


def generate_otp(phone: str) -> str:
    """Generate a 6-digit OTP for the given phone number.

    Raises ValueError if rate-limited.
    Returns the OTP code string.
    """
    _cleanup_expired()
    key = _phone_hash(phone)
    now = time.time()

    # Rate limiting
    timestamps = _rate_limit.get(key, [])
    timestamps = [t for t in timestamps if t > now - _RATE_WINDOW_SECONDS]
    if len(timestamps) >= _RATE_MAX_REQUESTS:
        raise ValueError('Bạn đã yêu cầu OTP quá nhiều lần. Vui lòng thử lại sau 10 phút.')
    timestamps.append(now)
    _rate_limit[key] = timestamps

    code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    _store[key] = _OTPEntry(
        code=code,
        created_at=now,
        expires_at=now + settings.OTP_EXPIRE_MINUTES * 60,
    )
    logger.info('OTP generated for phone hash %s...', key[:8])
    return code


def verify_otp(phone: str, code: str) -> bool:
    """Verify an OTP for the given phone number.

    Returns True if valid. Returns False if invalid, expired, or max attempts exceeded.
    Marks OTP as used on success (single-use).
    """
    _cleanup_expired()
    key = _phone_hash(phone)
    entry = _store.get(key)

    if not entry:
        return False

    if entry.used:
        return False

    if time.time() > entry.expires_at:
        del _store[key]
        return False

    entry.attempts += 1
    if entry.attempts > settings.OTP_MAX_ATTEMPTS:
        del _store[key]
        return False

    if not secrets.compare_digest(entry.code, code):
        return False

    # Success — mark as used
    entry.used = True
    return True
