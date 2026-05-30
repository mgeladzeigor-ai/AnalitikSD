# src/analitiksd/api/auth_routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from analitiksd.api.csrf import (
    CSRF_COOKIE_NAME,
    generate_csrf_token,
    require_csrf,
    set_csrf_cookie,
)
from analitiksd.api.deps import COOKIE_NAME, get_current_user, get_db
from analitiksd.api.schemas import LoginRequest, UserOut
from analitiksd.auth.service import authenticate_user, role_names
from analitiksd.auth.tokens import create_access_token
from analitiksd.config import get_settings
from analitiksd.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    body: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> dict[str, str]:
    user = authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    settings = get_settings()
    max_age = settings.jwt_expire_minutes * 60
    token = create_access_token(str(user.id))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
    )
    # CSRF-токен (double-submit): живёт столько же, сколько сессия.
    set_csrf_cookie(
        response, generate_csrf_token(), secure=settings.cookie_secure, max_age=max_age
    )
    return {"status": "ok"}


@router.post("/logout")
def logout(response: Response, _: None = Depends(require_csrf)) -> dict[str, str]:
    # Аутентификация НЕ требуется: пользователь должен мочь сбросить
    # просроченную/застрявшую cookie. От CSRF защищает double-submit-токен.
    secure = get_settings().cookie_secure
    response.delete_cookie(key=COOKIE_NAME, secure=secure, httponly=True, samesite="lax")
    response.delete_cookie(key=CSRF_COOKIE_NAME, secure=secure, samesite="lax")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, name=user.name, roles=role_names(db, user.id)
    )
