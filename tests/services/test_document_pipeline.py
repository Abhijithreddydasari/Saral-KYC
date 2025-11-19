"""Tests for document pipeline telemetry enrichments."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.models.enums import DocumentType
from app.services.document_pipeline import DocumentPipeline
from app.services.ml_clients import MLClientRegistry, StageOutput


class _StubVision:
    def parse(self, file_path: Path) -> StageOutput:
        return StageOutput(payload={"vision_parser": "नाम परीक्षण"}, confidence=0.9, metadata={"stage": "vision"})


class _StubOCR:
    def read_text(self, file_path: Path) -> StageOutput:
        return StageOutput(payload={"text": "John Doe"}, confidence=0.8, metadata={"stage": "ocr"})


class _StubEmbeddings:
    def compare(self, source: str, target: str) -> StageOutput:
        return StageOutput(payload={"match": True, "similarity": 0.95}, confidence=0.95, metadata={"stage": "embeddings"})


class _StubForgery:
    def analyze(self, file_path: Path, doc_type: DocumentType) -> StageOutput:
        return StageOutput(
            payload={"authenticity": 0.9, "liveness": 0.8},
            confidence=0.9,
            metadata={"stage": "cv_forgery"},
        )


@pytest.fixture()
def patched_settings(tmp_path) -> SimpleNamespace:
    settings = SimpleNamespace(
        doc_stage_weight_vision=0.35,
        doc_stage_weight_ocr=0.35,
        doc_stage_weight_forgery=0.2,
        doc_stage_weight_crossdoc=0.1,
        doc_similarity_threshold=0.7,
        doc_metadata_max_drift_minutes=0,
        doc_language_mismatch_penalty=0.2,
        doc_layout_anomaly_threshold=0.9,
        doc_entity_overlap_threshold=0.8,
    )
    return settings


def test_document_pipeline_emits_metadata_and_language_signals(monkeypatch, tmp_path, patched_settings):
    monkeypatch.setattr("app.services.document_pipeline.get_settings", lambda: patched_settings)

    clients = MLClientRegistry(
        vision=_StubVision(),
        ocr=_StubOCR(),
        embeddings=_StubEmbeddings(),
        forgery=_StubForgery(),
    )
    pipeline = DocumentPipeline(clients=clients)

    def fake_ner(self: DocumentPipeline, text: str, stage_outputs):
        self._record_stage(
            stage_outputs,
            "ner",
            StageOutput(payload={"entity_count": 1}, confidence=0.8, metadata={"stage": "ner", "status": "ok"}),
        )
        return {"raw_text": text, "NAME": ["John Doe"]}

    monkeypatch.setattr(DocumentPipeline, "_run_spacy_ner", fake_ner)  # type: ignore[method-assign]

    img_path = tmp_path / "doc.png"
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(img_path)

    insights = pipeline._analyze_file(img_path, DocumentType.PAN, {"NAME": ["Jane"]})

    trace = insights.model_trace
    assert "metadata" in trace["stages"]
    assert "language" in trace["stages"]
    assert "entity_overlap" in trace["stages"]
    assert trace["ensemble"]["language_consistency"] == pytest.approx(0.8, rel=1e-3)
    assert "language_mismatch" in insights.anomaly_flags
    assert "entity_overlap_low" in insights.anomaly_flags
    assert trace["stage_scores"]["ocr"] < 1

