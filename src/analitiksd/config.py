# src/analitiksd/config.py
from __future__ import annotations

import os
from dataclasses import dataclass


_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 часов
    # Флаг Secure на auth/CSRF-cookie. False для локальных HTTP-прогонов (MVP),
    # в проде (HTTPS) выставляется COOKIE_SECURE=true.
    cookie_secure: bool = False


def get_settings() -> Settings:
    """Считать настройки из окружения. Обязательные: DATABASE_URL, JWT_SECRET."""
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        jwt_secret=os.environ["JWT_SECRET"],
        jwt_algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        jwt_expire_minutes=int(os.environ.get("JWT_EXPIRE_MINUTES", "480")),
        cookie_secure=os.environ.get("COOKIE_SECURE", "false").lower() in _TRUE_VALUES,
    )
