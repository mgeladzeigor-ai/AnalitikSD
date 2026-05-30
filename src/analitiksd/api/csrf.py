# src/analitiksd/api/csrf.py
from __future__ import annotations

import hmac
import secrets

from fastapi import HTTPException, Request, Response, status

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    """Случайный CSRF-токен для схемы double-submit."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(
    response: Response, token: str, *, secure: bool, max_age: int
) -> None:
    """Положить CSRF-токен в cookie, доступную JavaScript (НЕ HttpOnly).

    SPA читает токен из cookie и дублирует его в заголовке X-CSRF-Token —
    межсайтовый злоумышленник не может прочитать cookie нашего origin, поэтому
    не сможет подставить совпадающий заголовок.
    """
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=max_age,
    )


def require_csrf(request: Request) -> None:
    """FastAPI-зависимость: проверка double-submit CSRF для изменяющих маршрутов.

    Cookie-токен должен присутствовать и совпадать с заголовком X-CSRF-Token.
    Сравнение через hmac.compare_digest — против тайминговых атак.
    """
    cookie = request.cookies.get(CSRF_COOKIE_NAME)
    header = request.headers.get(CSRF_HEADER_NAME)
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )
