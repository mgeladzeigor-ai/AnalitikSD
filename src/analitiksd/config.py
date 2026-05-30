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
    # Опциональные настройки агента/источника (нужны только для реальных вызовов;
    # ядро тестируется на моках). Секреты — только из окружения.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    bitrix_webhook_url: str | None = None


def get_settings() -> Settings:
    """Считать настройки из окружения. Обязательные: DATABASE_URL, JWT_SECRET."""
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        jwt_secret=os.environ["JWT_SECRET"],
        jwt_algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        jwt_expire_minutes=int(os.environ.get("JWT_EXPIRE_MINUTES", "480")),
        cookie_secure=os.environ.get("COOKIE_SECURE", "false").lower() in _TRUE_VALUES,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
        bitrix_webhook_url=os.environ.get("BITRIX_WEBHOOK_URL"),
    )
