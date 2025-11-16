"""Risk scoring, anomaly detection, and explainability helpers."""

from __future__ import annotations

import logging
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
        doc_confidences = [
            doc.authenticity_score or 0.5
            for doc in documents
            if doc.status == DocumentStatus.PROCESSED and doc.authenticity_score is not None
        ]
        doc_score = mean(doc_confidences) if doc_confidences else 0.5

        anomaly_penalty = sum(len(doc.anomaly_flags or []) * 0.05 for doc in documents)
        graph_score = self.graph_analyzer.score(application)
        behavior_score, sentiment_label = self.behavior_analyzer.score(customer_statement)

        combined = (
            0.6 * doc_score
            + 0.25 * graph_score
            + 0.15 * behavior_score
            - anomaly_penalty
        )
        combined = max(0.0, min(1.0, combined))

        band = self._band(combined)
        explanation = self._build_explanation(
            doc_score,
            graph_score,
            behavior_score,
            anomaly_penalty,
            sentiment_label,
        )
        fairness_report = self._build_fairness(application, documents, combined)

        return RiskAssessment(
            score=combined,
            band=band,
            explanation=explanation,
            fairness_report=fairness_report,
        )

    def _band(self, score: float) -> str:
        if score >= 0.75:
            return "low"
        if score >= 0.45:
            return "medium"
        return "high"

    def _build_explanation(
        self,
        doc_score: float,
        graph_score: float,
        behavior_score: float,
        anomaly_penalty: float,
        sentiment_label: str,
    ) -> Dict[str, Any]:
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
                    "id": "penalty",
                    "weight": -anomaly_penalty,
                    "value": round(anomaly_penalty, 3),
                    "detail": "Penalties for cross-document mismatches",
                },
            ],
            "shap_like": {
                "document": doc_score,
                "graph": graph_score,
                "behavior": behavior_score,
                "penalty": anomaly_penalty,
            },
        }

    def _build_fairness(
        self,
        application: KycApplication,
        documents: List[DocumentArtifact],
        score: float,
    ) -> Dict[str, Any]:
        processed = sum(1 for doc in documents if doc.status == DocumentStatus.PROCESSED)
        coverage = processed / max(1, len(documents)) if documents else 0

        return {
            "language": application.preferred_language or "en",
            "document_coverage": round(coverage, 3),
            "document_mix": [doc.doc_type.value for doc in documents],
            "score": score,
        }

