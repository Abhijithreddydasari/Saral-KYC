"""Workflow + notification schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus
from app.models.workflow import NotificationChannel, ReviewStatus


class ReviewCreate(BaseModel):
    issue_type: str = Field(..., min_length=3)
    ai_summary: Optional[str] = None


class ReviewRead(ReviewCreate):
    id: int
    status: ReviewStatus
    reviewer_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    channel: NotificationChannel = NotificationChannel.IN_APP
    message: str = Field(..., min_length=5)
    metadata: Optional[dict] = None


class NotificationRead(NotificationCreate):
    id: int
    created_at: datetime
    metadata: Optional[dict] = Field(default=None, alias="metadata_payload")

    class Config:
        from_attributes = True
        allow_population_by_field_name = True


class TimelineEntry(BaseModel):
    event_type: str
    message: str
    created_at: datetime
    payload: Optional[dict] = None


class ApplicationTimeline(BaseModel):
    application_id: int
    status: str
    entries: List[TimelineEntry]

