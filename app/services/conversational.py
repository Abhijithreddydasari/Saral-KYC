"""Conversational multilingual assistant."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langdetect import DetectorFactory, detect

from app.core.config import get_settings

DetectorFactory.seed = 42
logger = logging.getLogger(__name__)


LANGUAGE_TAGS = {
    "as": "<2as>",
    "bn": "<2bn>",
    "en": "<2en>",
    "gu": "<2gu>",
    "hi": "<2hi>",
    "kn": "<2kn>",
    "ml": "<2ml>",
    "mr": "<2mr>",
    "or": "<2or>",
    "pa": "<2pa>",
    "ta": "<2ta>",
    "te": "<2te>",
}


@dataclass
class ChatResponse:
    reply: str
    language: str
    safety_passed: bool
    metadata: Dict[str, Any]


class ConversationalAgent:
    """IndicBARTSS backed conversational agent with multilingual context awareness."""

    def __init__(self, model_name: str | None = None) -> None:
        self._settings = get_settings()
        self.model_name = model_name or self._settings.assistant_model_name
        self.system_prompt = self._settings.assistant_system_prompt
        self.default_language = self._settings.assistant_default_language
        self.max_input_tokens = self._settings.assistant_max_input_tokens
        self.max_output_tokens = self._settings.assistant_max_output_tokens
        self.history_limit = self._settings.assistant_history_limit

        self._tokenizer = None
        self._model = None
        self._torch = None
        self._load_error: str | None = None

    def respond(
        self,
        message: str,
        context: Optional[dict] = None,
        history: Optional[List[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> ChatResponse:
        language = self._select_language(message, context)
        safety_passed = self._safety_check(message)

        if not safety_passed:
            english_reply = "I cannot process this request. Please rephrase respectfully."
            if language != "en":
                reply = self._translate_text(english_reply, "en", language) or english_reply
            else:
                reply = english_reply
            return ChatResponse(
                reply=reply,
                language=language,
                safety_passed=False,
                metadata={"reason": "safety_violation", "backend": "template"},
            )

        # Generate English response using templates
        english_reply = self._template_response(message, context or {})
        
        # Translate to target language if not English
        if language != "en":
            translated_reply = self._translate_text(english_reply, "en", language)
            reply = translated_reply if translated_reply else english_reply
            metadata = {
                "backend": "indicbartss_translation",
                "original_language": "en",
                "target_language": language,
            }
        else:
            reply = english_reply
            metadata = {
                "backend": "template",
                "language": "en",
            }

        return ChatResponse(
            reply=reply,
            language=language,
            safety_passed=True,
            metadata=metadata,
        )

    def _select_language(self, message: str, context: Optional[dict]) -> str:
        try:
            detected = detect(message)
        except Exception:
            detected = None

        preferred = (
            (context or {}).get("preferences", {}).get("preferred_language")
            or self.default_language
        )
        detected = detected or preferred or self.default_language
        detected = detected.split("-")[0]
        return detected if detected in LANGUAGE_TAGS else self.default_language

    def _safety_check(self, message: str) -> bool:
        lowered = message.lower()
        banned = ["hate", "terror", "bomb"]
        return not any(term in lowered for term in banned)

    def _summarize_context(self, context: dict) -> str:
        """Condense context into a brief natural language summary."""
        parts = []
        profile = context.get("profile", {})
        if name := profile.get("full_name"):
            parts.append(f"User: {name}")
        if status := context.get("latest_activity", {}).get("status"):
            parts.append(f"Application status: {status}")
        docs = context.get("documents", [])
        if docs:
            doc_types = [d.get("doc_type", "") for d in docs[:3] if isinstance(d, dict)]
            if doc_types:
                parts.append(f"Documents: {', '.join(doc_types)}")
        return ". ".join(parts) if parts else "No specific context available."

    def _build_prompt(
        self,
        message: str,
        context: dict,
        history: List[dict],
        language: str,
        system_prompt: str,
    ) -> str:
        """Build a minimal prompt optimized for IndicBARTSS text generation."""
        # Extract key info for a very brief context
        profile = context.get("profile", {})
        name = profile.get("full_name", "user")
        status = context.get("latest_activity", {}).get("status", "unknown")
        
        # Create a very simple, natural prompt
        # Format: Simple question with minimal context
        if "status" in message.lower() or "kyc" in message.lower():
            prompt = f"User {name} asks: {message}. Their KYC status is {status}. Reply helpfully:"
        elif any(word in message.lower() for word in ["document", "doc", "upload"]):
            docs = context.get("documents", [])
            doc_count = len(docs) if docs else 0
            prompt = f"User asks: {message}. They have {doc_count} documents uploaded. Reply:"
        else:
            # Generic greeting or question
            prompt = f"User says: {message}. Reply as a helpful KYC assistant:"
        
        return prompt

    def _ensure_model(self) -> bool:
        if self._tokenizer and self._model:
            return True

        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            import torch
        except ImportError as exc:  # pragma: no cover - dependency missing
            self._load_error = f"transformers_missing: {exc}"
            logger.warning("Transformers not available: %s", exc)
            return False

        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                do_lower_case=False,
                use_fast=False,
                keep_accents=True,
            )
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            self._model.to(torch.device("cpu"))
            self._model.eval()
            self._torch = torch
            self._load_error = None
            return True
        except Exception as exc:  # pragma: no cover - model load errors
            self._load_error = f"model_load_failed: {exc}"
            logger.warning("Failed to load IndicBARTSS model: %s", exc)
            self._tokenizer = None
            self._model = None
            self._torch = None
            return False

    def _language_tag(self, language: str) -> str:
        lang = language.lower()
        return LANGUAGE_TAGS.get(lang, LANGUAGE_TAGS.get(self.default_language, "<2en>"))

    def _template_response(self, message: str, context: dict) -> str:
        """Generate a helpful template-based response when the model isn't working well."""
        msg_lower = message.lower()
        profile = context.get("profile", {})
        name = profile.get("full_name", "there")
        status = context.get("latest_activity", {}).get("status", "in progress")
        docs = context.get("documents", [])
        
        # Check for pending documents question
        if any(word in msg_lower for word in ["pending", "what documents", "which documents", "missing"]):
            if not docs:
                return f"Hello {name}! You haven't uploaded any documents yet. Please upload your Aadhaar card, PAN card, and a selfie to complete your KYC application."
            else:
                # Check document statuses
                processed_docs = [d for d in docs if isinstance(d, dict) and d.get("status") == "processed"]
                pending_docs = [d for d in docs if isinstance(d, dict) and d.get("status") not in ["processed", "verified"]]
                
                if pending_docs:
                    pending_types = [d.get("doc_type", "document") for d in pending_docs]
                    pending_list = ", ".join(set(pending_types))
                    return f"Based on your application, the following documents are still pending review: {pending_list}. Our team is working on verifying them. You'll be notified once the verification is complete."
                else:
                    return f"Great news, {name}! All your uploaded documents have been processed. Your application is currently in '{status}' status. We'll notify you once the final verification is complete."
        
        # Check for escalation request
        elif any(word in msg_lower for word in ["escalate", "escalation", "priority", "urgent", "hurry"]):
            if status in ["pending_review", "in_progress"]:
                return f"I understand you'd like to expedite your KYC review, {name}. Your application is currently in '{status}' status. I've noted your request for priority handling. Our review team will prioritize your case and you should receive an update within 24-48 hours."
            elif status == "approved":
                return f"Good news, {name}! Your KYC application has already been approved. No escalation is needed."
            elif status == "rejected":
                return f"I see your application was rejected. To escalate this case, please contact our support team directly with your reference ID: {profile.get('reference_id', 'N/A')}. They can review your case and provide next steps."
            else:
                return f"Your application is currently in '{status}' status. I've forwarded your escalation request to our review team. They will prioritize your case and get back to you soon."
        
        # Check for verification time estimate
        elif any(word in msg_lower for word in ["how long", "when", "time", "duration", "estimate", "complete"]):
            submitted_at = context.get("latest_activity", {}).get("submitted_at")
            if status == "approved":
                completed_at = context.get("latest_activity", {}).get("completed_at")
                return f"Your KYC verification has been completed! Your application was approved. Check your email for the confirmation details."
            elif status == "rejected":
                return f"Your application verification has been completed, but unfortunately it was rejected. Please check your notifications for details on what needs to be corrected."
            elif status in ["pending_review", "in_progress"]:
                if submitted_at:
                    return f"Your KYC application is currently under review. Typically, verification takes 2-5 business days from submission. Since your application is in '{status}' status, you should receive an update within the next 1-3 business days. We'll notify you via email once the verification is complete."
                else:
                    return f"Your KYC application is in '{status}' status. Verification typically takes 2-5 business days. You'll receive an email notification once the review is complete."
            else:
                return f"Your application is currently in '{status}' status. Standard verification takes 2-5 business days. We'll notify you as soon as the review is complete."
        
        # Check for latest status update
        elif any(word in msg_lower for word in ["latest status", "status update", "current status", "update"]):
            latest_notification = context.get("latest_activity", {}).get("recent_notification")
            notifications = context.get("notifications", [])
            
            status_msg = f"Your KYC application status: **{status}**"
            
            if latest_notification:
                status_msg += f"\n\nLatest update: {latest_notification}"
            elif notifications:
                latest = notifications[0] if isinstance(notifications, list) and notifications else None
                if latest and isinstance(latest, dict):
                    status_msg += f"\n\nLatest notification: {latest.get('message', 'No recent updates')}"
            
            if docs:
                doc_statuses = {}
                for doc in docs:
                    if isinstance(doc, dict):
                        doc_type = doc.get("doc_type", "unknown")
                        doc_status = doc.get("status", "unknown")
                        doc_statuses[doc_type] = doc_status
                
                if doc_statuses:
                    status_msg += f"\n\nDocument status:"
                    for doc_type, doc_status in doc_statuses.items():
                        status_msg += f"\n- {doc_type}: {doc_status}"
            
            risk_info = context.get("risk", {})
            if risk_info.get("current_score") is not None:
                risk_score = risk_info.get("current_score")
                status_msg += f"\n\nRisk assessment score: {risk_score:.2f}"
            
            return status_msg
        
        # Existing templates
        elif any(word in msg_lower for word in ["hi", "hello", "hey", "namaste"]):
            return f"Hello {name}! I'm Saral, your KYC assistant. How can I help you today?"
        elif any(word in msg_lower for word in ["status", "kyc status", "application"]):
            return f"Your KYC application status is currently '{status}'. Would you like more details?"
        elif any(word in msg_lower for word in ["document", "doc", "upload"]):
            doc_count = len(docs) if docs else 0
            return f"You have {doc_count} document(s) uploaded. I can help you check their status or upload more."
        elif any(word in msg_lower for word in ["help", "assist", "support"]):
            return "I can help you with your KYC application status, document uploads, and answer questions about the process. What do you need?"
        else:
            return f"I'm here to help with your KYC application, {name}. What would you like to know?"

    def _generate(
        self, prompt: str, language: str, history_len: int, message: str = "", context: dict = None
    ) -> tuple[str, dict]:
        if not self._ensure_model():
            fallback = (
                "Saral assistant: I'm unable to use the multilingual model right now. "
                "Please try again later."
            )
            return fallback, {
                "model": self.model_name,
                "backend": "fallback",
                "load_error": self._load_error,
            }

        tokenizer = self._tokenizer
        model = self._model
        torch = self._torch

        source_lang_tag = self._language_tag(language)
        target_lang_tag = source_lang_tag
        decoder_start_token_id = tokenizer._convert_token_to_id_with_added_voc(target_lang_tag)

        formatted_prompt = f"{prompt.strip()} </s> {source_lang_tag}"
        encoded = tokenizer(
            formatted_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_input_tokens,
        )
        input_ids = encoded.input_ids.to(model.device)
        attention_mask = encoded.attention_mask.to(model.device)

        try:
            with torch.no_grad():
                output_ids = model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    use_cache=True,
                    num_beams=4,
                    max_new_tokens=self.max_output_tokens,
                    min_length=1,
                    early_stopping=True,
                    pad_token_id=tokenizer.pad_token_id,
                    bos_token_id=tokenizer.bos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    decoder_start_token_id=decoder_start_token_id,
                )
            decoded = tokenizer.decode(
                output_ids[0],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            ).strip()
            
            # Remove the language tag if it appears at the start
            for tag in LANGUAGE_TAGS.values():
                if decoded.startswith(tag):
                    decoded = decoded[len(tag):].strip()
            
            # Filter out responses that are echoing the prompt
            prompt_words = set(prompt.lower().split())
            decoded_words = set(decoded.lower().split())
            
            # If decoded contains most of the prompt words, it's likely echoing
            overlap = len(prompt_words & decoded_words)
            if overlap > len(prompt_words) * 0.4 and len(decoded) > 50:
                # Too much overlap - use template-based response instead
                decoded = self._template_response(message, context or {})
            
            # Ensure we have a reasonable response
            if not decoded or len(decoded) < 3:
                decoded = self._template_response(message, context or {})
            
            metadata = {
                "model": self.model_name,
                "backend": "indicbartss",
                "language_tag": source_lang_tag,
                "input_tokens": int(input_ids.shape[-1]),
                "output_tokens": int(output_ids.shape[-1]),
                "history_turns": history_len,
            }
            return decoded, metadata
        except Exception as exc:  # pragma: no cover - inference failure
            logger.warning("IndicBART inference failed: %s", exc)
            return (
                "I'm unable to respond right now. Please try again shortly.",
                {
                    "model": self.model_name,
                    "backend": "indicbartss",
                    "error": str(exc),
                },
            )

