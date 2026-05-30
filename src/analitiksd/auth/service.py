# src/analitiksd/auth/service.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from analitiksd.auth.password import verify_password
from analitiksd.db.models import Role, User, UserRole


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """Вернуть пользователя при верных email+пароле и is_active, иначе None.

    Один и тот же None для «нет юзера / неверный пароль / неактивен» — не утекаем причину.
    """
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def role_names(session: Session, user_id: int) -> list[str]:
    """Имена ролей пользователя, отсортированные по алфавиту (детерминизм)."""
    rows = session.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.name)
    ).scalars().all()
    return list(rows)
