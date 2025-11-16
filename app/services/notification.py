"""Notification + nudge service."""

from __future__ import annotations

import logging
from datetime import datetime

from app.models.workflow import NotificationChannel

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends contextual nudges via configured channels."""

    def __init__(self) -> None:
        self.sent_events: list[dict] = []

    def send(self, channel: NotificationChannel, target: str | None, message: str, metadata: dict | None = None) -> None:
        payload = {
            "channel": channel.value,
            "target": target,
            "message": message,
            "metadata": metadata or {},
            "sent_at": datetime.utcnow().isoformat(),
        }
        self.sent_events.append(payload)
        logger.info("Dispatching notification", extra=payload)

