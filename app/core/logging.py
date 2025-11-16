"""Structured logging helpers."""

from __future__ import annotations

import logging
import logging.config
import re
from typing import Any, Dict

import structlog


def _build_logging_config(level: str) -> Dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
        },
        "root": {"handlers": ["default"], "level": level},
    }


def configure_logging(level: str = "INFO") -> None:
    """Configures standard logging + structlog for the app."""
    logging.config.dictConfig(_build_logging_config(level))
    logging.getLogger().addFilter(_PIIMaskingFilter())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class _PIIMaskingFilter(logging.Filter):
    pattern = re.compile(r"(\d{4,})")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.pattern.sub("****", record.msg)
        return True

