"""Database dependencies."""

from collections.abc import Generator

from sqlmodel import Session

from app.db.session import get_session


def get_db() -> Generator[Session, None, None]:
    """Yields a SQLModel session for request scope."""
    with get_session() as session:
        yield session

