"""Conversational assistant endpoints."""

from __future__ import annotations

from __future__ import annotations

import asyncio
from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.api.deps.db import get_db
from app.models.application import DocumentArtifact, KycApplication
from app.models.risk import RiskDecision
from app.models.workflow import NotificationEvent
from app.schemas.chat import AssistantBootstrapResponse, ChatMessageRequest, ChatMessageResponse
from app.services.conversational import ConversationalAgent

router = APIRouter(prefix="/assist", tags=["assistant"])
agent = ConversationalAgent()


def _isoformat(value) -> str | None:
    return value.isoformat() if value else None


def _summarize_documents(documents: List[DocumentArtifact]) -> list[dict]:
    summary: list[dict] = []
    for doc in documents:
        summary.append(
            {
                "doc_type": doc.doc_type.value,
                "status": doc.status.value,
                "authenticity_score": doc.authenticity_score,
                "liveness_score": doc.liveness_score,
                "uploaded_at": _isoformat(doc.created_at),
            }
        )
    return summary


def _summarize_notifications(events: List[NotificationEvent]) -> list[dict]:
    summary: list[dict] = []
    for event in events:
        summary.append(
            {
                "channel": event.channel.value,
                "message": event.message,
                "created_at": _isoformat(event.created_at),
            }
        )
    return summary


def _summarize_risk(application: KycApplication, decisions: List[RiskDecision]) -> dict:
    latest_decisions = [
        {
            "risk_score": decision.risk_score,
            "risk_band": decision.risk_band,
            "rule_version": decision.rule_version,
            "created_at": _isoformat(decision.created_at),
        }
        for decision in decisions[:3]
    ]
    return {
        "current_score": application.risk_score,
        "current_reason": application.risk_reason,
        "history": latest_decisions,
    }


def _build_application_context(
    payload: ChatMessageRequest,
    session: Session,
) -> Tuple[KycApplication | None, dict]:
    if not payload.application_reference_id:
        return None, {}

    application = session.exec(
        select(KycApplication).where(KycApplication.reference_id == payload.application_reference_id)
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found for reference ID")

    documents = session.exec(
        select(DocumentArtifact).where(DocumentArtifact.application_id == application.id).order_by(DocumentArtifact.id)
    ).all()
    notifications = session.exec(
        select(NotificationEvent)
        .where(NotificationEvent.application_id == application.id)
        .order_by(NotificationEvent.created_at.desc())
    ).all()
    risk_decisions = session.exec(
        select(RiskDecision)
        .where(RiskDecision.application_id == application.id)
        .order_by(RiskDecision.created_at.desc())
    ).all()

    profile = {
        "reference_id": application.reference_id,
        "full_name": application.full_name,
        "parent_name": application.parent_name,
        "contact_number": application.contact_number or application.phone_number,
        "email": application.email or (application.user.email if application.user else None),
        "nationality": application.nationality,
        "address_line": application.address_line,
        "pincode": application.pincode,
    }
    preferences = {
        "preferred_language": application.preferred_language,
    }
    latest_activity = {
        "status": application.status.value,
        "submitted_at": _isoformat(application.submitted_at),
        "completed_at": _isoformat(application.completed_at),
        "last_updated": _isoformat(application.updated_at),
        "recent_notification": notifications[0].message if notifications else None,
    }

    context = {
        "profile": profile,
        "preferences": preferences,
        "latest_activity": latest_activity,
        "documents": _summarize_documents(documents),
        "notifications": _summarize_notifications(notifications[:5]),
        "risk": _summarize_risk(application, risk_decisions),
    }

    return application, context


def _build_chat_response(payload: ChatMessageRequest, session: Session) -> ChatMessageResponse:
    _application, context = _build_application_context(payload, session)
    history_payload = [turn.dict() for turn in payload.history]
    result = agent.respond(
        message=payload.message,
        context=context,
        history=history_payload,
        system_prompt=payload.system_prompt,
    )
    return ChatMessageResponse(
        reply=result.reply,
        language=result.language,
        safety_passed=result.safety_passed,
        metadata=result.metadata,
    )


def _chunk_reply(text: str, chunk_size: int = 40) -> list[str]:
    tokens = text.split(" ")
    chunks = []
    current: list[str] = []
    for token in tokens:
        current.append(token)
        if sum(len(word) + 1 for word in current) >= chunk_size:
            chunks.append(" ".join(current) + " ")
            current = []
    if current:
        chunks.append(" ".join(current) + " ")
    return chunks or [text]


@router.get("/session/bootstrap", response_model=AssistantBootstrapResponse)
def bootstrap_session() -> AssistantBootstrapResponse:
    """Provides metadata for initializing the assistant widget."""
    return AssistantBootstrapResponse(
        welcome="Namaste! I’m Saral, your multilingual KYC assistant.",
        languages=["en", "hi", "bn"],
        safety_disclaimer="Conversations are monitored and logged for compliance.",
        suggestion_prompts=[
            "What documents are pending for my application?",
            "Can you escalate my KYC review?",
            "How long until verification completes?",
            "Send me the latest status update.",
        ],
        rate_limits={"per_minute": 5, "per_hour": 30},
    )


def _build_headers(response: ChatMessageResponse) -> dict[str, str]:
    headers = {"X-Assistant-Language": response.language}
    metadata = response.metadata or {}
    if model := metadata.get("model"):
        headers["X-Assistant-Model"] = str(model)
    if backend := metadata.get("backend"):
        headers["X-Assistant-Backend"] = str(backend)
    if input_tokens := metadata.get("input_tokens"):
        headers["X-Assistant-Input-Tokens"] = str(input_tokens)
    if output_tokens := metadata.get("output_tokens"):
        headers["X-Assistant-Output-Tokens"] = str(output_tokens)
    return headers


@router.post("/chat", response_model=ChatMessageResponse)
def chat(payload: ChatMessageRequest, response: Response, session: Session = Depends(get_db)) -> ChatMessageResponse:
    chat_response = _build_chat_response(payload, session)
    response.headers.update(_build_headers(chat_response))
    return chat_response


@router.post("/chat/stream")
async def chat_stream(payload: ChatMessageRequest, session: Session = Depends(get_db)) -> StreamingResponse:
    response = _build_chat_response(payload, session)
    chunks = _chunk_reply(response.reply)

    async def iterator():
        for chunk in chunks:
            yield chunk
            await asyncio.sleep(0.1)

    headers = _build_headers(response)
    return StreamingResponse(iterator(), media_type="text/plain", headers=headers)

