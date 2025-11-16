"""Conversational assistant schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=2)
    application_reference_id: str | None = None


class ChatMessageResponse(BaseModel):
    reply: str
    language: str
    safety_passed: bool
    metadata: dict

