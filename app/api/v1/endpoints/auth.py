"""Authentication endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, select

from app.api.deps.auth import get_current_session, get_current_user
from app.api.deps.db import get_db
from app.core.config import get_settings
from app.core.security import generate_token
from app.models.user import User, UserSession
from app.schemas.user import AuthResponse, UserLoginRequest, UserRead, UserSignupRequest

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _issue_session(db: Session, user: User, user_agent: str | None = None) -> UserSession:
    session_obj = UserSession(
        user_id=user.id,
        token=generate_token(),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes),
        user_agent=user_agent,
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return session_obj


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserSignupRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.exec(select(User).where(User.email == payload.email.lower())).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(email=payload.email.lower(), full_name=payload.full_name.strip())
    user.set_password(payload.password)
    db.add(user)
    db.commit()
    db.refresh(user)

    session_obj = _issue_session(db, user, request.headers.get("user-agent"))
    return AuthResponse(token=session_obj.token, user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.exec(select(User).where(User.email == payload.email.lower())).first()
    if not user or not user.verify_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.mark_updated()
    db.add(user)
    session_obj = _issue_session(db, user, request.headers.get("user-agent"))
    return AuthResponse(token=session_obj.token, user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(
    session_obj: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> Response:
    session_obj.revoke()
    db.add(session_obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

