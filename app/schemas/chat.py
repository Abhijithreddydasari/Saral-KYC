"""Conversational assistant schemas."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=2)
    application_reference_id: str | None = None


class ChatMessageResponse(BaseModel):
    reply: str
    language: str
    safety_passed: bool
    metadata: dict


class AssistantBootstrapResponse(BaseModel):
    welcome: str
    languages: List[str]
    safety_disclaimer: str
    suggestion_prompts: List[str]
    rate_limits: dict

