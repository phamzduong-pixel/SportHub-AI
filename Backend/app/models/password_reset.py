from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from ..database.base import Base

class PasswordResetChallenge(Base):
    __tablename__ = 'password_reset_challenges'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    channel = Column(String(10), nullable=False)
    destination_hash = Column(String(64), nullable=False, index=True)
    otp_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    resend_count = Column(Integer, nullable=False, default=0)
    used = Column(Boolean, nullable=False, default=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (Index('ix_reset_challenge_active', 'destination_hash', 'channel', 'used'),)
