"""Conversational assistant endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps.db import get_db
from app.models.application import KycApplication
from app.models.audit import AuditAction
from app.models.workflow import ConversationRole, ConversationTurn
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.services.audit import AuditLogger
from app.services.conversational import ConversationalAgent

router = APIRouter(prefix="/assist", tags=["assistant"])
agent = ConversationalAgent()
audit_logger = AuditLogger()


@router.post("/chat", response_model=ChatMessageResponse)
def chat(payload: ChatMessageRequest, session: Session = Depends(get_db)) -> ChatMessageResponse:
    application = None
    context = {}
    if payload.application_reference_id:
        application = session.exec(
            select(KycApplication).where(KycApplication.reference_id == payload.application_reference_id)
        ).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found for reference ID")

        recent_nudges = [note.message for note in (application.notifications or [])][-3:]
        context = {"status": application.status.value, "nudges": recent_nudges}

    result = agent.respond(payload.message, context)

    user_turn = ConversationTurn(
        application_id=application.id if application else None,
        role=ConversationRole.USER,
        language=result.language,
        message=payload.message,
    )
    assistant_turn = ConversationTurn(
        application_id=application.id if application else None,
        role=ConversationRole.ASSISTANT,
        language=result.language,
        message=result.reply,
    )

    session.add(user_turn)
    session.add(assistant_turn)
    session.flush()

    audit_logger.record(
        session,
        AuditAction.CHAT_MESSAGE,
        "conversation_turn",
        str(user_turn.id),
        {"role": "user"},
        actor="customer",
    )
    audit_logger.record(
        session,
        AuditAction.CHAT_MESSAGE,
        "conversation_turn",
        str(assistant_turn.id),
        {"role": "assistant"},
        actor="assistant",
    )

    session.commit()

    return ChatMessageResponse(
        reply=result.reply,
        language=result.language,
        safety_passed=result.safety_passed,
        metadata=result.metadata,
    )

