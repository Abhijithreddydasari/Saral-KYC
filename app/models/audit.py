"""Audit log models."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field

from app.models.base import PrimaryKeyModel, TimestampedModel


class AuditAction(str, Enum):
    APPLICATION_CREATED = "application_created"
    DOCUMENT_UPLOADED = "document_uploaded"
    RISK_ASSESSED = "risk_assessed"
    ESCALATED = "escalated"
    NUDGE_SENT = "nudge_sent"
    CHAT_MESSAGE = "chat_message"


class AuditEvent(PrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "audit_event"

    action: AuditAction
    entity_type: str
    entity_id: str
    actor: str = Field(default="system")
    payload: Optional[dict] = Field(sa_column=Column(JSON, nullable=True), default=None)

