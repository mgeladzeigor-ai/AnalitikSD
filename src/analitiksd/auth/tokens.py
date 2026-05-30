# src/analitiksd/auth/tokens.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from analitiksd.config import get_settings


def create_access_token(subject: str, *, expires_minutes: int | None = None) -> str:
    """Создать подписанный JWT с sub=subject и сроком жизни."""
    settings = get_settings()
    minutes = settings.jwt_expire_minutes if expires_minutes is None else expires_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Вернуть subject (sub) из валидного токена. Невалидный/просроченный -> jwt.PyJWTError.

    Токен без claim `sub` тоже считается невалидным (jwt.InvalidTokenError),
    чтобы весь поверхностный контракт ошибок оставался в рамках jwt.PyJWTError.
    """
    settings = get_settings()
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    subject = payload.get("sub")
    if subject is None:
        raise jwt.InvalidTokenError("Token missing 'sub' claim")
    return subject
