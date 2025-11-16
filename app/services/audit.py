"""Audit logging helpers."""

from __future__ import annotations

from typing import Any, Dict

from sqlmodel import Session

from app.models.audit import AuditAction, AuditEvent


class AuditLogger:
    """Persists audit events for compliance traceability."""

    def record(
        self,
        session: Session,
        action: AuditAction,
        entity_type: str,
        entity_id: str,
        payload: Dict[str, Any] | None = None,
        actor: str = "system",
    ) -> AuditEvent:
        event = AuditEvent(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            actor=actor,
        )
        session.add(event)
        return event

