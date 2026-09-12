from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
from sqlalchemy import Column, String, DateTime, Text, JSON, Integer, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    metadata_json = Column(JSON, default=dict)

    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan", order_by="MessageModel.created_at")

class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=True)
    name = Column(String(128), nullable=True)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(64), nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    session = relationship("SessionModel", back_populates="messages")

class MemoryEntityModel(Base):
    __tablename__ = "memory_entities"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    project = Column(String(128), index=True, default="default")
    topic = Column(String(128), index=True, nullable=False)
    summary = Column(Text, nullable=False)
    raw_content = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(64), index=True, nullable=False)
    actor = Column(String(64), nullable=False)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)