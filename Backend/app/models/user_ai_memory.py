from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from ..database.base import Base


class UserAIMemory(Base):
    """Explicit, account-scoped preferences used by the Natural Mode assistant."""

    __tablename__ = 'user_ai_memories'
    __table_args__ = (
        UniqueConstraint('user_id', 'memory_key', name='uq_user_ai_memory_key'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    memory_type = Column(String(40), nullable=False)
    memory_key = Column(String(60), nullable=False)
    value = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    source_conversation_id = Column(
        Integer,
        ForeignKey('ai_conversations.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
