"""System/diagnostic schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    app_version: str

