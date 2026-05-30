# src/analitiksd/api/deps.py
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from analitiksd.auth.tokens import decode_access_token
from analitiksd.db.base import get_session
from analitiksd.db.models import User

COOKIE_NAME = "access_token"

# FastAPI-зависимость сессии БД — единая реализация в db.base.get_session.
# Тесты переопределяют именно этот символ (app.dependency_overrides[get_db]).
get_db = get_session


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        subject = decode_access_token(token)
        user_id = int(subject)  # нечисловой sub -> ValueError -> тоже 401, не 500
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unknown user")
    return user
