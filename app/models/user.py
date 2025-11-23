"""User and session models for authentication."""

from datetime import datetime, timedelta

from sqlmodel import Field, Relationship

from app.core.config import get_settings
from app.core.security import generate_token, hash_password, verify_password
from app.models.base import PrimaryKeyModel, TimestampedModel

settings = get_settings()


def _default_expiry() -> datetime:
    return datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)


class User(PrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "user"

    email: str = Field(unique=True, index=True)
    full_name: str
    hashed_password: str
    is_admin: bool = Field(default=False)


    def set_password(self, password: str) -> None:
        self.hashed_password = hash_password(password)

    def verify_password(self, password: str) -> bool:
        return verify_password(password, self.hashed_password)


class UserSession(PrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "user_session"

    user_id: int = Field(foreign_key="user.id")
    user: User = Relationship()

    token: str = Field(default_factory=generate_token, unique=True, index=True)
    expires_at: datetime = Field(default_factory=_default_expiry)
    revoked_at: datetime | None = Field(default=None, nullable=True)
    user_agent: str | None = Field(default=None)

    @property
    def is_active(self) -> bool:
        if self.revoked_at:
            return False
        return datetime.utcnow() < self.expires_at

    def revoke(self) -> None:
        self.revoked_at = datetime.utcnow()

