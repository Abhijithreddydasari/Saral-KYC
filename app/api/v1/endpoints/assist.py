"""Conversational assistant endpoints."""

from __future__ import annotations

from __future__ import annotations

import asyncio
from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.api.deps.db import get_db
from app.models.application import KycApplication
from app.models.audit import AuditAction
from app.models.workflow import ConversationRole, ConversationTurn
from app.schemas.chat import AssistantBootstrapResponse, ChatMessageRequest, ChatMessageResponse
from app.services.audit import AuditLogger
from app.services.conversational import ConversationalAgent

router = APIRouter(prefix="/assist", tags=["assistant"])
agent = ConversationalAgent()
audit_logger = AuditLogger()


def _resolve_application_context(
    payload: ChatMessageRequest,
    session: Session,
) -> Tuple[KycApplication | None, dict]:
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
    return application, context


def _persist_conversation_turns(
    session: Session,
    application: KycApplication | None,
    payload: ChatMessageRequest,
    reply: str,
    language: str,
) -> None:
    user_turn = ConversationTurn(
        application_id=application.id if application else None,
        role=ConversationRole.USER,
        language=language,
        message=payload.message,
    )
    assistant_turn = ConversationTurn(
        application_id=application.id if application else None,
        role=ConversationRole.ASSISTANT,
        language=language,
        message=reply,
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


def _build_chat_response(payload: ChatMessageRequest, session: Session) -> ChatMessageResponse:
    application, context = _resolve_application_context(payload, session)
    result = agent.respond(payload.message, context)
    reply = result.reply
    _persist_conversation_turns(session, application, payload, reply, result.language)
    return ChatMessageResponse(
        reply=reply,
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


@router.post("/chat", response_model=ChatMessageResponse)
def chat(payload: ChatMessageRequest, session: Session = Depends(get_db)) -> ChatMessageResponse:
    return _build_chat_response(payload, session)


@router.post("/chat/stream")
async def chat_stream(payload: ChatMessageRequest, session: Session = Depends(get_db)) -> StreamingResponse:
    response = _build_chat_response(payload, session)
    chunks = _chunk_reply(response.reply)

    async def iterator():
        for chunk in chunks:
            yield chunk
            await asyncio.sleep(0.1)

    headers = {"X-Assistant-Language": response.language}
    return StreamingResponse(iterator(), media_type="text/plain", headers=headers)

