from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from ..database.base import Base


class AIConversation(Base):
    __tablename__ = 'ai_conversations'

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    context_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship('User')
    messages = relationship('AIMessage', back_populates='conversation', cascade='all, delete-orphan', order_by='AIMessage.created_at.asc()')


class AIMessage(Base):
    __tablename__ = 'ai_messages'

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey('ai_conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    conversation = relationship('AIConversation', back_populates='messages')
