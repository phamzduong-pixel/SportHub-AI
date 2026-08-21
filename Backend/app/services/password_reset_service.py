import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.password_reset import PasswordResetChallenge

GENERIC = 'Nếu thông tin tồn tại trong hệ thống, mã xác nhận sẽ được gửi đến bạn.'


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_challenge(db: Session, user_id: int, destination: str, channel: str) -> str:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=10)
    all_challenges = db.scalars(select(PasswordResetChallenge).where(
        PasswordResetChallenge.user_id == user_id,
        PasswordResetChallenge.channel == channel,
    )).all()
    recent = [c for c in all_challenges if _as_utc(c.created_at) >= cutoff]

    if len(recent) >= settings.OTP_MAX_RESENDS + 1:
        raise HTTPException(429, 'Bạn đã yêu cầu mã quá nhiều lần. Vui lòng thử lại sau 10 phút.')

    code = ''.join(str(secrets.randbelow(10)) for _ in range(6))
    challenge = PasswordResetChallenge(
        user_id=user_id,
        channel=channel,
        destination_hash=_hash(destination),
        otp_hash=_hash(code),
        expires_at=now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        resend_count=len(recent),
    )
    db.add(challenge)
    db.commit()
    return code


def verify_challenge(db: Session, user_id: int, destination: str, channel: str, code: str) -> None:
    item = db.scalar(
        select(PasswordResetChallenge).where(
            PasswordResetChallenge.user_id == user_id,
            PasswordResetChallenge.channel == channel,
            PasswordResetChallenge.destination_hash == _hash(destination),
            PasswordResetChallenge.used.is_(False),
        ).order_by(PasswordResetChallenge.created_at.desc())
    )
    now = datetime.now(timezone.utc)
    if not item or _as_utc(item.expires_at) < now:
        raise HTTPException(400, 'Mã xác nhận không đúng hoặc đã hết hạn.')

    item.attempts += 1
    if item.attempts > settings.OTP_MAX_ATTEMPTS:
        item.used = True
        db.commit()
        raise HTTPException(429, 'Mã xác nhận đã bị khóa do nhập sai quá số lần cho phép.')

    if not secrets.compare_digest(item.otp_hash, _hash(code)):
        db.commit()
        raise HTTPException(400, 'Mã xác nhận không đúng hoặc đã hết hạn.')

    item.used = True
    item.verified_at = now
    db.commit()
