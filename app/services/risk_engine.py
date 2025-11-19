"""Risk scoring, anomaly detection, and explainability helpers."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from app.models.application import DocumentArtifact, KycApplication
from app.models.enums import DocumentStatus

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    score: float
    band: str
    explanation: Dict[str, Any]
    fairness_report: Dict[str, Any]
    rule_version: str = "2024.11"


@dataclass
class FeatureVector:
    """Aggregated document intelligence signals for the risk engine."""

    doc_score: float
    stage_breakdown: Dict[str, float]
    coverage: float
    doc_mix: List[str]
    doc_type_counter: Dict[str, int]
    liveness_penalty: float
    anomaly_penalty: float
    metadata_penalty: float
    language_penalty: float
    flag_counter: Dict[str, int]
    ensemble_averages: Dict[str, float]

    @classmethod
    def from_documents(cls, documents: List[DocumentArtifact]) -> "FeatureVector":
        processed = [doc for doc in documents if doc.status == DocumentStatus.PROCESSED]
        doc_mix = [doc.doc_type.value for doc in documents if doc.doc_type]
        doc_type_counter = dict(Counter(doc_mix))
        coverage = len(processed) / max(1, len(documents)) if documents else 0.0

        doc_scores = [doc.authenticity_score or 0.5 for doc in processed]
        doc_score = mean(doc_scores) if doc_scores else 0.5

        stage_values: Dict[str, List[float]] = defaultdict(list)
        liveness_penalty = 0.0
        anomaly_penalty = 0.0
        metadata_penalty = 0.0
        language_penalty = 0.0
        flag_counter: Counter[str] = Counter()
        ensemble_totals: Dict[str, List[float]] = defaultdict(list)
        for doc in processed:
            if doc.liveness_score is not None and doc.liveness_score < 0.5:
                liveness_penalty += 0.05
            doc_flags = doc.anomaly_flags or []
            anomaly_penalty += 0.05 * len(doc_flags)
            flag_counter.update(doc_flags)
            if "language_mismatch" in doc_flags:
                language_penalty += 0.03
            if any(flag.startswith("metadata") or flag == "timestamp_drift" for flag in doc_flags):
                metadata_penalty += 0.02

            trace = doc.model_trace or {}
            stage_scores = trace.get("stage_scores") or {}
            for name, value in stage_scores.items():
                try:
                    stage_values[name].append(float(value))
                except (TypeError, ValueError):
                    continue
            ensemble = trace.get("ensemble") or {}
            for name, value in ensemble.items():
                try:
                    ensemble_totals[name].append(float(value))
                except (TypeError, ValueError):
                    continue

        stage_breakdown = {name: mean(values) for name, values in stage_values.items()}
        defaults = {"vision": 0.4, "ocr": 0.4, "forgery": 0.5, "crossdoc": 0.75}
        for key, default in defaults.items():
            stage_breakdown.setdefault(key, default)
        ensemble_averages = {name: mean(values) for name, values in ensemble_totals.items()}

        return cls(
            doc_score=doc_score,
            stage_breakdown=stage_breakdown,
            coverage=coverage,
            doc_mix=doc_mix,
            doc_type_counter=doc_type_counter,
            liveness_penalty=liveness_penalty,
            anomaly_penalty=anomaly_penalty,
             metadata_penalty=metadata_penalty,
             language_penalty=language_penalty,
             flag_counter=dict(flag_counter),
             ensemble_averages=ensemble_averages,
        )


class GraphSignalAnalyzer:
    """Lightweight placeholder for graph anomaly detection."""

    def __init__(self) -> None:
        try:
            import networkx as nx
        except ImportError as exc:  # pragma: no cover
            logger.warning("networkx not installed: %s", exc)
            nx = None
        self._nx = nx
        self._graph = nx.Graph() if nx else None

    def score(self, application: KycApplication) -> float:
        if not self._graph:
            return 0.5

        node_id = application.reference_id
        self._graph.add_node(node_id, kind="app")

        if application.email:
            domain = application.email.split("@")[-1]
            self._graph.add_node(domain, kind="domain")
            self._graph.add_edge(node_id, domain)

        if application.phone_number:
            phone_cluster = application.phone_number[:4]
            self._graph.add_node(phone_cluster, kind="phone_cluster")
            self._graph.add_edge(node_id, phone_cluster)

        centrality = self._nx.degree_centrality(self._graph).get(node_id, 0.0)
        anomaly_score = 1 - min(1.0, centrality)
        return anomaly_score


class BehaviorAnalyzer:
    """Multilingual text risk analyzer backed by open-source models."""

    def __init__(self, model_name: str = "cardiffnlp/twitter-xlm-roberta-base-sentiment") -> None:
        try:
            from transformers import pipeline
        except ImportError:
            self._pipeline = None
        else:
            try:
                self._pipeline = pipeline("sentiment-analysis", model=model_name)
            except Exception as exc:  # pragma: no cover
                logger.warning("LLM pipeline init failed: %s", exc)
                self._pipeline = None

    def score(self, statement: Optional[str]) -> Tuple[float, str]:
        if not statement:
            return 0.6, "neutral"

        if not self._pipeline:
            lower = statement.lower()
            if any(word in lower for word in ("fraud", "delay", "issue")):
                return 0.3, "negative"
            return 0.7, "positive"

        try:
            result = self._pipeline(statement[:256])[0]
        except Exception as exc:  # pragma: no cover
            logger.warning("LLM inference failed: %s", exc)
            return 0.6, "neutral"

        label = result.get("label", "neutral").lower()
        score = float(result.get("score", 0.5))
        normalized = score if "pos" in label else 1 - score
        return normalized, label


class RiskEngine:
    """Combines document authenticity, graph anomalies, and behavior understanding."""

    def __init__(self) -> None:
        self.graph_analyzer = GraphSignalAnalyzer()
        self.behavior_analyzer = BehaviorAnalyzer()

    def assess(
        self,
        application: KycApplication,
        documents: List[DocumentArtifact],
        customer_statement: Optional[str] = None,
    ) -> RiskAssessment:
        features = FeatureVector.from_documents(documents)
        doc_score = features.doc_score
        graph_score = self.graph_analyzer.score(application)
        behavior_score, sentiment_label = self.behavior_analyzer.score(customer_statement)
        behavior_score = self._apply_language_prior(behavior_score, application.preferred_language)
        coverage_penalty = self._coverage_penalty(features.coverage)
        mix_penalty = self._document_mix_penalty(features.doc_type_counter)

        combined = (
            0.5 * doc_score
            + 0.2 * graph_score
            + 0.15 * behavior_score
            + 0.15 * features.stage_breakdown.get("crossdoc", 0.75)
            - features.anomaly_penalty
            - features.liveness_penalty
            - coverage_penalty
            - features.metadata_penalty
            - features.language_penalty
            - mix_penalty
        )
        combined = max(0.0, min(1.0, combined))

        band = self._band(combined)
        penalties = {
            "anomaly": features.anomaly_penalty,
            "liveness": features.liveness_penalty,
            "coverage": coverage_penalty,
            "language": features.language_penalty,
            "metadata": features.metadata_penalty,
            "mix": mix_penalty,
        }
        explanation = self._build_explanation(
            features,
            doc_score,
            graph_score,
            behavior_score,
            penalties,
            sentiment_label,
        )
        fairness_report = self._build_fairness(application, documents, features, combined, penalties)

        return RiskAssessment(
            score=combined,
            band=band,
            explanation=explanation,
            fairness_report=fairness_report,
        )

    def _apply_language_prior(self, score: float, language: Optional[str]) -> float:
        if not language:
            return score
        normalized = language.lower()
        if normalized.startswith(("hi", "bn")):
            return min(1.0, score + 0.05)
        if normalized.startswith(("mr", "ta", "te")):
            return max(0.0, score - 0.02)
        return score

    def _band(self, score: float) -> str:
        if score >= 0.75:
            return "low"
        if score >= 0.45:
            return "medium"
        return "high"

    def _coverage_penalty(self, coverage: float) -> float:
        if coverage >= 0.8:
            return 0.0
        if coverage >= 0.5:
            return 0.05
        return 0.1

    def _document_mix_penalty(self, doc_type_counter: Dict[str, int]) -> float:
        if not doc_type_counter:
            return 0.1
        if len(doc_type_counter) < 2:
            return 0.05
        return 0.0

    def _build_explanation(
        self,
        features: FeatureVector,
        doc_score: float,
        graph_score: float,
        behavior_score: float,
        penalties: Dict[str, float],
        sentiment_label: str,
    ) -> Dict[str, Any]:
        stage_breakdown = features.stage_breakdown
        return {
            "factors": [
                {
                    "id": "document_authenticity",
                    "weight": 0.6,
                    "value": round(doc_score, 3),
                    "detail": "Mean authenticity + liveness across documents",
                },
                {
                    "id": "graph_anomaly",
                    "weight": 0.25,
                    "value": round(graph_score, 3),
                    "detail": "NetworkX degree centrality-based anomaly score",
                },
                {
                    "id": "behavioral_signal",
                    "weight": 0.15,
                    "value": round(behavior_score, 3),
                    "detail": f"Sentiment classification ({sentiment_label})",
                },
                {
                    "id": "crossdoc_consistency",
                    "weight": 0.15,
                    "value": round(stage_breakdown.get("crossdoc", 0.75), 3),
                    "detail": "Cross-document embedding similarity",
                },
                {
                    "id": "liveness_penalty",
                    "weight": -penalties.get("liveness", 0.0),
                    "value": round(penalties.get("liveness", 0.0), 3),
                    "detail": "Penalties for low selfie/video liveness",
                },
                {
                    "id": "coverage_penalty",
                    "weight": -penalties.get("coverage", 0.0),
                    "value": round(penalties.get("coverage", 0.0), 3),
                    "detail": "Penalty for low processed-document coverage",
                },
                {
                    "id": "anomaly_penalty",
                    "weight": -penalties.get("anomaly", 0.0),
                    "value": round(penalties.get("anomaly", 0.0), 3),
                    "detail": "Penalties for cross-document mismatches",
                },
                {
                    "id": "language_consistency",
                    "weight": -penalties.get("language", 0.0),
                    "value": round(penalties.get("language", 0.0), 3),
                    "detail": "Penalty for repeated language mismatches",
                },
                {
                    "id": "metadata_integrity",
                    "weight": -penalties.get("metadata", 0.0),
                    "value": round(penalties.get("metadata", 0.0), 3),
                    "detail": "Penalty for timestamp or EXIF anomalies",
                },
                {
                    "id": "document_mix",
                    "weight": -penalties.get("mix", 0.0),
                    "value": round(penalties.get("mix", 0.0), 3),
                    "detail": "Penalty when application is missing critical document types",
                },
            ],
            "shap_like": {
                "document": doc_score,
                "graph": graph_score,
                "behavior": behavior_score,
                "crossdoc": stage_breakdown.get("crossdoc", 0.75),
                "liveness_penalty": penalties.get("liveness", 0.0),
                "coverage_penalty": penalties.get("coverage", 0.0),
                "anomaly_penalty": penalties.get("anomaly", 0.0),
                "language_penalty": penalties.get("language", 0.0),
                "metadata_penalty": penalties.get("metadata", 0.0),
                "mix_penalty": penalties.get("mix", 0.0),
            },
            "stage_breakdown": {k: round(v, 3) for k, v in stage_breakdown.items()},
            "ensemble": {k: round(v, 3) for k, v in features.ensemble_averages.items()},
            "flag_counter": features.flag_counter,
            "rule_version": RiskAssessment.rule_version,
        }

    def _build_fairness(
        self,
        application: KycApplication,
        documents: List[DocumentArtifact],
        features: FeatureVector,
        score: float,
        penalties: Dict[str, float],
    ) -> Dict[str, Any]:
        return {
            "language": application.preferred_language or "en",
            "document_coverage": round(features.coverage, 3),
            "document_mix": features.doc_mix,
            "doc_type_counts": features.doc_type_counter,
            "stage_breakdown": {k: round(v, 3) for k, v in features.stage_breakdown.items()},
            "penalties": {
                "liveness": round(features.liveness_penalty, 3),
                "anomaly": round(features.anomaly_penalty, 3),
                "language": round(penalties.get("language", 0.0), 3),
                "metadata": round(penalties.get("metadata", 0.0), 3),
                "coverage": round(penalties.get("coverage", 0.0), 3),
                "mix": round(penalties.get("mix", 0.0), 3),
            },
            "flag_counts": features.flag_counter,
            "ensemble_averages": {k: round(v, 3) for k, v in features.ensemble_averages.items()},
            "score": score,
        }

