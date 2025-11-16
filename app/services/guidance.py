"""Guidance + escalation summarization helpers."""

from __future__ import annotations

from typing import List

from app.models.application import DocumentArtifact


class GuidanceEngine:
    """Produces contextual nudges + escalation summaries."""

    def build_escalation_summary(self, documents: List[DocumentArtifact]) -> str:
        pending = [doc for doc in documents if not doc.extraction_payload]
        anomalies = [doc for doc in documents if doc.anomaly_flags]

        parts: List[str] = []
        if pending:
            pending_types = ", ".join(doc.doc_type.value for doc in pending)
            parts.append(f"Missing extraction for: {pending_types}")
        if anomalies:
            anomaly_types = ", ".join(doc.doc_type.value for doc in anomalies)
            parts.append(f"Anomalies detected in: {anomaly_types}")

        return "; ".join(parts) or "Escalated for manual verification"

