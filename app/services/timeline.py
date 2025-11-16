"""Builds timeline views for KYC applications."""

from __future__ import annotations

from typing import List

from app.models.application import KycApplication
from app.models.risk import RiskDecision
from app.models.workflow import NotificationEvent, ReviewTask
from app.schemas.workflow import ApplicationTimeline, TimelineEntry


class TimelineBuilder:
    def build(self, application: KycApplication) -> ApplicationTimeline:
        entries: List[TimelineEntry] = []

        for doc in sorted(application.documents or [], key=lambda d: d.created_at):
            entries.append(
                TimelineEntry(
                    event_type="document",
                    message=f"{doc.doc_type.value} -> {doc.status.value}",
                    created_at=doc.created_at,
                    payload={
                        "authenticity": doc.authenticity_score,
                        "anomalies": doc.anomaly_flags,
                    },
                )
            )

        for decision in sorted(application.risk_decisions or [], key=lambda d: d.created_at):
            entries.append(
                TimelineEntry(
                    event_type="risk_decision",
                    message=f"Risk band: {decision.risk_band}",
                    created_at=decision.created_at,
                    payload={"score": decision.risk_score},
                )
            )

        for review in sorted(application.review_tasks or [], key=lambda r: r.created_at):
            entries.append(
                TimelineEntry(
                    event_type="review",
                    message=f"Review {review.status.value} ({review.issue_type})",
                    created_at=review.created_at,
                    payload={"ai_summary": review.ai_summary},
                )
            )

        for note in sorted(application.notifications or [], key=lambda n: n.created_at):
            entries.append(
                TimelineEntry(
                    event_type="notification",
                    message=f"Nudge via {note.channel.value}",
                    created_at=note.created_at,
                    payload={"message": note.message},
                )
            )

        entries.sort(key=lambda e: e.created_at)
        return ApplicationTimeline(application_id=application.id, status=application.status.value, entries=entries)

