from __future__ import annotations

from typing import Any

from analitiksd.recipe.models import (
    AggregateOp,
    ComputedOp,
    FilterCondition,
    FilterOp,
    GroupByOp,
    LimitOp,
    Metric,
    SortKey,
    SortOp,
    Transform,
)


def apply_transforms(rows: list[dict[str, Any]], transforms: list[Transform]) -> list[dict[str, Any]]:
    """Применить конвейер трансформаций к строкам. Вход не мутируется."""
    result = [dict(r) for r in rows]
    group_keys: list[str] | None = None
    for t in transforms:
        if isinstance(t, FilterOp):
            result = _filter(result, t.where)
        elif isinstance(t, GroupByOp):
            group_keys = t.keys
        elif isinstance(t, AggregateOp):
            result = _aggregate(result, group_keys, t.metrics)
            group_keys = None
        elif isinstance(t, SortOp):
            result = _sort(result, t.sort)
        elif isinstance(t, ComputedOp):
            result = _computed(result, t)
        elif isinstance(t, LimitOp):
            result = result[: t.n]
        else:
            raise ValueError(f"Unknown transform: {type(t).__name__}")
    return result


def _cmp(value: Any, operator: str, target: Any) -> bool:
    if operator == "==":
        return value == target
    if operator == "!=":
        return value != target
    if operator == "in":
        return value in target
    if operator == "contains":
        return target in value if value is not None else False
    if value is None:
        return False  # упорядочивающие сравнения с None всегда False
    if operator == ">":
        return value > target
    if operator == ">=":
        return value >= target
    if operator == "<":
        return value < target
    if operator == "<=":
        return value <= target
    raise ValueError(f"Unknown operator: {operator}")


def _filter(rows: list[dict[str, Any]], where: list[FilterCondition]) -> list[dict[str, Any]]:
    def ok(row: dict[str, Any]) -> bool:
        return all(_cmp(row.get(c.field), c.operator, c.value) for c in where)

    return [r for r in rows if ok(r)]


# Заглушки — реализуются в следующих задачах:
def _aggregate(rows, group_keys, metrics):  # noqa: ANN001
    raise NotImplementedError


def _sort(rows, keys):  # noqa: ANN001
    raise NotImplementedError


def _computed(rows, t):  # noqa: ANN001
    raise NotImplementedError
