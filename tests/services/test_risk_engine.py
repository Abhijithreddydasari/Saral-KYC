"""Tests for the risk engine feature vector enrichments."""

from __future__ import annotations

import pytest

from app.models.application import DocumentArtifact, KycApplication
from app.models.enums import DocumentStatus, DocumentType
from app.services.risk_engine import FeatureVector, RiskEngine


def _artifact(**kwargs) -> DocumentArtifact:
    defaults = {
        "application_id": 1,
        "doc_type": DocumentType.PAN,
        "status": DocumentStatus.PROCESSED,
        "authenticity_score": 0.85,
        "liveness_score": 0.4,
        "anomaly_flags": ["language_mismatch", "timestamp_drift"],
        "model_trace": {
            "stage_scores": {"vision": 0.8, "ocr": 0.7, "forgery": 0.6, "crossdoc": 0.9},
            "ensemble": {"metadata_signal": 0.4, "language_consistency": 0.3},
        },
    }
    defaults.update(kwargs)
    return DocumentArtifact(**defaults)


def test_feature_vector_aggregates_penalties_and_ensemble():
    doc = _artifact()
    vector = FeatureVector.from_documents([doc])
    assert vector.language_penalty > 0
    assert vector.metadata_penalty > 0
    assert vector.flag_counter["language_mismatch"] == 1
    assert vector.ensemble_averages["metadata_signal"] == pytest.approx(0.4)


def test_risk_engine_explanation_contains_new_fields():
    application = KycApplication(full_name="Test User", email="test@example.com", preferred_language="en")
    doc = _artifact()
    engine = RiskEngine()

    assessment = engine.assess(application, [doc], customer_statement="I have an issue")

    factor_ids = {factor["id"] for factor in assessment.explanation["factors"]}
    assert "metadata_integrity" in factor_ids
    assert "language_consistency" in factor_ids
    assert assessment.explanation["ensemble"]["metadata_signal"] == pytest.approx(0.4)
    assert assessment.fairness_report["flag_counts"]["language_mismatch"] == 1
    assert assessment.fairness_report["penalties"]["language"] > 0

