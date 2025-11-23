"""Admin-only monitoring endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps.auth import get_current_admin
from app.api.deps.db import get_db
from app.models.application import DocumentArtifact, KycApplication
from app.models.user import User
from app.schemas.admin import (
    AdminDocumentInsight,
    AdminGraph,
    AdminMonitoringResponse,
    AdminRiskProfile,
    AdminUserOverview,
    GraphEdge,
    GraphNode,
)
from app.services.risk_catalog import derive_risk_category, risk_reasons_for

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminMonitoringResponse)
def get_admin_overview(
    session: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminMonitoringResponse:
    users = session.exec(select(User)).all()
    snapshots = [
        _build_user_overview(user, session)
        for user in users
        if not user.is_admin
    ]
    return AdminMonitoringResponse(users=snapshots)


@router.get("/users/{user_id}", response_model=AdminUserOverview)
def get_admin_user_snapshot(
    user_id: int,
    session: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminUserOverview:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Admin accounts are not monitored")
    return _build_user_overview(user, session)


def _build_user_overview(user: User, session: Session) -> AdminUserOverview:
    applications = session.exec(select(KycApplication).where(KycApplication.user_id == user.id)).all()
    for application in applications:
        application.documents = session.exec(
            select(DocumentArtifact).where(DocumentArtifact.application_id == application.id)
        ).all()

    all_documents: list[DocumentArtifact] = []
    for application in applications:
        all_documents.extend(application.documents or [])

    insights = [
        AdminDocumentInsight(
            document_id=document.id,
            doc_type=document.doc_type.value,
            extracted_fields=document.extraction_payload,
        )
        for document in all_documents
        if document.extraction_payload
    ]

    risk_profile = _build_risk_profile(applications)
    graph = _build_graph_payload(user, applications, risk_profile)

    return AdminUserOverview(
        user=user,
        applications=applications,
        documents=all_documents,
        insights=insights,
        risk_profile=risk_profile,
        graph=graph,
    )


def _build_risk_profile(applications: list[KycApplication]) -> AdminRiskProfile:
    if not applications:
        category = "medium"
        score = 0.5
        reasons = risk_reasons_for(category)
        return AdminRiskProfile(application_id=None, category=category, score=score, reasons=reasons)

    latest_application = max(applications, key=lambda app: app.created_at)
    category, score = derive_risk_category(latest_application.risk_score, latest_application.reference_id)
    reasons = risk_reasons_for(category)
    return AdminRiskProfile(
        application_id=latest_application.id,
        category=category,
        score=score,
        reasons=reasons,
    )


def _build_graph_payload(
    user: User,
    applications: list[KycApplication],
    risk_profile: AdminRiskProfile,
) -> AdminGraph:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def add_node(node: GraphNode) -> None:
        if node.id not in nodes:
            nodes[node.id] = node

    user_node_id = f"user-{user.id}"
    add_node(GraphNode(id=user_node_id, label=user.full_name, kind="user", risk=risk_profile.category))

    risk_node_id = f"risk-{user.id}"
    add_node(
        GraphNode(
            id=risk_node_id,
            label=f"Risk: {risk_profile.category.title()}",
            kind="risk",
            risk=risk_profile.category,
        )
    )
    edges.append(GraphEdge(source=user_node_id, target=risk_node_id, label="risk"))

    for application in applications:
        app_node_id = f"application-{application.id}"
        add_node(GraphNode(id=app_node_id, label=f"KYC #{application.id}", kind="application", risk=application.status.value))
        edges.append(GraphEdge(source=user_node_id, target=app_node_id, label="owns"))

        for document in application.documents or []:
            doc_node_id = f"document-{document.id}"
            doc_risk = "high" if (document.anomaly_flags or (document.liveness_score and document.liveness_score < 0.5)) else "safe"
            add_node(GraphNode(id=doc_node_id, label=document.doc_type.value.upper(), kind="document", risk=doc_risk))
            edges.append(GraphEdge(source=app_node_id, target=doc_node_id, label="document"))

            if document.anomaly_flags:
                flag_node_id = f"flag-{document.id}"
                add_node(GraphNode(id=flag_node_id, label="Alert", kind="flag", risk="high"))
                edges.append(GraphEdge(source=doc_node_id, target=flag_node_id, label="anomaly"))

    return AdminGraph(nodes=list(nodes.values()), edges=edges)

