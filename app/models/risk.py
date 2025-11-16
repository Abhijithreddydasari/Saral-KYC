"""Risk decision models."""

from typing import Optional

from sqlalchemy import Column, JSON
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship

from app.models.application import KycApplication
from app.models.base import PrimaryKeyModel, TimestampedModel


class RiskDecision(PrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "risk_decision"

    application_id: int = Field(foreign_key="kyc_application.id")
    application: Mapped[KycApplication] = Relationship(back_populates="risk_decisions")

    risk_score: float = Field(ge=0, le=1)
    risk_band: str = Field(default="medium")
    rule_version: str = Field(default="2024.11")

    explanation: dict = Field(sa_column=Column(JSON, nullable=False))
    fairness_report: Optional[dict] = Field(sa_column=Column(JSON, nullable=True), default=None)

