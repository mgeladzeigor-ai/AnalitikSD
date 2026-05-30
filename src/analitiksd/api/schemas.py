# src/analitiksd/api/schemas.py
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    # ограничиваем длину пароля (символы; bcrypt всё равно использует первые
    # 72 байта) — не пускаем огромные тела на неаутентифицированный /auth/login.
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    roles: list[str]
