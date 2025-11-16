"""Schemas for KYC application + documents."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import ApplicationStatus, DocumentStatus, DocumentType


class DocumentBase(BaseModel):
    doc_type: DocumentType


class DocumentUpload(DocumentBase):
    pass


class DocumentRead(DocumentBase):
    id: int
    status: DocumentStatus
    authenticity_score: Optional[float]
    liveness_score: Optional[float]
    anomaly_flags: Optional[List[str]]
    extraction_payload: Optional[dict]
    model_trace: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationBase(BaseModel):
    full_name: str = Field(..., min_length=3)
    email: Optional[str] = None
    phone_number: Optional[str] = None
    preferred_language: Optional[str] = Field(default="en")


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationRead(ApplicationBase):
    id: int
    reference_id: str
    status: ApplicationStatus
    submitted_at: Optional[datetime]
    risk_score: Optional[float]
    risk_reason: Optional[str]
    documents: List[DocumentRead] = Field(default_factory=list)

    class Config:
        from_attributes = True

