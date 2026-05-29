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


def _aggregate(
    rows: list[dict[str, Any]],
    group_keys: list[str] | None,
    metrics: list[Metric],
) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = {}
    order: list[tuple] = []
    if group_keys:
        for r in rows:
            key = tuple(r.get(k) for k in group_keys)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(r)
    else:
        order = [()]
        groups = {(): rows}

    out: list[dict[str, Any]] = []
    for key in order:
        grp = groups[key]
        row: dict[str, Any] = {}
        if group_keys:
            for name, val in zip(group_keys, key):
                row[name] = val
        for m in metrics:
            row[m.as_] = _metric(grp, m)
        out.append(row)
    return out


def _metric(grp: list[dict[str, Any]], m: Metric) -> Any:
    if m.fn == "count":
        return len(grp)
    if m.field is None:
        raise ValueError(f"Aggregate fn '{m.fn}' requires a field")
    vals = [r[m.field] for r in grp if r.get(m.field) is not None]
    if not vals:
        return 0 if m.fn == "sum" else None
    if m.fn == "sum":
        return sum(vals)
    if m.fn == "avg":
        return sum(vals) / len(vals)
    if m.fn == "min":
        return min(vals)
    if m.fn == "max":
        return max(vals)
    raise ValueError(f"Unknown aggregate fn: {m.fn}")


def _sort(rows: list[dict[str, Any]], keys: list[SortKey]) -> list[dict[str, Any]]:
    result = list(rows)
    # стабильная многоключевая сортировка: применяем ключи в обратном порядке
    for k in reversed(keys):
        result.sort(
            key=lambda r, by=k.by: (r.get(by) is None, r.get(by)),
            reverse=(k.dir == "desc"),
        )
    return result


def _operand(row: dict[str, Any], token: str) -> Any:
    try:
        num = float(token)
        return int(num) if num.is_integer() else num
    except ValueError:
        return row.get(token)


def _computed(rows: list[dict[str, Any]], t: ComputedOp) -> list[dict[str, Any]]:
    for row in rows:
        left = _operand(row, t.left)
        right = _operand(row, t.right)
        row[t.as_] = _arith(left, t.operator, right)
    return rows


def _arith(left: Any, operator: str, right: Any) -> Any:
    if left is None or right is None:
        return None
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        return None if right == 0 else left / right
    raise ValueError(f"Unknown operator: {operator}")
