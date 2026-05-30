# src/analitiksd/auth/password.py
from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """Вернуть bcrypt-хеш пароля (со случайной солью)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Проверить пароль против хеша. Любая ошибка формата хеша -> False."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False
