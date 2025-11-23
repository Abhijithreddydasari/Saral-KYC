"""Application configuration and settings management."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    app_name: str = "Saral-KYC API"
    env: str = "dev"
    doc_pipeline_mode: str = "full"
    api_v1_prefix: str = "/api/v1"
    cors_origins: List[str] = ["*"]

    secret_key: str = Field(default="")
    encryption_key: str = Field(default="")
    access_token_expire_minutes: int = 60

    # Assistant / conversational agent
    assistant_model_name: str = "ai4bharat/IndicBARTSS"
    assistant_system_prompt: str = (
        "You are Saral, a friendly multilingual compliance assistant for KYC journeys. "
        "Be concise, polite, and reference user data when helpful."
    )
    assistant_default_language: str = "en"
    assistant_max_input_tokens: int = 512
    assistant_max_output_tokens: int = 256
    assistant_history_limit: int = 6

    database_url: str = "sqlite:///./saral_kyc.db"
    storage_path: str = "./storage"

    log_level: str = "INFO"
    enable_request_logging: bool = True

    doc_stage_weight_vision: float = 0.35
    doc_stage_weight_ocr: float = 0.35
    doc_stage_weight_forgery: float = 0.2
    doc_stage_weight_crossdoc: float = 0.1
    doc_similarity_threshold: float = 0.6
    doc_metadata_max_drift_minutes: int = 90
    doc_language_mismatch_penalty: float = 0.2
    doc_layout_anomaly_threshold: float = 0.35
    doc_entity_overlap_threshold: float = 0.4
    doc_enable_vision_stage: bool = False
    doc_enable_ocr_stage: bool = True
    doc_enable_embeddings_stage: bool = True
    doc_enable_metadata_stage: bool = True
    doc_embedding_min_chars: int = 80
    doc_enable_async_processing: bool = False

    # Model Paths
    model_dir_vision: str = "./app/models_data/vision/donut-docvqa"
    model_dir_forgery: str = "./app/models_data/forgery/2.7_80x80_MiniFASNetV2.pth"
    model_spacy_ner: str = "en_core_web_md"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def storage_dir(self) -> Path:
        return Path(self.storage_path).resolve()


@lru_cache
def get_settings() -> Settings:
    """Returns a cached Settings instance."""
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings

