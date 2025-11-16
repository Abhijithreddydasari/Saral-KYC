"""Document intelligence pipeline coordinating multiple AI stages."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import UploadFile

from app.models.application import DocumentArtifact, KycApplication
from app.models.enums import DocumentStatus, DocumentType
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
    ) -> None:
        self.storage = LocalBlobStorage()
        self.vision_model_name = vision_model_name
        self.embedding_model_name = embedding_model_name
        self.ocr_languages = ocr_languages

        self._vision_components: Optional[tuple[Any, Any]] = None
        self._sentence_model: Optional[Any] = None
        self._ocr_reader: Optional[Any] = None

    async def ingest_and_analyze(
        self,
        application: KycApplication,
        doc: DocumentArtifact,
        file: UploadFile,
    ) -> DocumentArtifact:
        relative_path = f"{application.reference_id}/{doc.doc_type.value}/{doc.id}_{file.filename}"
        saved_path = self.storage.save_upload(file, relative_path)

        doc.storage_path = str(saved_path)
        doc.status = DocumentStatus.PROCESSING

        loop = asyncio.get_running_loop()
        insights = await loop.run_in_executor(
            None,
            self._analyze_file,
            saved_path,
            doc.doc_type,
            self._historical_entities(application),
        )

        doc.extraction_payload = insights.extracted_entities
        doc.authenticity_score = insights.authenticity_score
        doc.liveness_score = insights.liveness_score
        doc.anomaly_flags = insights.anomaly_flags
        doc.model_trace = insights.model_trace
        doc.status = DocumentStatus.PROCESSED
        return doc

    def _analyze_file(
        self,
        file_path: Path,
        doc_type: DocumentType,
        historical_entities: Optional[Dict[str, Any]],
    ) -> DocumentInsights:
        vision_result = self._run_vision_transformer(file_path)
        ocr_entities = self._run_ocr_ner(file_path)
        forgery, liveness = self._run_forgery_and_liveness(file_path, doc_type)
        cross_doc_flags = self._cross_document_validation(ocr_entities, historical_entities)

        extracted_entities = {**vision_result, **ocr_entities}
        authenticity_score = (forgery + 0.1 * len(extracted_entities)) / (1 + len(extracted_entities))
        authenticity_score = max(0.0, min(1.0, authenticity_score))

        anomaly_flags = cross_doc_flags
        return DocumentInsights(
            extracted_entities=extracted_entities,
            authenticity_score=authenticity_score,
            liveness_score=liveness,
            anomaly_flags=anomaly_flags,
            model_trace={
                "vision_model": self.vision_model_name,
                "embedding_model": self.embedding_model_name,
                "ocr_langs": self.ocr_languages,
            },
        )

    def _historical_entities(self, application: KycApplication) -> Optional[Dict[str, Any]]:
        aggregated: Dict[str, Any] = {}
        for artifact in application.documents or []:
            if artifact.extraction_payload:
                aggregated.update(artifact.extraction_payload)
        return aggregated or None

    def _run_vision_transformer(self, file_path: Path) -> Dict[str, Any]:
        try:
            from PIL import Image
            from transformers import DonutProcessor, VisionEncoderDecoderModel
        except ImportError:
            logger.debug("Transformers/Pillow not installed; skipping VT extraction")
            return {}

        if self._vision_components is None:
            try:
                processor = DonutProcessor.from_pretrained(self.vision_model_name)
                model = VisionEncoderDecoderModel.from_pretrained(self.vision_model_name)
                self._vision_components = (processor, model)
            except Exception as exc:  # pragma: no cover - optional dependency
                logger.warning("Failed to load vision model: %s", exc)
                self._vision_components = (None, None)

        processor, model = self._vision_components
        if processor is None or model is None:
            return {}

        try:
            image = Image.open(file_path).convert("RGB")
            pixel_values = processor(image, return_tensors="pt").pixel_values
            output_ids = model.generate(pixel_values, max_length=512)
            raw = processor.batch_decode(output_ids, skip_special_tokens=True)[0]
            return {"vision_parser": raw}
        except Exception as exc:  # pragma: no cover - hardware/torch runtime
            logger.warning("Vision extraction error: %s", exc)
            return {}

    def _run_ocr_ner(self, file_path: Path) -> Dict[str, Any]:
        text = self._perform_easyocr(file_path)
        entities = self._run_spacy_ner(text)
        return entities

    def _perform_easyocr(self, file_path: Path) -> str:
        try:
            import easyocr
        except ImportError:
            logger.debug("easyocr not installed; skipping OCR")
            return ""

        if self._ocr_reader is None:
            try:
                self._ocr_reader = easyocr.Reader(list(self.ocr_languages))
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to initialize easyocr: %s", exc)
                self._ocr_reader = None

        if self._ocr_reader is None:
            return ""

        result = self._ocr_reader.readtext(str(file_path), detail=0)
        return " ".join(result)

    def _run_spacy_ner(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        try:
            import spacy
        except ImportError:
            logger.debug("spaCy not installed; returning plain text fallback")
            return {"raw_text": text[:512]}

        try:
            nlp = spacy.blank("en")
        except Exception as exc:  # pragma: no cover
            logger.warning("spaCy init failed: %s", exc)
            return {"raw_text": text[:512]}

        doc = nlp(text)
        entities: Dict[str, Any] = {"raw_text": text[:512]}
        for ent in doc.ents:
            entities.setdefault(ent.label_, []).append(ent.text)
        return entities

    def _run_forgery_and_liveness(self, file_path: Path, doc_type: DocumentType) -> tuple[float, Optional[float]]:
        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.debug("OpenCV/Numpy not installed; returning neutral authenticity")
            return 0.5, None

        img = cv2.imread(str(file_path))
        if img is None:
            return 0.5, None

        variance = float(cv2.Laplacian(img, cv2.CV_64F).var())
        authenticity = max(0.1, min(1.0, variance / 1000))
        liveness = None
        if doc_type == DocumentType.SELFIE:
            liveness = max(0.1, min(1.0, variance / 500))
        return authenticity, liveness

    def _cross_document_validation(
        self,
        current_entities: Dict[str, Any],
        historical_entities: Optional[Dict[str, Any]],
    ) -> List[str]:
        if not current_entities or not historical_entities:
            return []

        embeddings_ok = self._compare_embeddings(current_entities, historical_entities)
        flags: List[str] = []
        if not embeddings_ok:
            flags.append("entity_mismatch")
        return flags

    def _compare_embeddings(self, source: Dict[str, Any], target: Dict[str, Any]) -> bool:
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError:
            logger.debug("SentenceTransformer not installed; falling back to string comparison")
            return bool(set(source.items()) & set(target.items()))

        if self._sentence_model is None:
            try:
                self._sentence_model = SentenceTransformer(self.embedding_model_name)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to load sentence transformer: %s", exc)
                self._sentence_model = None

        if self._sentence_model is None:
            return bool(set(source.items()) & set(target.items()))

        def flatten(d: Dict[str, Any]) -> str:
            return " ".join(f"{k}:{','.join(v) if isinstance(v, list) else v}" for k, v in d.items())

        emb_a = self._sentence_model.encode(flatten(source), convert_to_tensor=True)
        emb_b = self._sentence_model.encode(flatten(target), convert_to_tensor=True)

        try:
            similarity = util.pytorch_cos_sim(emb_a, emb_b).item()
        except Exception as exc:  # pragma: no cover
            logger.warning("Embedding comparison failed: %s", exc)
            return True

        return similarity >= 0.6

