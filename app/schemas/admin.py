"""Schemas powering admin monitoring dashboards."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from app.schemas.application import ApplicationRead, DocumentRead
from app.schemas.user import UserRead


class AdminDocumentInsight(BaseModel):
    document_id: int
    doc_type: str
    extracted_fields: Optional[dict]


class AdminRiskProfile(BaseModel):
    application_id: Optional[int]
    category: str
    score: float
    reasons: List[str]


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str
    risk: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str


class AdminGraph(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class AdminUserOverview(BaseModel):
    user: UserRead
    applications: List[ApplicationRead]
    documents: List[DocumentRead]
    insights: List[AdminDocumentInsight]
    risk_profile: AdminRiskProfile
    graph: AdminGraph


class AdminMonitoringResponse(BaseModel):
    users: List[AdminUserOverview]

