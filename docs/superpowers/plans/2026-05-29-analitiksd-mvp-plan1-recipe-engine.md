# AnalitikSD MVP — План 1: Фундамент и движок рецептов

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать детерминированное ядро отчётов — модель «рецепта», подстановку параметров и движок трансформаций (`filter / group_by / aggregate / sort / computed / limit`) над списком строк, полностью покрытое тестами и без какого-либо ввода-вывода (без сети, БД, LLM).

**Architecture:** Чистый Python-пакет `analitiksd.recipe`. Рецепт описывается Pydantic-моделями. Движок принимает уже полученные строки (`list[dict]`) и применяет к ним декларативный конвейер трансформаций, возвращая `list[dict]`. Никакого ввода-вывода — это гарантирует воспроизводимость и делает ядро легко тестируемым. Исполнение шагов-источников (MCP/SQL) добавится в следующих планах и будет передавать строки в этот движок.

**Tech Stack:** Python 3.12, Pydantic v2, pytest.

---

## Файловая структура (создаётся этим планом)

```
pyproject.toml                          # метаданные пакета + конфиг pytest
src/analitiksd/__init__.py
src/analitiksd/recipe/__init__.py
src/analitiksd/recipe/models.py         # Pydantic-модели рецепта
src/analitiksd/recipe/params.py         # резолв и подстановка параметров
src/analitiksd/recipe/transforms.py     # движок трансформаций
tests/__init__.py
tests/recipe/__init__.py
tests/recipe/test_models.py
tests/recipe/test_params.py
tests/recipe/test_transforms.py
tests/recipe/test_pipeline.py
```

Принцип: один файл — одна ответственность (`models` — структуры, `params` — подстановка, `transforms` — исполнение). Файлы маленькие и сфокусированные.

---

## Task 1: Скаффолд проекта

**Files:**
- Create: `pyproject.toml`
- Create: `src/analitiksd/__init__.py`
- Create: `src/analitiksd/recipe/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/recipe/__init__.py`

- [ ] **Step 1: Создать `pyproject.toml`**

```toml
[project]
name = "analitiksd"
version = "0.1.0"
description = "AnalitikSD — система отчётности по данным компании"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-v"
```

- [ ] **Step 2: Создать пустые init-файлы**

Создать четыре пустых файла:
- `src/analitiksd/__init__.py`
- `src/analitiksd/recipe/__init__.py`
- `tests/__init__.py`
- `tests/recipe/__init__.py`

- [ ] **Step 3: Создать виртуальное окружение и установить зависимости**

Run:
```bash
python3.12 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
```
Expected: установка завершается успешно, `pytest` доступен.

- [ ] **Step 4: Проверить, что pytest запускается (тестов пока нет)**

Run: `. .venv/bin/activate && pytest`
Expected: `no tests ran` (код выхода 5) — это нормально, тестов ещё нет.

- [ ] **Step 5: Создать `.gitignore` и закоммитить**

Создать `.gitignore`:
```
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
```

```bash
git add pyproject.toml .gitignore src/ tests/
git commit -m "chore: scaffold analitiksd package and pytest config"
```

---

## Task 2: Модели рецепта

**Files:**
- Create: `src/analitiksd/recipe/models.py`
- Test: `tests/recipe/test_models.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/recipe/test_models.py
from analitiksd.recipe.models import Recipe, FilterOp, AggregateOp


def test_parse_recipe_from_dict():
    raw = {
        "version": 1,
        "source": "bitrix",
        "steps": [
            {"type": "tool_call", "tool": "crm_deal_list",
             "params": {"filter": {"CLOSED": "Y"}, "select": ["ID", "ASSIGNED_BY_ID", "OPPORTUNITY"]}}
        ],
        "transform": [
            {"op": "filter", "where": [{"field": "CLOSED", "operator": "==", "value": "Y"}]},
            {"op": "group_by", "keys": ["ASSIGNED_BY_ID"]},
            {"op": "aggregate", "metrics": [
                {"fn": "count", "as": "deals"},
                {"fn": "sum", "field": "OPPORTUNITY", "as": "amount"}]},
        ],
        "presentation": {"type": "table", "columns": ["ASSIGNED_BY_ID", "deals", "amount"],
                         "sort": [{"by": "amount", "dir": "desc"}]},
    }

    recipe = Recipe.model_validate(raw)

    assert recipe.source == "bitrix"
    assert recipe.steps[0].tool == "crm_deal_list"
    assert isinstance(recipe.transform[0], FilterOp)
    assert recipe.transform[0].where[0].field == "CLOSED"
    assert isinstance(recipe.transform[2], AggregateOp)
    assert recipe.transform[2].metrics[0].as_ == "deals"
    assert recipe.transform[2].metrics[1].field == "OPPORTUNITY"
    assert recipe.presentation.sort[0].by == "amount"
    assert recipe.presentation.sort[0].dir == "desc"
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `pytest tests/recipe/test_models.py -v`
Expected: FAIL с `ModuleNotFoundError: No module named 'analitiksd.recipe.models'`

- [ ] **Step 3: Реализовать модели**

```python
# src/analitiksd/recipe/models.py
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class ToolCallStep(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)


class FilterCondition(BaseModel):
    field: str
    operator: Literal["==", "!=", ">", ">=", "<", "<=", "in", "contains"]
    value: Any


class Metric(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    fn: Literal["count", "sum", "avg", "min", "max"]
    field: str | None = None
    as_: str = Field(alias="as")


class SortKey(BaseModel):
    by: str
    dir: Literal["asc", "desc"] = "asc"


class FilterOp(BaseModel):
    op: Literal["filter"]
    where: list[FilterCondition]


class GroupByOp(BaseModel):
    op: Literal["group_by"]
    keys: list[str]


class AggregateOp(BaseModel):
    op: Literal["aggregate"]
    metrics: list[Metric]


class SortOp(BaseModel):
    op: Literal["sort"]
    sort: list[SortKey]


class ComputedOp(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    op: Literal["computed"]
    as_: str = Field(alias="as")
    left: str
    operator: Literal["+", "-", "*", "/"]
    right: str


class LimitOp(BaseModel):
    op: Literal["limit"]
    n: int


Transform = Annotated[
    Union[FilterOp, GroupByOp, AggregateOp, SortOp, ComputedOp, LimitOp],
    Field(discriminator="op"),
]


class Presentation(BaseModel):
    type: Literal["table"] = "table"
    columns: list[str]
    sort: list[SortKey] = Field(default_factory=list)


class Recipe(BaseModel):
    version: int = 1
    source: str
    steps: list[ToolCallStep]
    transform: list[Transform] = Field(default_factory=list)
    presentation: Presentation
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `pytest tests/recipe/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/recipe/models.py tests/recipe/test_models.py
git commit -m "feat(recipe): add recipe pydantic models with discriminated transform union"
```

---

## Task 3: Резолв и подстановка параметров

Параметры (`reports.params`) описывают изменяемые значения (период и т.п.). При запуске они разворачиваются в плоскую карту (`{"period.from": "...", "period.to": "..."}`) и подставляются в плейсхолдеры `{{period.from}}` внутри `steps`.

**Files:**
- Create: `src/analitiksd/recipe/params.py`
- Test: `tests/recipe/test_params.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/recipe/test_params.py
import pytest

from analitiksd.recipe.params import resolve_params, substitute


def test_resolve_date_range_uses_default():
    params = {"period": {"type": "date_range",
                         "default": {"from": "2026-05-01", "to": "2026-05-31"}}}
    assert resolve_params(params, overrides=None) == {
        "period.from": "2026-05-01", "period.to": "2026-05-31"}


def test_resolve_date_range_applies_override():
    params = {"period": {"type": "date_range",
                         "default": {"from": "2026-05-01", "to": "2026-05-31"}}}
    overrides = {"period": {"from": "2026-06-01", "to": "2026-06-30"}}
    assert resolve_params(params, overrides) == {
        "period.from": "2026-06-01", "period.to": "2026-06-30"}


def test_substitute_replaces_exact_placeholder_keeping_type():
    obj = {"filter": {">=CLOSEDATE": "{{period.from}}", "LIMIT": 50}}
    out = substitute(obj, {"period.from": "2026-05-01"})
    assert out == {"filter": {">=CLOSEDATE": "2026-05-01", "LIMIT": 50}}


def test_substitute_replaces_inside_nested_lists():
    obj = {"select": ["ID"], "ranges": ["{{period.from}}", "{{period.to}}"]}
    out = substitute(obj, {"period.from": "a", "period.to": "b"})
    assert out == {"select": ["ID"], "ranges": ["a", "b"]}


def test_substitute_raises_on_unknown_placeholder():
    with pytest.raises(KeyError):
        substitute({"x": "{{missing.key}}"}, {})
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `pytest tests/recipe/test_params.py -v`
Expected: FAIL с `ModuleNotFoundError: No module named 'analitiksd.recipe.params'`

- [ ] **Step 3: Реализовать резолв и подстановку**

```python
# src/analitiksd/recipe/params.py
from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def resolve_params(params: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, str]:
    """Развернуть спецификацию параметров в плоскую карту значений.

    Для каждого параметра берётся override (если задан), иначе default.
    Поддерживаемый тип в MVP: date_range -> ключи "<name>.from" и "<name>.to".
    """
    overrides = overrides or {}
    flat: dict[str, str] = {}
    for name, spec in params.items():
        ptype = spec["type"]
        value = overrides.get(name, spec["default"])
        if ptype == "date_range":
            flat[f"{name}.from"] = value["from"]
            flat[f"{name}.to"] = value["to"]
        else:
            raise ValueError(f"Unsupported param type: {ptype}")
    return flat


def substitute(obj: Any, values: dict[str, str]) -> Any:
    """Рекурсивно подставить плейсхолдеры {{key}} из values в структуру obj.

    Если строка целиком равна одному плейсхолдеру, подставляется значение как есть.
    Неизвестный ключ -> KeyError (тихо ничего не глотаем).
    """
    if isinstance(obj, dict):
        return {k: substitute(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, values) for v in obj]
    if isinstance(obj, str):
        return _sub_str(obj, values)
    return obj


def _sub_str(s: str, values: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"Unknown placeholder: {key}")
        return str(values[key])

    return _PLACEHOLDER.sub(repl, s)
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `pytest tests/recipe/test_params.py -v`
Expected: PASS (5 тестов)

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/recipe/params.py tests/recipe/test_params.py
git commit -m "feat(recipe): add parameter resolution and placeholder substitution"
```

---

## Task 4: Трансформация filter

**Files:**
- Create: `src/analitiksd/recipe/transforms.py`
- Test: `tests/recipe/test_transforms.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/recipe/test_transforms.py
from analitiksd.recipe.models import FilterOp
from analitiksd.recipe.transforms import apply_transforms

ROWS = [
    {"id": 1, "manager": "A", "amount": 100, "closed": "Y"},
    {"id": 2, "manager": "B", "amount": 200, "closed": "N"},
    {"id": 3, "manager": "A", "amount": 300, "closed": "Y"},
]


def test_filter_equality():
    t = [FilterOp(op="filter", where=[{"field": "closed", "operator": "==", "value": "Y"}])]
    out = apply_transforms(ROWS, t)
    assert [r["id"] for r in out] == [1, 3]


def test_filter_greater_than():
    t = [FilterOp(op="filter", where=[{"field": "amount", "operator": ">", "value": 150}])]
    out = apply_transforms(ROWS, t)
    assert [r["id"] for r in out] == [2, 3]


def test_filter_in_operator():
    t = [FilterOp(op="filter", where=[{"field": "manager", "operator": "in", "value": ["B"]}])]
    out = apply_transforms(ROWS, t)
    assert [r["id"] for r in out] == [2]


def test_filter_does_not_mutate_input():
    t = [FilterOp(op="filter", where=[{"field": "closed", "operator": "==", "value": "Y"}])]
    apply_transforms(ROWS, t)
    assert len(ROWS) == 3  # исходный список не изменён
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `pytest tests/recipe/test_transforms.py -v`
Expected: FAIL с `ModuleNotFoundError: No module named 'analitiksd.recipe.transforms'`

- [ ] **Step 3: Реализовать движок с filter**

```python
# src/analitiksd/recipe/transforms.py
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
)


def apply_transforms(rows: list[dict[str, Any]], transforms: list[Any]) -> list[dict[str, Any]]:
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
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `pytest tests/recipe/test_transforms.py -v`
Expected: PASS (4 теста)

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/recipe/transforms.py tests/recipe/test_transforms.py
git commit -m "feat(recipe): add transform engine with filter operation"
```

---

## Task 5: Трансформации group_by + aggregate

**Files:**
- Modify: `src/analitiksd/recipe/transforms.py` (заменить заглушку `_aggregate`)
- Test: `tests/recipe/test_transforms.py` (добавить тесты)

- [ ] **Step 1: Дописать падающие тесты**

Добавить в конец `tests/recipe/test_transforms.py`:

```python
from analitiksd.recipe.models import AggregateOp, GroupByOp


def test_group_by_with_count_and_sum():
    t = [
        GroupByOp(op="group_by", keys=["manager"]),
        AggregateOp(op="aggregate", metrics=[
            {"fn": "count", "as": "deals"},
            {"fn": "sum", "field": "amount", "as": "total"}]),
    ]
    out = apply_transforms(ROWS, t)
    assert out == [
        {"manager": "A", "deals": 2, "total": 400},
        {"manager": "B", "deals": 1, "total": 200},
    ]


def test_aggregate_without_group_by_is_single_group():
    t = [AggregateOp(op="aggregate", metrics=[{"fn": "count", "as": "n"}])]
    out = apply_transforms(ROWS, t)
    assert out == [{"n": 3}]


def test_aggregate_avg_min_max():
    t = [AggregateOp(op="aggregate", metrics=[
        {"fn": "avg", "field": "amount", "as": "avg_amount"},
        {"fn": "min", "field": "amount", "as": "min_amount"},
        {"fn": "max", "field": "amount", "as": "max_amount"}])]
    out = apply_transforms(ROWS, t)
    assert out == [{"avg_amount": 200, "min_amount": 100, "max_amount": 300}]
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `pytest tests/recipe/test_transforms.py -k "group_by or aggregate" -v`
Expected: FAIL с `NotImplementedError`

- [ ] **Step 3: Реализовать `_aggregate`**

Заменить заглушку `_aggregate` в `src/analitiksd/recipe/transforms.py` на:

```python
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
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `pytest tests/recipe/test_transforms.py -v`
Expected: PASS (все тесты, включая прежние)

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/recipe/transforms.py tests/recipe/test_transforms.py
git commit -m "feat(recipe): add group_by and aggregate (count/sum/avg/min/max)"
```

---

## Task 6: Трансформации sort, computed, limit

**Files:**
- Modify: `src/analitiksd/recipe/transforms.py` (заменить заглушки `_sort`, `_computed`)
- Test: `tests/recipe/test_transforms.py` (добавить тесты)

- [ ] **Step 1: Дописать падающие тесты**

Добавить в конец `tests/recipe/test_transforms.py`:

```python
from analitiksd.recipe.models import ComputedOp, LimitOp, SortOp


def test_sort_desc_by_amount():
    t = [SortOp(op="sort", sort=[{"by": "amount", "dir": "desc"}])]
    out = apply_transforms(ROWS, t)
    assert [r["amount"] for r in out] == [300, 200, 100]


def test_sort_multi_key_stable():
    rows = [
        {"g": "A", "n": 2}, {"g": "B", "n": 1}, {"g": "A", "n": 1},
    ]
    t = [SortOp(op="sort", sort=[{"by": "g", "dir": "asc"}, {"by": "n", "dir": "asc"}])]
    out = apply_transforms(rows, t)
    assert out == [{"g": "A", "n": 1}, {"g": "A", "n": 2}, {"g": "B", "n": 1}]


def test_computed_division():
    rows = [{"a": 10, "b": 2}, {"a": 9, "b": 3}]
    t = [ComputedOp(op="computed", **{"as": "ratio"}, left="a", operator="/", right="b")]
    out = apply_transforms(rows, t)
    assert [r["ratio"] for r in out] == [5, 3]


def test_computed_division_by_zero_is_none():
    rows = [{"a": 10, "b": 0}]
    t = [ComputedOp(op="computed", **{"as": "ratio"}, left="a", operator="/", right="b")]
    out = apply_transforms(rows, t)
    assert out[0]["ratio"] is None


def test_computed_with_numeric_literal():
    rows = [{"a": 10}]
    t = [ComputedOp(op="computed", **{"as": "doubled"}, left="a", operator="*", right="2")]
    out = apply_transforms(rows, t)
    assert out[0]["doubled"] == 20


def test_limit():
    t = [LimitOp(op="limit", n=2)]
    out = apply_transforms(ROWS, t)
    assert [r["id"] for r in out] == [1, 2]
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `pytest tests/recipe/test_transforms.py -k "sort or computed or limit" -v`
Expected: FAIL с `NotImplementedError` (для sort и computed)

- [ ] **Step 3: Реализовать `_sort` и `_computed`**

Заменить заглушки `_sort` и `_computed` в `src/analitiksd/recipe/transforms.py` на:

```python
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
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `pytest tests/recipe/test_transforms.py -v`
Expected: PASS (все тесты)

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/recipe/transforms.py tests/recipe/test_transforms.py
git commit -m "feat(recipe): add sort, computed and limit transforms"
```

---

## Task 7: Сквозной конвейер и детерминизм

Проверяем пример из спеки целиком (вызов → подстановка параметров → трансформации) и гарантию детерминизма (один рецепт + одни данные = одинаковый результат дважды).

**Files:**
- Test: `tests/recipe/test_pipeline.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/recipe/test_pipeline.py
from analitiksd.recipe.models import Recipe
from analitiksd.recipe.params import resolve_params, substitute
from analitiksd.recipe.transforms import apply_transforms

RECIPE_RAW = {
    "version": 1,
    "source": "bitrix",
    "steps": [
        {"type": "tool_call", "tool": "crm_deal_list",
         "params": {"filter": {">=CLOSEDATE": "{{period.from}}",
                               "<=CLOSEDATE": "{{period.to}}", "CLOSED": "Y"},
                    "select": ["ID", "ASSIGNED_BY_ID", "OPPORTUNITY"]}}
    ],
    "transform": [
        {"op": "group_by", "keys": ["ASSIGNED_BY_ID"]},
        {"op": "aggregate", "metrics": [
            {"fn": "count", "as": "deals"},
            {"fn": "sum", "field": "OPPORTUNITY", "as": "amount"}]},
        {"op": "sort", "sort": [{"by": "amount", "dir": "desc"}]},
    ],
    "presentation": {"type": "table",
                     "columns": ["ASSIGNED_BY_ID", "deals", "amount"],
                     "sort": [{"by": "amount", "dir": "desc"}]},
}

PARAMS = {"period": {"type": "date_range",
                     "default": {"from": "2026-05-01", "to": "2026-05-31"}}}

# Имитация ответа источника (в следующих планах его отдаёт MCP-раннер):
SOURCE_ROWS = [
    {"ID": 1, "ASSIGNED_BY_ID": 10, "OPPORTUNITY": 100},
    {"ID": 2, "ASSIGNED_BY_ID": 20, "OPPORTUNITY": 500},
    {"ID": 3, "ASSIGNED_BY_ID": 10, "OPPORTUNITY": 300},
]


def test_param_substitution_into_steps():
    recipe = Recipe.model_validate(RECIPE_RAW)
    values = resolve_params(PARAMS, overrides=None)
    step = substitute(recipe.steps[0].model_dump(), values)
    assert step["params"]["filter"][">=CLOSEDATE"] == "2026-05-01"
    assert step["params"]["filter"]["<=CLOSEDATE"] == "2026-05-31"


def test_full_pipeline_produces_expected_report():
    recipe = Recipe.model_validate(RECIPE_RAW)
    out = apply_transforms(SOURCE_ROWS, recipe.transform)
    assert out == [
        {"ASSIGNED_BY_ID": 20, "deals": 1, "amount": 500},
        {"ASSIGNED_BY_ID": 10, "deals": 2, "amount": 400},
    ]


def test_pipeline_is_deterministic():
    recipe = Recipe.model_validate(RECIPE_RAW)
    first = apply_transforms(SOURCE_ROWS, recipe.transform)
    second = apply_transforms(SOURCE_ROWS, recipe.transform)
    assert first == second
```

- [ ] **Step 2: Запустить файл — это интеграционная проверка уже готовых модулей**

Run: `pytest tests/recipe/test_pipeline.py -v`
Expected: PASS (3 теста).

> Примечание: всё используемое здесь уже реализовано и протестировано в задачах 2–6, поэтому это сквозная (интеграционная) проверка их совместной работы — она должна пройти сразу. Если какой-то тест падает — это сигнал о реальной ошибке интеграции в движке: чинить движок, а не тест.

- [ ] **Step 3: Запустить весь набор тестов**

Run: `pytest`
Expected: PASS — все тесты пакета (models, params, transforms, pipeline).

- [ ] **Step 4: Коммит**

```bash
git add tests/recipe/test_pipeline.py
git commit -m "test(recipe): add end-to-end pipeline and determinism tests"
```

---

## Готовность плана

После выполнения всех задач есть: устанавливаемый пакет `analitiksd`, модель рецепта, подстановка параметров и детерминированный движок трансформаций, полностью покрытый тестами. Это фундамент для Плана 3 (Agent Service строит рецепт) и Плана 4 (Report Service исполняет рецепт при обновлении).

**Следующие планы:** План 2 (Auth + RBAC), План 3 (Agent Service + MCP), План 4 (Report Service + API), План 5 (React-фронтенд).
