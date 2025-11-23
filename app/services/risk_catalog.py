"""Helpers for risk categories and canned explanation reasons."""

from __future__ import annotations

import hashlib
from typing import Dict, List, Tuple

RISK_REASON_LIBRARY: Dict[str, List[str]] = {
    "safe": [
        "All submitted documents exhibit consistent metadata and layout.",
        "No adverse watchlists or fraud indicators were detected for this applicant.",
        "Biographic data matches across the ledger and historical submissions.",
    ],
    "medium": [
        "One or more documents showed moderate quality or metadata drift.",
        "Further verification is recommended for the declared address and identity information.",
        "Limited historical data requires additional manual review before approval.",
    ],
    "high": [
        "Document forensics flagged significant anomalies requiring escalation.",
        "Applicant details overlap with high-risk entities within the network graph.",
        "Liveness or biometric confidence fell below the safe operating threshold.",
    ],
}


def derive_risk_category(score: float | None, reference_id: str) -> Tuple[str, float]:
    """Return a (category, normalized_score) tuple based on stored score or deterministic hash."""
    if score is not None:
        normalized = max(0.0, min(1.0, score))
    else:
        seed = int(hashlib.sha1(reference_id.encode("utf-8")).hexdigest(), 16)
        normalized = ((seed % 100) / 100) or 0.5

    if normalized < 0.33:
        category = "safe"
    elif normalized < 0.66:
        category = "medium"
    else:
        category = "high"
    return category, normalized


def risk_reasons_for(category: str) -> List[str]:
    """Return canned reasons for the provided risk bucket."""
    return RISK_REASON_LIBRARY.get(category, RISK_REASON_LIBRARY["medium"])

