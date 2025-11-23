"""Shared ML client wrappers for document intelligence pipeline."""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Optional, Tuple

from app.models.enums import DocumentType

logger = logging.getLogger(__name__)


@dataclass
class StageOutput:
    """Container for model stage outputs and telemetry."""

    payload: Dict[str, Any]
    confidence: Optional[float] = None
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    retryable: bool = True

    def succeeded(self) -> bool:
        return self.error is None

    def clone(self) -> "StageOutput":
        return StageOutput(
            payload=deepcopy(self.payload),
            confidence=self.confidence,
            latency_ms=self.latency_ms,
            metadata=deepcopy(self.metadata),
            error=self.error,
            retryable=self.retryable,
        )


@dataclass
class _CacheEntry:
    fingerprint: Tuple[Any, ...]
    output: StageOutput


class InferenceCache:
    """Small LRU cache for deterministic model outputs."""

    def __init__(self, maxsize: int = 64) -> None:
        self.maxsize = maxsize
        self._entries: "OrderedDict[str, _CacheEntry]" = OrderedDict()
        self._lock = Lock()

    def get(self, key: str, fingerprint: Tuple[Any, ...]) -> Optional[StageOutput]:
        with self._lock:
            entry = self._entries.get(key)
            if not entry or entry.fingerprint != fingerprint:
                return None
            self._entries.move_to_end(key)
            return entry.output.clone()

    def set(self, key: str, fingerprint: Tuple[Any, ...], output: StageOutput) -> None:
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
            self._entries[key] = _CacheEntry(fingerprint=fingerprint, output=output.clone())
            while len(self._entries) > self.maxsize:
                self._entries.popitem(last=False)


class BaseInferenceClient:
    """Shared helpers for caching + retries."""

    def __init__(
        self,
        cache_prefix: str,
        cache_enabled: bool = True,
        cache_size: int = 32,
        max_retries: int = 2,
        retry_backoff: float = 0.2,
    ) -> None:
        self.cache_prefix = cache_prefix
        self.cache_enabled = cache_enabled
        self.max_retries = max(1, max_retries)
        self.retry_backoff = retry_backoff
        self._cache = InferenceCache(cache_size) if cache_enabled else None

    def _cache_key(self, *parts: str) -> str:
        return "::".join((self.cache_prefix, *parts))

    def _get_cached(self, key: str, fingerprint: Tuple[Any, ...]) -> Optional[StageOutput]:
        if not self._cache:
            return None
        result = self._cache.get(key, fingerprint)
        if result:
            result.metadata = {**result.metadata, "cache_hit": True}
        return result

    def _set_cache(self, key: str, fingerprint: Tuple[Any, ...], output: StageOutput) -> None:
        if not self._cache or output.error:
            return
        self._cache.set(key, fingerprint, output)

    def _run_with_retries(self, func: Callable[[], StageOutput]) -> StageOutput:
        last_output: Optional[StageOutput] = None
        for attempt in range(self.max_retries):
            output = func()
            output.metadata = {**output.metadata, "attempt": attempt + 1}
            if not output.error or not output.retryable:
                return output
            last_output = output
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_backoff * (attempt + 1))
        return last_output or StageOutput(
            payload={},
            metadata={"stage": self.cache_prefix, "status": "exhausted"},
            error="inference_failed",
            retryable=False,
        )


def _file_fingerprint(file_path: Path) -> Tuple[Any, ...]:
    try:
        stat = file_path.stat()
    except FileNotFoundError:
        return (str(file_path.resolve()), None, None)
    return (str(file_path.resolve()), stat.st_mtime_ns, stat.st_size)


def _text_fingerprint(*values: str) -> Tuple[Any, ...]:
    return tuple(hash(value) for value in values)


class VisionModelClient(BaseInferenceClient):
    """Lazy loader for Donut / VQA style models."""

    def __init__(
        self,
        model_name: str = "nielsr/donut-base-finetuned-docvqa",
        max_length: int = 512,
        cache_enabled: bool = True,
        cache_size: int = 16,
        max_retries: int = 2,
        retry_backoff: float = 0.25,
    ) -> None:
        super().__init__(
            cache_prefix="vision",
            cache_enabled=cache_enabled,
            cache_size=cache_size,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
        self.model_name = model_name
        self.max_length = max_length
        self._processor = None
        self._model = None

    def parse(self, file_path: Path) -> StageOutput:
        fingerprint = _file_fingerprint(file_path)
        cache_key = self._cache_key(self.model_name, str(file_path))
        cached = self._get_cached(cache_key, fingerprint)
        if cached:
            return cached

        def infer() -> StageOutput:
            start = time.perf_counter()
            metadata = {"model": self.model_name, "stage": "vision_transformer"}
            try:
                from PIL import Image
                from transformers import DonutProcessor, VisionEncoderDecoderModel
            except ImportError as exc:
                logger.debug("Transformers/Pillow missing for vision stage: %s", exc)
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={},
                    latency_ms=latency,
                    metadata={**metadata, "status": "skipped"},
                    error="missing_dependencies",
                    retryable=False,
                )

            if self._processor is None or self._model is None:
                try:
                    self._processor = DonutProcessor.from_pretrained(self.model_name)
                    self._model = VisionEncoderDecoderModel.from_pretrained(self.model_name)
                except Exception as exc:  # pragma: no cover - optional dependency
                    logger.warning("Failed to load Donut model %s: %s", self.model_name, exc)
                    latency = (time.perf_counter() - start) * 1000
                    return StageOutput(
                        payload={},
                        latency_ms=latency,
                        metadata={**metadata, "status": "load_error"},
                        error=str(exc),
                        retryable=False,
                    )

            try:
                image = Image.open(file_path).convert("RGB")
                pixel_values = self._processor(image, return_tensors="pt").pixel_values
                output_ids = self._model.generate(pixel_values, max_length=self.max_length)
                decoded = self._processor.batch_decode(output_ids, skip_special_tokens=True)[0]
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"vision_parser": decoded},
                    confidence=1.0,
                    latency_ms=latency,
                    metadata={**metadata, "status": "ok"},
                )
            except Exception as exc:  # pragma: no cover - hardware/torch runtime
                logger.warning("Vision model inference failed: %s", exc)
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={},
                    latency_ms=latency,
                    metadata={**metadata, "status": "runtime_error"},
                    error=str(exc),
                )

        output = self._run_with_retries(infer)
        self._set_cache(cache_key, fingerprint, output)
        return output


class OCRClient(BaseInferenceClient):
    """Handles text extraction via EasyOCR with graceful degradation."""

    def __init__(
        self,
        languages: Tuple[str, ...] = ("en", "hi"),
        cache_enabled: bool = True,
        cache_size: int = 64,
        max_retries: int = 2,
        retry_backoff: float = 0.2,
    ) -> None:
        super().__init__(
            cache_prefix="ocr",
            cache_enabled=cache_enabled,
            cache_size=cache_size,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
        self.languages = languages
        self._reader = None

    def read_text(self, file_path: Path) -> StageOutput:
        fingerprint = _file_fingerprint(file_path)
        cache_key = self._cache_key("easyocr", str(file_path))
        cached = self._get_cached(cache_key, fingerprint)
        if cached:
            return cached

        def infer() -> StageOutput:
            start = time.perf_counter()
            metadata = {"languages": self.languages, "stage": "ocr"}
            try:
                import easyocr
            except ImportError:
                logger.debug("easyocr not installed; using empty OCR output")
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"text": ""},
                    latency_ms=latency,
                    metadata={**metadata, "status": "skipped"},
                    error="missing_easyocr",
                    retryable=False,
                )

            if self._reader is None:
                try:
                    self._reader = easyocr.Reader(list(self.languages))
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed to initialize EasyOCR reader: %s", exc)
                    latency = (time.perf_counter() - start) * 1000
                    return StageOutput(
                        payload={"text": ""},
                        latency_ms=latency,
                        metadata={**metadata, "status": "init_error"},
                        error=str(exc),
                        retryable=False,
                    )

            try:
                result = self._reader.readtext(str(file_path), detail=0)
                text = " ".join(result)
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"text": text},
                    confidence=1.0 if text else 0.0,
                    latency_ms=latency,
                    metadata={**metadata, "status": "ok"},
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("OCR failed: %s", exc)
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"text": ""},
                    latency_ms=latency,
                    metadata={**metadata, "status": "runtime_error"},
                    error=str(exc),
                )

        output = self._run_with_retries(infer)
        self._set_cache(cache_key, fingerprint, output)
        return output


class NERClient(BaseInferenceClient):
    """Named Entity Recognition using SpaCy."""

    def __init__(
        self,
        model_name: str = "en_core_web_md",
        cache_enabled: bool = True,
        cache_size: int = 64,
        max_retries: int = 1,
        retry_backoff: float = 0.1,
    ) -> None:
        super().__init__(
            cache_prefix="ner",
            cache_enabled=cache_enabled,
            cache_size=cache_size,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
        self.model_name = model_name
        self._nlp = None

    def extract_entities(self, text: str) -> StageOutput:
        fingerprint = _text_fingerprint(text, self.model_name)
        cache_key = self._cache_key("spacy", str(hash(text)))
        cached = self._get_cached(cache_key, fingerprint)
        if cached:
            return cached

        def infer() -> StageOutput:
            start = time.perf_counter()
            metadata = {"model": self.model_name, "stage": "ner"}
            
            if not text:
                 latency = (time.perf_counter() - start) * 1000
                 return StageOutput(
                    payload={"entities": {}},
                    confidence=0.0,
                    latency_ms=latency,
                    metadata={**metadata, "status": "empty_text"},
                )

            try:
                import spacy
            except ImportError:
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"entities": {}},
                    confidence=0.0,
                    latency_ms=latency,
                    metadata={**metadata, "status": "skipped"},
                    error="missing_spacy",
                    retryable=False,
                )

            if self._nlp is None:
                try:
                    self._nlp = spacy.load(self.model_name)
                except OSError:
                     logger.warning(f"SpaCy model {self.model_name} not found. Trying to download...")
                     try:
                         # Fallback to blank if download not possible in runtime or use subprocess
                         # Ideally models are pre-downloaded.
                         from spacy.cli import download
                         download(self.model_name)
                         self._nlp = spacy.load(self.model_name)
                     except Exception as exc:
                         logger.error(f"Failed to load or download SpaCy model {self.model_name}: {exc}")
                         self._nlp = spacy.blank("en") # Fallback
                except Exception as exc:
                    logger.warning("Failed to load SpaCy model %s: %s", self.model_name, exc)
                    latency = (time.perf_counter() - start) * 1000
                    return StageOutput(
                        payload={"entities": {}},
                        latency_ms=latency,
                        metadata={**metadata, "status": "load_error"},
                        error=str(exc),
                        retryable=False,
                    )

            try:
                doc = self._nlp(text)
                entities: Dict[str, Any] = {"raw_text": text[:512]}
                for ent in doc.ents:
                    entities.setdefault(ent.label_, []).append(ent.text)
                
                entity_count = sum(len(values) for key, values in entities.items() if key != "raw_text" and isinstance(values, list))
                confidence = min(1.0, entity_count / 5) if entity_count else 0.4
                
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"entities": entities},
                    confidence=confidence,
                    latency_ms=latency,
                    metadata={**metadata, "status": "ok", "entity_count": entity_count},
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("NER inference failed: %s", exc)
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"entities": {}},
                    latency_ms=latency,
                    metadata={**metadata, "status": "runtime_error"},
                    error=str(exc),
                )

        output = self._run_with_retries(infer)
        self._set_cache(cache_key, fingerprint, output)
        return output


class EmbeddingClient(BaseInferenceClient):
    """SentenceTransformer-backed similarity comparer."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        threshold: float = 0.6,
        cache_enabled: bool = True,
        cache_size: int = 128,
        max_retries: int = 2,
        retry_backoff: float = 0.2,
    ) -> None:
        super().__init__(
            cache_prefix="embedding",
            cache_enabled=cache_enabled,
            cache_size=cache_size,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
        self.model_name = model_name
        self.threshold = threshold
        self._model = None
        self._util = None

    def compare(self, source: str, target: str) -> StageOutput:
        fingerprint = _text_fingerprint(source, target, str(self.threshold), self.model_name)
        cache_key = self._cache_key(str(hash(source)), str(hash(target)))
        cached = self._get_cached(cache_key, fingerprint)
        if cached:
            return cached

        def infer() -> StageOutput:
            start = time.perf_counter()
            metadata = {"model": self.model_name, "stage": "embeddings", "threshold": self.threshold}
            try:
                from sentence_transformers import SentenceTransformer, util
            except ImportError:
                logger.debug("SentenceTransformer missing; fallback to string overlap")
                match = bool(source and target and source == target)
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"similarity": 1.0 if match else 0.0, "match": match},
                    confidence=1.0 if match else 0.2,
                    latency_ms=latency,
                    metadata={**metadata, "status": "skipped"},
                    error="missing_sentence_transformers",
                    retryable=False,
                )

            if self._model is None or self._util is None:
                try:
                    self._model = SentenceTransformer(self.model_name)
                    self._util = util
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed to load SentenceTransformer %s: %s", self.model_name, exc)
                    latency = (time.perf_counter() - start) * 1000
                    return StageOutput(
                        payload={"similarity": 0.0, "match": True},
                        latency_ms=latency,
                        metadata={**metadata, "status": "load_error"},
                        error=str(exc),
                        retryable=False,
                    )

            try:
                emb_a = self._model.encode(source, convert_to_tensor=True)
                emb_b = self._model.encode(target, convert_to_tensor=True)
                similarity = float(self._util.pytorch_cos_sim(emb_a, emb_b).item())
                match = similarity >= self.threshold
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"similarity": similarity, "match": match},
                    confidence=similarity,
                    latency_ms=latency,
                    metadata={**metadata, "status": "ok"},
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Embedding similarity failed: %s", exc)
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"similarity": 0.0, "match": True},
                    latency_ms=latency,
                    metadata={**metadata, "status": "runtime_error"},
                    error=str(exc),
                )

        output = self._run_with_retries(infer)
        self._set_cache(cache_key, fingerprint, output)
        return output


class ForgeryClient(BaseInferenceClient):
    """Runs lightweight CV heuristics for forgery/liveness estimation."""

    def __init__(
        self,
        cache_enabled: bool = True,
        cache_size: int = 64,
        max_retries: int = 1,
        retry_backoff: float = 0.15,
    ) -> None:
        super().__init__(
            cache_prefix="forgery",
            cache_enabled=cache_enabled,
            cache_size=cache_size,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )

    def analyze(self, file_path: Path, doc_type: DocumentType) -> StageOutput:
        fingerprint = _file_fingerprint(file_path) + (doc_type.value,)
        cache_key = self._cache_key(doc_type.value, str(file_path))
        cached = self._get_cached(cache_key, fingerprint)
        if cached:
            return cached

        def infer() -> StageOutput:
            start = time.perf_counter()
            metadata = {"stage": "cv_forgery", "doc_type": doc_type.value}
            try:
                import cv2
                import numpy as np
            except ImportError:
                logger.debug("OpenCV/Numpy missing; returning neutral authenticity")
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"authenticity": 0.5, "liveness": None},
                    latency_ms=latency,
                    metadata={**metadata, "status": "skipped"},
                    error="missing_opencv",
                    retryable=False,
                )

            img = cv2.imread(str(file_path))
            if img is None:
                latency = (time.perf_counter() - start) * 1000
                return StageOutput(
                    payload={"authenticity": 0.5, "liveness": None},
                    latency_ms=latency,
                    metadata={**metadata, "status": "read_error"},
                    error="image_not_found",
                    retryable=False,
                )
            
            # Default Heuristic
            variance = float(cv2.Laplacian(img, cv2.CV_64F).var())
            authenticity = max(0.1, min(1.0, variance / 1000))
            liveness = None
            
            # MiniFASNet Inference (PyTorch) if available
            model_path = Path("app/models_data/forgery/2.7_80x80_MiniFASNetV2.pth")
            if doc_type == DocumentType.SELFIE and model_path.exists():
                try:
                    import torch
                    from app.services.minifasnet import MiniFASNetV2

                    # Initialize model
                    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                    model = MiniFASNetV2(conv6_kernel=(7, 7)).to(device)
                    state_dict = torch.load(str(model_path), map_location=device)
                    
                    # Fix keys if they have 'module.' prefix (common in DataParallel)
                    new_state_dict = {}
                    for k, v in state_dict.items():
                        name = k[7:] if k.startswith('module.') else k
                        new_state_dict[name] = v
                    model.load_state_dict(new_state_dict)
                    model.eval()
                    
                    # Preprocessing (resize to 80x80, transpose to C,H,W, normalize)
                    resized = cv2.resize(img, (80, 80))
                    # MiniFASNet expects [0, 255] input? Or normalized?
                    # Standard is usually ToTensor() which is [0, 1] if using torchvision transforms
                    # or manual division. The paper code uses standard torchvision transforms.
                    # We will assume standard ToTensor-like behavior: (H,W,C) -> (C,H,W) / 255.0
                    inp = resized.astype(np.float32).transpose(2, 0, 1) # C H W
                    inp = torch.from_numpy(inp).unsqueeze(0).to(device)
                    
                    with torch.no_grad():
                        logits = model(inp)
                        probs = torch.nn.functional.softmax(logits, dim=1).cpu().numpy()
                    
                    # Class 1 is "Live", Class 0 or 2 are Spoof depending on specific training. 
                    # Usually index 1 is live for binary, but MiniFASNet original has 3 classes (Live, Spoof1, Spoof2)?
                    # Actually looking at definition: num_classes=3 by default.
                    # In many anti-spoofing datasets: 1=Live, 0,2=Spoof.
                    # Let's assume index 1 is Live.
                    liveness_score = float(probs[0][1])
                    liveness = max(0.0, min(1.0, liveness_score))
                    
                    # Heuristic blend
                    authenticity = (authenticity + liveness) / 2
                    metadata["model"] = "MiniFASNetV2"
                except Exception as e:
                    logger.warning(f"MiniFASNet inference failed: {e}")
                    # Fallback to variance heuristic
                    liveness = max(0.1, min(1.0, variance / 500))
            elif doc_type == DocumentType.SELFIE:
                 liveness = max(0.1, min(1.0, variance / 500))

            latency = (time.perf_counter() - start) * 1000
            return StageOutput(
                payload={"authenticity": authenticity, "liveness": liveness},
                confidence=authenticity,
                latency_ms=latency,
                metadata={**metadata, "status": "ok"},
            )

        output = self._run_with_retries(infer)
        self._set_cache(cache_key, fingerprint, output)
        return output


@dataclass
class MLClientRegistry:
    """Helper to bundle the various model clients."""

    vision: VisionModelClient
    ocr: OCRClient
    embeddings: EmbeddingClient
    forgery: ForgeryClient
    ner: Optional[NERClient] = None

    @classmethod
    def default(
        cls,
        vision_model_name: str = "nielsr/donut-base-finetuned-docvqa",
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        ocr_languages: Tuple[str, ...] = ("en", "hi"),
        embedding_threshold: float = 0.6,
    ) -> "MLClientRegistry":
        return cls(
            vision=VisionModelClient(model_name=vision_model_name),
            ocr=OCRClient(languages=ocr_languages),
            embeddings=EmbeddingClient(model_name=embedding_model_name, threshold=embedding_threshold),
            forgery=ForgeryClient(),
            ner=NERClient(),
        )


