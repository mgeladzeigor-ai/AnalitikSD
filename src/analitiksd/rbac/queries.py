# src/analitiksd/rbac/queries.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from analitiksd.db.models import DataSource, ReportPerm, RoleSource, UserRole


def accessible_source_keys(session: Session, user_id: int) -> set[str]:
    """Множество ключей источников, доступных через роли пользователя."""
    rows = session.execute(
        select(DataSource.key)
        .join(RoleSource, RoleSource.source_id == DataSource.id)
        .join(UserRole, UserRole.role_id == RoleSource.role_id)
        .where(UserRole.user_id == user_id)
    ).scalars().all()
    return set(rows)


def report_access_levels(session: Session, user_id: int, report_id: int) -> list[str]:
    """Уровни доступа (view/edit), выданные ролям пользователя на конкретный отчёт.

    distinct(): разные роли могут давать один уровень — возвращаем уникальные значения.
    """
    rows = session.execute(
        select(ReportPerm.access)
        .join(UserRole, UserRole.role_id == ReportPerm.role_id)
        .where(UserRole.user_id == user_id, ReportPerm.report_id == report_id)
        .distinct()
    ).scalars().all()
    return list(rows)
