"""Database initialization helpers."""

from sqlmodel import SQLModel

from app.db.base import SQLModel as BaseModel  # noqa
from app.db.session import engine


def init_db() -> None:
    """Create database tables."""
    SQLModel.metadata.create_all(bind=engine)

