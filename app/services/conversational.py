"""Conversational multilingual assistant."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from langdetect import DetectorFactory, detect

DetectorFactory.seed = 42
logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    reply: str
    language: str
    safety_passed: bool
    metadata: Dict[str, Any]


class ConversationalAgent:
    """Wraps a lightweight text generation model with fairness guardrails."""

    def __init__(self, model_name: str = "google/flan-t5-small") -> None:
        try:
            from transformers import pipeline
        except ImportError:
            self._pipeline = None
        else:
            try:
                self._pipeline = pipeline("text2text-generation", model=model_name)
            except Exception as exc:  # pragma: no cover
                logger.warning("Conversational agent init failed: %s", exc)
                self._pipeline = None

        self.model_name = model_name

    def respond(self, message: str, context: Optional[dict] = None) -> ChatResponse:
        language = self._detect_language(message)
        safety_passed = self._safety_check(message)

        if not safety_passed:
            return ChatResponse(
                reply="I cannot process this request. Please rephrase respectfully.",
                language=language,
                safety_passed=False,
                metadata={"reason": "safety_violation"},
            )

        prompt = self._build_prompt(message, context, language)
        reply = self._generate(prompt)

        return ChatResponse(
            reply=reply,
            language=language,
            safety_passed=True,
            metadata={"model": self.model_name},
        )

    def _detect_language(self, message: str) -> str:
        try:
            return detect(message)
        except Exception:
            return "en"

    def _safety_check(self, message: str) -> bool:
        lowered = message.lower()
        banned = ["hate", "terror", "bomb"]
        return not any(term in lowered for term in banned)

    def _build_prompt(self, message: str, context: Optional[dict], language: str) -> str:
        status = context.get("status") if context else "unknown"
        recent_nudges = ", ".join(context.get("nudges", [])) if context else "none"
        return (
            f"You are Saral-KYC's compliance assistant. Respond in language {language}. "
            f"Application status: {status}. Recent nudges: {recent_nudges}. "
            f"Message: {message}"
        )

    def _generate(self, prompt: str) -> str:
        if not self._pipeline:
            return (
                "Saral-KYC assistant: I'm here to help with your onboarding. "
                "Please follow the on-screen checklist and let me know if you have questions."
            )
        try:
            generated = self._pipeline(prompt, max_new_tokens=128)
            return generated[0]["generated_text"].strip()
        except Exception as exc:  # pragma: no cover
            logger.warning("Conversational inference failed: %s", exc)
            return "I'm unable to respond right now. Please try again shortly."

