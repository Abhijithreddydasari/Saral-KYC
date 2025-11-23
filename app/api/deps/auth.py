"""Authentication dependencies for FastAPI routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.api.deps.db import get_db
from app.models.user import User, UserSession

http_bearer = HTTPBearer(auto_error=False)


def _get_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")
    return credentials.credentials


def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    session: Session = Depends(get_db),
) -> UserSession:
    token = _get_token(credentials)
    session_obj = session.exec(select(UserSession).where(UserSession.token == token)).first()
    if not session_obj or not session_obj.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return session_obj


def get_current_user(
    session_obj: UserSession = Depends(get_current_session),
) -> User:
    return session_obj.user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    session: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    try:
        session_obj = get_current_session(credentials, session)
    except HTTPException:
        return None
    return session_obj.user

