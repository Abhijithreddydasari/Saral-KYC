"""Utility functions for identifiers."""

import uuid


def short_uuid() -> str:
    return uuid.uuid4().hex[:12]

