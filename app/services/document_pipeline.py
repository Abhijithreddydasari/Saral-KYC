"""Document intelligence pipeline coordinating multiple AI stages."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile

from app.core.config import get_settings
from app.models.application import DocumentArtifact, KycApplication
from app.models.enums import DocumentStatus, DocumentType
from app.services.ml_clients import MLClientRegistry, NERClient, StageOutput
from app.services.storage import LocalBlobStorage

logger = logging.getLogger(__name__)


@dataclass
class DocumentInsights:
    extracted_entities: Dict[str, Any]
    authenticity_score: float
    liveness_score: Optional[float]
    anomaly_flags: List[str]
    model_trace: Dict[str, Any]


class DocumentPipeline:
    """High-level orchestrator for doc intelligence stages."""

    def __init__(
        self,
        vision_model_name: str = "nielsr/donut-base-finetuned-docvqa",
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        ocr_languages: tuple[str, ...] = ("en", "hi"),
        clients: Optional[MLClientRegistry] = None,
    ) -> None:
        self.storage = LocalBlobStorage()
        self.vision_model_name = vision_model_name
        self.embedding_model_name = embedding_model_name
        self.ocr_languages = ocr_languages

        settings = get_settings()
        raw_mode = getattr(settings, "doc_pipeline_mode", "full") or "full"
        self.pipeline_mode = raw_mode.lower()
        self.mock_mode = self.pipeline_mode == "mock"
        self.stage_weights = self._normalize_weights(
            {
                "vision": settings.doc_stage_weight_vision,
                "ocr": settings.doc_stage_weight_ocr,
                "forgery": settings.doc_stage_weight_forgery,
                "crossdoc": settings.doc_stage_weight_crossdoc,
            }
        )
        self.crossdoc_threshold = settings.doc_similarity_threshold

        self.metadata_max_drift = settings.doc_metadata_max_drift_minutes
        self.language_penalty = settings.doc_language_mismatch_penalty
        self.layout_anomaly_threshold = settings.doc_layout_anomaly_threshold
        self.entity_overlap_threshold = settings.doc_entity_overlap_threshold
        self.enable_vision_stage = getattr(settings, "doc_enable_vision_stage", True)
        self.enable_ocr_stage = getattr(settings, "doc_enable_ocr_stage", True)
        self.enable_embeddings_stage = getattr(settings, "doc_enable_embeddings_stage", True)
        self.enable_metadata_stage = getattr(settings, "doc_enable_metadata_stage", True)
        self.embedding_min_chars = getattr(settings, "doc_embedding_min_chars", 80)
        self._language_patterns = {
            "hi": re.compile(r"[\u0900-\u097F]"),
            "bn": re.compile(r"[\u0980-\u09FF]"),
            "ta": re.compile(r"[\u0B80-\u0BFF]"),
            "te": re.compile(r"[\u0C00-\u0C7F]"),
        }

        self.clients = clients or MLClientRegistry.default(
            vision_model_name=vision_model_name,
            embedding_model_name=embedding_model_name,
            ocr_languages=ocr_languages,
            embedding_threshold=self.crossdoc_threshold,
        )
        if self.clients.ner is None:
            self.clients.ner = NERClient()

    async def ingest_and_analyze(
        self,
        application: KycApplication,
        doc: DocumentArtifact,
        file: UploadFile,
    ) -> DocumentArtifact:
        saved_path = self.store_document_file(application, doc, file)
        doc.status = DocumentStatus.PROCESSING

        logger.info(
            "Document ingestion started app_id=%s doc_id=%s doc_type=%s mode=%s",
            application.id,
            doc.id,
            doc.doc_type.value,
            self.pipeline_mode,
        )

        insights = await self._run_full_analysis(saved_path, doc, application)

        self._apply_insights(doc, insights)

        logger.info(
            "Document ingestion finished doc_id=%s status=%s authenticity=%.2f anomalies=%s",
            doc.id,
            doc.status.value,
            doc.authenticity_score or 0.0,
            ",".join(doc.anomaly_flags or []) or "none",
        )
        return doc

    def analyze_stored_document(self, application: KycApplication, doc: DocumentArtifact) -> DocumentArtifact:
        if not doc.storage_path:
            raise ValueError("Document storage path missing; cannot analyze.")

        insights = self._analyze_file(
            Path(doc.storage_path),
            doc.doc_type,
            self._historical_entities(application),
        )
        self._apply_insights(doc, insights)
        return doc

    def store_document_file(self, application: KycApplication, doc: DocumentArtifact, file: UploadFile) -> Path:
        relative_path = f"{application.reference_id}/{doc.doc_type.value}/{doc.id}_{file.filename}"
        saved_path = self.storage.save_upload(file, relative_path)
        doc.storage_path = str(saved_path)
        return saved_path

    def _apply_insights(self, doc: DocumentArtifact, insights: DocumentInsights) -> None:
        doc.extraction_payload = insights.extracted_entities
        doc.authenticity_score = insights.authenticity_score
        doc.liveness_score = insights.liveness_score
        doc.anomaly_flags = insights.anomaly_flags
        doc.model_trace = insights.model_trace
        doc.status = DocumentStatus.PROCESSED

    def _analyze_file(
        self,
        file_path: Path,
        doc_type: DocumentType,
        historical_entities: Optional[Dict[str, Any]],
    ) -> DocumentInsights:
        stage_outputs: Dict[str, StageOutput] = {}
        vision_result: Dict[str, Any] = {}
        if self.enable_vision_stage:
            vision_result = self._run_vision_transformer(file_path, stage_outputs)
        else:
            self._record_stage(
                stage_outputs,
                "vision",
                StageOutput(payload={}, metadata={"stage": "vision_transformer", "status": "skipped"}, confidence=None, retryable=False),
            )

        ocr_entities: Dict[str, Any] = {}
        ocr_text = ""
        if self.enable_ocr_stage:
            ocr_entities, ocr_text = self._run_ocr_ner(file_path, stage_outputs)
        else:
            self._record_stage(
                stage_outputs,
                "ocr",
                StageOutput(payload={"text": ""}, metadata={"stage": "ocr", "status": "skipped"}, confidence=None, retryable=False),
            )

        forgery, liveness = self._run_forgery_and_liveness(file_path, doc_type, stage_outputs)

        should_run_embeddings = self.enable_embeddings_stage and self._should_run_embeddings(stage_outputs.get("ocr"))
        if should_run_embeddings:
            cross_doc_flags = self._cross_document_validation(ocr_entities, historical_entities, stage_outputs)
        else:
            cross_doc_flags = []
            self._record_stage(
                stage_outputs,
                "embedding",
                StageOutput(
                    payload={"match": True},
                    metadata={"stage": "embeddings", "status": "skipped"},
                    confidence=None,
                    retryable=False,
                ),
            )

        if self.enable_metadata_stage:
            metadata_flags, metadata_signal = self._metadata_cross_checks(file_path, stage_outputs)
            layout_signal = self._layout_anomaly_score(file_path, stage_outputs)
            language_signal = self._language_consistency_signal(vision_result, ocr_entities, stage_outputs)
            overlap_signal = self._entity_overlap_signal(vision_result, ocr_entities, stage_outputs)
        else:
            metadata_flags, metadata_signal = [], 0.8
            layout_signal = language_signal = overlap_signal = 0.8
            self._record_stage(
                stage_outputs,
                "metadata",
                StageOutput(
                    payload={"flags": []},
                    metadata={"stage": "metadata", "status": "skipped"},
                    confidence=metadata_signal,
                    retryable=False,
                ),
            )

        extracted_entities = {**vision_result, **ocr_entities}
        stage_scores = self._compute_stage_scores(
            stage_outputs,
            forgery_score=forgery,
            historical_entities=historical_entities,
            cross_doc_flags=cross_doc_flags,
            ocr_entities=ocr_entities,
            metadata_signal=metadata_signal,
            layout_signal=layout_signal,
            language_signal=language_signal,
            overlap_signal=overlap_signal,
        )
        authenticity_score = self._weighted_score(stage_scores)
        stage_metrics = self._stage_metrics(stage_outputs)
        anomaly_flags = self._collect_anomalies(stage_outputs, cross_doc_flags, metadata_flags)
        self._log_stage_metrics(stage_outputs)

        return DocumentInsights(
            extracted_entities=extracted_entities,
            authenticity_score=authenticity_score,
            liveness_score=liveness,
            anomaly_flags=anomaly_flags,
            model_trace={
                "vision_model": self.vision_model_name,
                "embedding_model": self.embedding_model_name,
                "ocr_langs": self.ocr_languages,
                "stage_weights": self.stage_weights,
                "stage_scores": stage_scores,
                "ensemble": {
                    "language_consistency": round(language_signal, 3),
                    "entity_overlap": round(overlap_signal, 3),
                    "layout_score": round(layout_signal, 3),
                    "metadata_signal": round(metadata_signal, 3),
                },
                "stages": stage_metrics,
            },
        )

    def _mock_insights(self, file_path: Path, doc_type: DocumentType) -> DocumentInsights:
        """Return deterministic mock insights for fast local testing."""
        seed = int(hashlib.sha1(f"{doc_type.value}:{file_path}".encode("utf-8")).hexdigest(), 16)
        base_score = 0.65 + ((seed % 30) / 100)
        authenticity_score = round(min(0.95, base_score), 2)
        liveness_score = round(0.7 + ((seed >> 8) % 20) / 100, 2) if doc_type == DocumentType.SELFIE else None
        anomaly_flags: List[str] = []
        if seed % 11 == 0:
            anomaly_flags.append("mock_timestamp_drift")
        stage_scores = {
            "vision": min(1.0, authenticity_score + 0.05),
            "ocr": max(0.4, authenticity_score - 0.1),
            "forgery": authenticity_score,
            "crossdoc": 0.8,
        }
        extraction_payload = {
            "document_type": doc_type.value,
            "file_name": file_path.name,
            "reference_number": f"MOCK-{seed % 100000:05d}",
            "file_size_bytes": file_path.stat().st_size if file_path.exists() else 0,
        }
        logger.info(
            "Mock pipeline returning synthetic insights doc_type=%s seed=%s authenticity=%.2f",
            doc_type.value,
            seed & 0xFFFFFFFF,
            authenticity_score,
        )
        return DocumentInsights(
            extracted_entities=extraction_payload,
            authenticity_score=authenticity_score,
            liveness_score=liveness_score,
            anomaly_flags=anomaly_flags,
            model_trace={
                "mode": "mock",
                "reason": "doc_pipeline_mode=mock",
                "stage_scores": stage_scores,
                "seed": seed & 0xFFFFFFFF,
            },
        )

    def _historical_entities(self, application: KycApplication) -> Optional[Dict[str, Any]]:
        aggregated: Dict[str, Any] = {}
        for artifact in application.documents or []:
            if artifact.extraction_payload:
                aggregated.update(artifact.extraction_payload)
        return aggregated or None

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        total = sum(weights.values()) or 1.0
        return {key: value / total for key, value in weights.items()}

    def _record_stage(self, stage_outputs: Dict[str, StageOutput], stage: str, output: StageOutput) -> None:
        stage_outputs[stage] = output

    def _should_run_embeddings(self, ocr_stage: Optional[StageOutput]) -> bool:
        if not ocr_stage:
            return True
        text = ocr_stage.payload.get("text") if isinstance(ocr_stage.payload, dict) else ""
        text_len = len(text or "")
        confidence = ocr_stage.confidence or 0.0
        return confidence < 0.6 or text_len < self.embedding_min_chars

    def _log_stage_metrics(self, stage_outputs: Dict[str, StageOutput]) -> None:
        if not logger.isEnabledFor(logging.DEBUG):
            return
        summary = {
            name: {
                "latency_ms": output.latency_ms,
                "status": output.metadata.get("status") if output.metadata else None,
            }
            for name, output in stage_outputs.items()
        }
        logger.debug("Document stage metrics: %s", summary)

    def _run_vision_transformer(self, file_path: Path, stage_outputs: Dict[str, StageOutput]) -> Dict[str, Any]:
        output = self.clients.vision.parse(file_path)
        self._record_stage(stage_outputs, "vision", output)
        return output.payload

    def _run_ocr_ner(self, file_path: Path, stage_outputs: Dict[str, StageOutput]) -> Tuple[Dict[str, Any], str]:
        ocr_output = self._perform_easyocr(file_path, stage_outputs)
        text = ""
        if isinstance(ocr_output, StageOutput):
            if isinstance(ocr_output.payload, dict):
                text = ocr_output.payload.get("text", "")
        else:
            text = str(ocr_output or "")
        entities = self._run_ner_client(text, stage_outputs)
        return entities, text

    def _perform_easyocr(self, file_path: Path, stage_outputs: Dict[str, StageOutput]) -> str:
        output = self.clients.ocr.read_text(file_path)
        self._record_stage(stage_outputs, "ocr", output)
        return output.payload.get("text", "")

    def _run_ner_client(self, text: str, stage_outputs: Dict[str, StageOutput]) -> Dict[str, Any]:
        return self._run_spacy_ner(text, stage_outputs)

    def _run_spacy_ner(self, text: str, stage_outputs: Dict[str, StageOutput]) -> Dict[str, Any]:
        """Backward-compatible hook for tests that patch the old method name."""
        output = self.clients.ner.extract_entities(text)
        self._record_stage(stage_outputs, "ner", output)
        return output.payload.get("entities", {})

    def _run_forgery_and_liveness(
        self,
        file_path: Path,
        doc_type: DocumentType,
        stage_outputs: Dict[str, StageOutput],
    ) -> tuple[float, Optional[float]]:
        output = self.clients.forgery.analyze(file_path, doc_type)
        self._record_stage(stage_outputs, "forgery", output)
        authenticity = output.payload.get("authenticity", 0.5)
        liveness = output.payload.get("liveness") if doc_type == DocumentType.SELFIE else None
        return authenticity, liveness

    def _cross_document_validation(
        self,
        current_entities: Dict[str, Any],
        historical_entities: Optional[Dict[str, Any]],
        stage_outputs: Dict[str, StageOutput],
    ) -> List[str]:
        if not current_entities or not historical_entities:
            self._record_stage(
                stage_outputs,
                "embedding",
                StageOutput(
                    payload={"similarity": None, "match": True},
                    confidence=0.75,
                    metadata={"stage": "embeddings", "status": "no_context"},
                ),
            )
            return []

        embeddings_ok = self._compare_embeddings(current_entities, historical_entities, stage_outputs)
        flags: List[str] = []
        if not embeddings_ok:
            flags.append("entity_mismatch")
        return flags

    def _compare_embeddings(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any],
        stage_outputs: Dict[str, StageOutput],
    ) -> bool:
        def flatten(d: Dict[str, Any]) -> str:
            return " ".join(f"{k}:{','.join(v) if isinstance(v, list) else v}" for k, v in d.items())

        source_flat = flatten(source)
        target_flat = flatten(target)
        output = self.clients.embeddings.compare(source_flat, target_flat)
        self._record_stage(stage_outputs, "embedding", output)
        if output.error and output.payload.get("match") is None:
            return bool(set(source.items()) & set(target.items()))
        return bool(output.payload.get("match", True))

    def _metadata_cross_checks(
        self,
        file_path: Path,
        stage_outputs: Dict[str, StageOutput],
    ) -> tuple[List[str], float]:
        metadata = {"stage": "metadata"}
        payload: Dict[str, Any] = {}
        flags: List[str] = []
        status = "ok"
        error_text: Optional[str] = None
        retryable = True
        score = 0.85

        try:
            stat = file_path.stat()
            file_ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            drift_min = abs((datetime.now(timezone.utc) - file_ts).total_seconds()) / 60
            payload["timestamp_drift_min"] = round(drift_min, 2)
            if drift_min > self.metadata_max_drift:
                flags.append("timestamp_drift")
                score -= 0.25
        except OSError as exc:
            status = "stat_error"
            error_text = str(exc)
            retryable = False
            score = 0.5
            flags.append("metadata_unavailable")

        if status == "ok":
            try:
                from PIL import ExifTags, Image
            except ImportError:
                status = "skipped"
                error_text = "metadata_unavailable"
                retryable = False
            else:
                try:
                    image = Image.open(file_path)
                    exif_raw = image._getexif() or {}
                    mapped = {ExifTags.TAGS.get(tag, str(tag)): value for tag, value in exif_raw.items()}
                    device_fingerprint = "|".join(
                        str(mapped.get(field)) for field in ("Model", "Make", "Software") if mapped.get(field)
                    )
                    if device_fingerprint:
                        payload["device_hash"] = hashlib.sha1(device_fingerprint.encode("utf-8")).hexdigest()
                    capture_time = mapped.get("DateTimeOriginal") or mapped.get("DateTime")
                    if capture_time:
                        payload["capture_time"] = str(capture_time)
                except Exception as exc:  # pragma: no cover
                    status = "metadata_error"
                    error_text = str(exc)
                    retryable = False

        payload["flags"] = flags
        confidence = max(0.1, min(1.0, score))
        self._record_stage(
            stage_outputs,
            "metadata",
            StageOutput(
                payload=payload,
                confidence=confidence,
                metadata={**metadata, "status": status, "flags": flags},
                error=error_text,
                retryable=retryable,
            ),
        )
        return flags, confidence

    def _layout_anomaly_score(self, file_path: Path, stage_outputs: Dict[str, StageOutput]) -> float:
        metadata = {"stage": "layout"}
        flags: List[str] = []
        status = "ok"
        error_text: Optional[str] = None
        retryable = True
        aspect_ratio = None
        texture_score = 0.6
        final_score = 0.7

        try:
            from PIL import Image
        except ImportError:
            status = "skipped"
            error_text = "layout_unavailable"
            retryable = False
            final_score = 0.6
        else:
            try:
                image = Image.open(file_path)
                width, height = image.size
                aspect_ratio = round(width / max(1, height), 3)
                histogram = image.convert("L").histogram()
                total = sum(histogram) or 1
                mean_val = sum(i * count for i, count in enumerate(histogram)) / total
                variance = sum(((i - mean_val) ** 2) * count for i, count in enumerate(histogram)) / total
                texture_score = max(0.05, min(1.0, variance / 2000))
                final_score = max(0.05, min(1.0, texture_score))
                if final_score < self.layout_anomaly_threshold:
                    flags.append("layout_anomaly")
            except Exception as exc:  # pragma: no cover
                status = "layout_error"
                error_text = str(exc)
                retryable = False
                final_score = 0.6

        payload = {
            "aspect_ratio": aspect_ratio,
            "texture_score": round(texture_score, 3),
            "flags": flags,
        }
        self._record_stage(
            stage_outputs,
            "layout",
            StageOutput(
                payload=payload,
                confidence=final_score,
                metadata={**metadata, "status": status, "flags": flags},
                error=error_text,
                retryable=retryable,
            ),
        )
        return final_score

    def _language_consistency_signal(
        self,
        vision_payload: Dict[str, Any],
        ocr_entities: Dict[str, Any],
        stage_outputs: Dict[str, StageOutput],
    ) -> float:
        metadata = {"stage": "language"}
        vision_text = self._vision_text(vision_payload)
        ocr_text = self._ocr_text(ocr_entities)
        vision_lang = self._language_hint(vision_text)
        ocr_lang = self._language_hint(ocr_text)
        consistent = vision_lang == ocr_lang or "unknown" in (vision_lang, ocr_lang)
        score = 1.0 if consistent else max(0.1, 1.0 - self.language_penalty)
        flags = [] if consistent else ["language_mismatch"]
        self._record_stage(
            stage_outputs,
            "language",
            StageOutput(
                payload={"vision_lang": vision_lang, "ocr_lang": ocr_lang},
                confidence=score,
                metadata={**metadata, "vision_lang": vision_lang, "ocr_lang": ocr_lang, "flags": flags},
            ),
        )
        return score

    def _entity_overlap_signal(
        self,
        vision_payload: Dict[str, Any],
        ocr_entities: Dict[str, Any],
        stage_outputs: Dict[str, StageOutput],
    ) -> float:
        metadata = {"stage": "entity_overlap"}
        vision_text = self._vision_text(vision_payload).lower()
        entity_tokens = [value.lower() for value in self._entity_values(ocr_entities)]
        total = len(entity_tokens)
        matches = sum(1 for token in entity_tokens if token and token in vision_text)
        ratio = matches / total if total else 1.0
        score = max(0.1, min(1.0, ratio))
        flags = []
        if total and ratio < self.entity_overlap_threshold:
            flags.append("entity_overlap_low")
        self._record_stage(
            stage_outputs,
            "entity_overlap",
            StageOutput(
                payload={
                    "entity_matches": matches,
                    "entity_total": total,
                    "ratio": round(ratio, 3),
                },
                confidence=score,
                metadata={**metadata, "flags": flags, "status": "ok" if not flags else "low_overlap"},
            ),
        )
        return score

    def _vision_text(self, payload: Dict[str, Any]) -> str:
        if not payload:
            return ""
        if isinstance(payload.get("vision_parser"), str):
            return payload["vision_parser"]
        return " ".join(str(value) for value in payload.values() if isinstance(value, str))

    def _ocr_text(self, entities: Dict[str, Any]) -> str:
        if not entities:
            return ""
        if isinstance(entities.get("raw_text"), str):
            return entities["raw_text"]
        return " ".join(self._entity_values(entities))

    def _entity_values(self, entities: Dict[str, Any]) -> List[str]:
        tokens: List[str] = []
        for value in entities.values():
            if isinstance(value, list):
                tokens.extend(str(item) for item in value)
        return tokens

    def _language_hint(self, text: str) -> str:
        if not text:
            return "unknown"
        for code, pattern in self._language_patterns.items():
            if pattern.search(text):
                return code
        if re.search(r"[A-Za-z]", text):
            return "en"
        return "unknown"

    def _stage_confidence(self, output: Optional[StageOutput], default: float) -> float:
        if not output:
            return default
        if output.confidence is None:
            return default
        return max(0.0, min(1.0, output.confidence))

    def _ocr_signal(self, stage_outputs: Dict[str, StageOutput], entities: Dict[str, Any]) -> float:
        ocr_conf = self._stage_confidence(stage_outputs.get("ocr"), 0.4)
        ner_output = stage_outputs.get("ner")
        ner_conf = self._stage_confidence(ner_output, 0.4)
        if entities:
            entity_count = sum(len(values) for values in entities.values() if isinstance(values, list))
            if entity_count:
                ner_conf = max(ner_conf, min(1.0, entity_count / 5))
        return (ocr_conf + ner_conf) / 2

    def _crossdoc_signal(
        self,
        stage_outputs: Dict[str, StageOutput],
        historical_entities: Optional[Dict[str, Any]],
        cross_doc_flags: List[str],
    ) -> float:
        if not historical_entities:
            return 0.75
        embedding_output = stage_outputs.get("embedding")
        if not embedding_output:
            return 0.3 if cross_doc_flags else 0.8
        if cross_doc_flags:
            return min(0.3, self._stage_confidence(embedding_output, 0.3))
        return self._stage_confidence(embedding_output, 0.8)

    def _compute_stage_scores(
        self,
        stage_outputs: Dict[str, StageOutput],
        forgery_score: float,
        historical_entities: Optional[Dict[str, Any]],
        cross_doc_flags: List[str],
        ocr_entities: Dict[str, Any],
        metadata_signal: float,
        layout_signal: float,
        language_signal: float,
        overlap_signal: float,
    ) -> Dict[str, float]:
        vision_score = self._stage_confidence(stage_outputs.get("vision"), 0.4)
        ocr_score = self._ocr_signal(stage_outputs, ocr_entities)
        forgery_normalized = max(0.0, min(1.0, forgery_score))
        crossdoc_score = self._crossdoc_signal(stage_outputs, historical_entities, cross_doc_flags)
        blended_vision = (0.7 * vision_score) + (0.3 * layout_signal)
        blended_ocr = (0.6 * ocr_score) + (0.2 * language_signal) + (0.2 * overlap_signal)
        blended_forgery = (0.8 * forgery_normalized) + (0.2 * metadata_signal)
        return {
            "vision": max(0.0, min(1.0, blended_vision)),
            "ocr": max(0.0, min(1.0, blended_ocr)),
            "forgery": max(0.0, min(1.0, blended_forgery)),
            "crossdoc": crossdoc_score,
        }

    def _weighted_score(self, stage_scores: Dict[str, float]) -> float:
        combined = sum(self.stage_weights.get(name, 0.0) * stage_scores.get(name, 0.0) for name in self.stage_weights)
        return max(0.0, min(1.0, combined))

    def _collect_anomalies(
        self,
        stage_outputs: Dict[str, StageOutput],
        cross_doc_flags: List[str],
        extra_flags: Optional[List[str]] = None,
    ) -> List[str]:
        flags = list(cross_doc_flags)
        if extra_flags:
            flags.extend(extra_flags)
        for name, output in stage_outputs.items():
            if output.error:
                flags.append(f"{name}_error")
            elif output.confidence is not None and output.confidence < 0.3:
                flags.append(f"{name}_low_conf")
            stage_flag_payload = (output.metadata or {}).get("flags")
            if stage_flag_payload:
                flags.extend(stage_flag_payload)
        # deduplicate while maintaining order
        seen = set()
        ordered: List[str] = []
        for flag in flags:
            if flag in seen:
                continue
            seen.add(flag)
            ordered.append(flag)
        return ordered

    def _stage_metrics(self, stage_outputs: Dict[str, StageOutput]) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        for name, output in stage_outputs.items():
            metrics[name] = {
                "confidence": output.confidence,
                "latency_ms": output.latency_ms,
                "metadata": output.metadata,
                "error": output.error,
                "payload_preview": self._safe_payload_snapshot(output.payload),
            }
        return metrics

    def _safe_payload_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str):
                snapshot[key] = value[:64]
            elif isinstance(value, list):
                snapshot[key] = len(value)
            elif isinstance(value, dict):
                snapshot[key] = list(value.keys())[:5]
            else:
                snapshot[key] = value
        return snapshot
