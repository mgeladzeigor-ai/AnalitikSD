# src/analitiksd/auth/password.py
from __future__ import annotations

import bcrypt

# bcrypt не принимает пароль длиннее 72 байт (raise ValueError в bcrypt>=5).
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Вернуть bcrypt-хеш пароля (со случайной солью).

    Пароль длиннее 72 байт отвергаем явной ValueError (не молчаливое усечение и
    не сырая ошибка bcrypt) — вызывающий слой превратит её в 400, а не 500.
    """
    encoded = password.encode("utf-8")
    if len(encoded) > _MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {_MAX_PASSWORD_BYTES} bytes"
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Проверить пароль против хеша. Любая ошибка формата хеша -> False."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False
