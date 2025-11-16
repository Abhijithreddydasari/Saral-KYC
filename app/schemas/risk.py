"""Risk scoring schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RiskAssessmentRequest(BaseModel):
    customer_statement: Optional[str] = None


class RiskDecisionRead(BaseModel):
    id: int
    risk_score: float
    risk_band: str
    rule_version: str
    explanation: dict
    fairness_report: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True

