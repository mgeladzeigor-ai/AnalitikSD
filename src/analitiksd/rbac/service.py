# src/analitiksd/rbac/service.py
from __future__ import annotations

from collections.abc import Iterable

_ACCESS_RANK = {"view": 1, "edit": 2}

# Публичный набор допустимых уровней доступа — единый источник правды
# (например, для валидации параметров фабрик зависимостей на старте приложения).
ACCESS_LEVELS = frozenset(_ACCESS_RANK)


def can_access_source(accessible_source_keys: Iterable[str], source_key: str) -> bool:
    """True, если ключ источника есть среди доступных ролям пользователя."""
    return source_key in set(accessible_source_keys)


def can_access_report(granted_levels: Iterable[str], required: str) -> bool:
    """True, если хотя бы один выданный уровень >= требуемого (edit покрывает view).

    Неизвестный требуемый уровень -> KeyError (тихо ничего не глотаем).
    """
    required_rank = _ACCESS_RANK[required]
    return any(_ACCESS_RANK.get(level, 0) >= required_rank for level in granted_levels)
