"""Workflow and communication models."""

from enum import Enum
from typing import Optional

from sqlalchemy import Column, JSON
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship

from app.models.application import KycApplication
from app.models.base import PrimaryKeyModel, TimestampedModel


class ReviewStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"


class ConversationRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ReviewTask(PrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "review_task"

    application_id: int = Field(foreign_key="kyc_application.id")
    application: Mapped[KycApplication] = Relationship(back_populates="review_tasks")

    issue_type: str
    status: ReviewStatus = Field(default=ReviewStatus.OPEN)
    ai_summary: Optional[str] = Field(default=None)
    reviewer_notes: Optional[str] = Field(default=None)


class NotificationEvent(PrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "notification_event"

    application_id: int = Field(foreign_key="kyc_application.id")
    application: Mapped[KycApplication] = Relationship(back_populates="notifications")

    channel: NotificationChannel = Field(default=NotificationChannel.IN_APP)
    message: str
    metadata_payload: Optional[dict] = Field(sa_column=Column(JSON, nullable=True), default=None)


class ConversationTurn(PrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "conversation_turn"

    application_id: Optional[int] = Field(default=None, foreign_key="kyc_application.id")
    application: Mapped[Optional[KycApplication]] = Relationship()

    role: ConversationRole
    language: str = Field(default="en")
    message: str

