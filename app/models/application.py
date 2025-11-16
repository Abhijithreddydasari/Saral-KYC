"\"\"\"KYC application and document models.\"\"\""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, JSON
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import PrimaryKeyModel, TimestampedModel
from app.models.enums import ApplicationStatus, DocumentStatus, DocumentType
from app.utils.ids import short_uuid

if TYPE_CHECKING:
    from app.models.risk import RiskDecision
    from app.models.workflow import NotificationEvent, ReviewTask

class KycApplication(PrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "kyc_application"

    reference_id: str = Field(default_factory=short_uuid, unique=True, index=True)
    full_name: str
    email: Optional[str] = Field(default=None, index=True)
    phone_number: Optional[str] = Field(default=None, index=True)
    preferred_language: Optional[str] = Field(default="en")

    status: ApplicationStatus = Field(default=ApplicationStatus.DRAFT)
    submitted_at: Optional[datetime] = Field(default=None)

    risk_score: Optional[float] = Field(default=None, ge=0, le=1)
    risk_reason: Optional[str] = Field(default=None)

    documents: Mapped[list["DocumentArtifact"]] = Relationship(back_populates="application")
    risk_decisions: Mapped[list["RiskDecision"]] = Relationship(back_populates="application")
    review_tasks: Mapped[list["ReviewTask"]] = Relationship(back_populates="application")
    notifications: Mapped[list["NotificationEvent"]] = Relationship(back_populates="application")


class DocumentArtifact(PrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "document_artifact"

    application_id: int = Field(foreign_key="kyc_application.id")
    application: Mapped[KycApplication] = Relationship(back_populates="documents")

    doc_type: DocumentType = Field(default=DocumentType.OTHER, index=True)
    status: DocumentStatus = Field(default=DocumentStatus.UPLOADED, index=True)
    storage_path: Optional[str] = Field(default=None)

    authenticity_score: Optional[float] = Field(default=None, ge=0, le=1)
    liveness_score: Optional[float] = Field(default=None, ge=0, le=1)

    extraction_payload: Optional[dict] = Field(
        sa_column=Column(JSON, nullable=True),
        default=None,
    )
    anomaly_flags: Optional[list[str]] = Field(
        sa_column=Column(JSON, nullable=True),
        default=None,
    )
    model_trace: Optional[dict] = Field(
        sa_column=Column(JSON, nullable=True),
        default=None,
    )

