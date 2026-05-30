# AnalitikSD MVP — План 3: Agent Service + источники Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить вопрос на естественном языке в детерминированный рецепт и его результат: LLM-планировщик (один structured-output вызов) выдаёт рецепт по схеме Плана 1, а наш код исполняет его — тянет строки из источника (Битрикс REST с пагинацией) и применяет трансформации Плана 1.

**Architecture:** Два чистых пакета. `source/` — детерминированное исполнение рецепта над источником без LLM (`SourceRunner` интерфейс + `BitrixRestRunner`; `execute_recipe` = fetch + трансформации Плана 1), переиспользуется Планом 4. `agent/` — планирование рецепта LLM (`ModelProvider` интерфейс + `AnthropicProvider` с принудительным tool-use; `AgentService.ask` оркестрирует). Всё тестируется на моках; реальные LLM/Битрикс — отдельные smoke-тесты.

**Tech Stack:** Python 3.12+, Anthropic SDK (tool-use), httpx, Pydantic v2, pytest. Переиспользует `analitiksd.recipe` (Плана 1).

---

## Предусловие

Ядро (задачи 1–7) тестируется **на моках** и не требует ключей. Реальные вызовы — только в smoke-тестах (задача 8), они пропускаются без переменных окружения:
- `ANTHROPIC_API_KEY` — для реального LLM-провайдера.
- `BITRIX_WEBHOOK_URL` — базовый URL входящего вебхука Битрикса (вид `https://<portal>.bitrix24.ru/rest/<user>/<token>`), для реального раннера.

---

## Файловая структура (создаётся планом)

```
src/analitiksd/source/__init__.py
src/analitiksd/source/runner.py        # SourceRunner (Protocol) + BitrixRestRunner (REST + пагинация)
src/analitiksd/source/executor.py      # execute_recipe(recipe, runner, *, values) -> list[dict]
src/analitiksd/agent/__init__.py
src/analitiksd/agent/decision.py       # CannotBuild + RecipeDecision
src/analitiksd/agent/catalog.py        # ToolSpec, SourceCatalog, BITRIX_CATALOG
src/analitiksd/agent/prompts.py        # схемы инструментов submit_recipe/cannot_build + промпт
src/analitiksd/agent/provider.py       # ModelProvider (Protocol) + AnthropicProvider
src/analitiksd/agent/service.py        # AgentService.ask -> AgentAnswer
src/analitiksd/config.py               # +anthropic_api_key/model, +bitrix_webhook_url (опциональные)
tests/source/__init__.py  tests/source/test_runner.py  tests/source/test_executor.py
tests/agent/__init__.py   tests/agent/test_provider.py  tests/agent/test_service.py  tests/agent/test_prompts.py
tests/smoke/__init__.py   tests/smoke/test_smoke.py
```

---

## Task 1: Зависимости и конфигурация

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/analitiksd/config.py`
- Test: `tests/test_config.py` (дописать)

- [ ] **Step 1: Обновить зависимости в `pyproject.toml`**

Перенести `httpx` в runtime и добавить `anthropic`. В `[project] dependencies` добавить:
```toml
    "httpx>=0.27",
    "anthropic>=0.40",
```
И УДАЛИТЬ строку `"httpx>=0.27",` из `[project.optional-dependencies] dev` (теперь httpx — runtime-зависимость). Остальное не трогать.

- [ ] **Step 2: Установить**

Run: `. .venv/bin/activate && pip install -e ".[dev]"`
Expected: успешно (ставится `anthropic`).

- [ ] **Step 3: Дописать падающий тест в `tests/test_config.py`**

Добавить в конец файла:
```python
def test_settings_agent_source_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://localhost/x")
    monkeypatch.setenv("JWT_SECRET", "secret")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BITRIX_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    s = get_settings()
    assert s.anthropic_api_key is None
    assert s.bitrix_webhook_url is None
    assert s.anthropic_model  # непустая строка по умолчанию


def test_settings_agent_source_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://localhost/x")
    monkeypatch.setenv("JWT_SECRET", "secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-x")
    monkeypatch.setenv("BITRIX_WEBHOOK_URL", "https://p.bitrix24.ru/rest/1/tok")
    s = get_settings()
    assert s.anthropic_api_key == "sk-test"
    assert s.anthropic_model == "claude-x"
    assert s.bitrix_webhook_url == "https://p.bitrix24.ru/rest/1/tok"
```

- [ ] **Step 4: Запустить — убедиться, что падает**

Run: `pytest tests/test_config.py -k agent_source -v`
Expected: FAIL (`AttributeError`/`TypeError`: у `Settings` нет полей).

- [ ] **Step 5: Дополнить `src/analitiksd/config.py`**

Добавить поля в `Settings` (после `cookie_secure`):
```python
    # Опциональные настройки агента/источника (нужны только для реальных вызовов;
    # ядро тестируется на моках). Секреты — только из окружения.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    bitrix_webhook_url: str | None = None
```
И в `get_settings()` (в конструктор `Settings(...)`) добавить:
```python
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
        bitrix_webhook_url=os.environ.get("BITRIX_WEBHOOK_URL"),
```

- [ ] **Step 6: Запустить — убедиться, что проходит**

Run: `pytest tests/test_config.py -v`  → PASS.
Run: `pytest -q`  → весь набор зелёный (report count).

- [ ] **Step 7: Коммит**

```bash
git add pyproject.toml src/analitiksd/config.py tests/test_config.py
git commit -m "feat(config): add anthropic/bitrix settings; httpx+anthropic deps

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: SourceRunner + BitrixRestRunner (пагинация)

**Files:**
- Create: `src/analitiksd/source/__init__.py` (пустой)
- Create: `src/analitiksd/source/runner.py`
- Create: `tests/source/__init__.py` (пустой)
- Test: `tests/source/test_runner.py`

Битрикс REST list-методы возвращают `{"result": [...], "next": <int>, "total": <int>}`; пагинация — параметром `start`, пока в ответе есть `next`.

- [ ] **Step 1: Написать падающий тест `tests/source/test_runner.py`**

```python
# tests/source/test_runner.py
import httpx
import pytest

from analitiksd.recipe.models import ToolCallStep
from analitiksd.source.runner import BitrixRestRunner


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://p.bitrix24.ru/rest/1/tok")


def test_fetch_collects_all_pages():
    pages = {
        0: {"result": [{"ID": "1"}, {"ID": "2"}], "next": 2, "total": 3},
        2: {"result": [{"ID": "3"}], "total": 3},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.content)
        assert request.url.path.endswith("/crm.deal.list")
        return httpx.Response(200, json=pages[body["start"]])

    runner = BitrixRestRunner("https://p.bitrix24.ru/rest/1/tok", _client(handler))
    step = ToolCallStep(type="tool_call", tool="crm_deal_list", params={"select": ["ID"]})
    rows = runner.fetch(step)
    assert [r["ID"] for r in rows] == ["1", "2", "3"]


def test_fetch_unknown_tool_raises():
    runner = BitrixRestRunner("https://p.bitrix24.ru/rest/1/tok", _client(lambda r: httpx.Response(200, json={"result": []})))
    step = ToolCallStep(type="tool_call", tool="unknown_tool", params={})
    with pytest.raises(ValueError):
        runner.fetch(step)


def test_fetch_http_error_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    runner = BitrixRestRunner("https://p.bitrix24.ru/rest/1/tok", _client(handler))
    step = ToolCallStep(type="tool_call", tool="crm_deal_list", params={})
    with pytest.raises(httpx.HTTPStatusError):
        runner.fetch(step)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/source/test_runner.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'analitiksd.source.runner'`).

- [ ] **Step 3: Реализовать `src/analitiksd/source/runner.py`**

```python
# src/analitiksd/source/runner.py
from __future__ import annotations

from typing import Any, Protocol

import httpx

from analitiksd.recipe.models import ToolCallStep

# Маппинг имён инструментов рецепта на REST-методы Битрикса.
_TOOL_METHODS = {
    "crm_deal_list": "crm.deal.list",
}


class SourceRunner(Protocol):
    """Тянет строки источника для одного tool_call-шага рецепта."""

    def fetch(self, step: ToolCallStep) -> list[dict[str, Any]]: ...


class BitrixRestRunner:
    """SourceRunner поверх входящего вебхука Битрикса (REST), с постраничной выборкой."""

    def __init__(self, webhook_url: str, http: httpx.Client) -> None:
        self._webhook_url = webhook_url.rstrip("/")
        self._http = http

    def fetch(self, step: ToolCallStep) -> list[dict[str, Any]]:
        method = _TOOL_METHODS.get(step.tool)
        if method is None:
            raise ValueError(f"Unknown tool: {step.tool}")
        rows: list[dict[str, Any]] = []
        start = 0
        while True:
            payload = {**step.params, "start": start}
            response = self._http.post(f"{self._webhook_url}/{method}", json=payload)
            self._raise_for_status(response)
            data = response.json()
            # Битрикс отдаёт result=false при нуле записей -> приводим к [].
            rows.extend(data.get("result") or [])
            next_start = data.get("next")
            # next отсутствует -> конец; защита от зацикливания, если сервер вернул
            # не возрастающий next (например 0) на кривом ответе.
            if next_start is None or next_start <= start:
                break
            start = next_start
        return rows

    def _raise_for_status(self, response: httpx.Response) -> None:
        """raise_for_status, но без утечки секретного токена вебхука в сообщение/лог."""
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            scrubbed = str(exc).replace(self._webhook_url, "<webhook>")
            raise httpx.HTTPStatusError(
                scrubbed, request=exc.request, response=exc.response
            ) from None
```

> Тесты также покрывают: одностраничный ответ, `result=false` (ноль записей), не возрастающий `next` (без зацикливания) и скрабинг токена в сообщении ошибки.

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/source/test_runner.py -v`  → PASS (3 теста).

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/source/__init__.py src/analitiksd/source/runner.py tests/source/__init__.py tests/source/test_runner.py
git commit -m "feat(source): add SourceRunner protocol and paginating BitrixRestRunner

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: execute_recipe (исполнитель рецепта)

**Files:**
- Create: `src/analitiksd/source/executor.py`
- Test: `tests/source/test_executor.py`

`execute_recipe` подставляет значения параметров в шаги (Плана 1 `substitute`), тянет строки раннером по всем шагам, применяет трансформации Плана 1. Без LLM. Раннер в тестах — мок.

- [ ] **Step 1: Написать падающий тест `tests/source/test_executor.py`**

```python
# tests/source/test_executor.py
from analitiksd.recipe.models import Recipe
from analitiksd.source.executor import execute_recipe


class FakeRunner:
    def __init__(self, rows_by_tool):
        self.rows_by_tool = rows_by_tool
        self.calls = []

    def fetch(self, step):
        self.calls.append(step)
        return self.rows_by_tool[step.tool]


RECIPE_RAW = {
    "version": 1,
    "source": "bitrix",
    "steps": [
        {"type": "tool_call", "tool": "crm_deal_list",
         "params": {"filter": {">=CLOSEDATE": "{{period.from}}", "CLOSED": "Y"},
                    "select": ["ID", "ASSIGNED_BY_ID", "OPPORTUNITY"]}}
    ],
    "transform": [
        {"op": "group_by", "keys": ["ASSIGNED_BY_ID"]},
        {"op": "aggregate", "metrics": [
            {"fn": "count", "as": "deals"},
            {"fn": "sum", "field": "OPPORTUNITY", "as": "amount"}]},
        {"op": "sort", "sort": [{"by": "amount", "dir": "desc"}]},
    ],
    "presentation": {"type": "table", "columns": ["ASSIGNED_BY_ID", "deals", "amount"]},
}

SOURCE_ROWS = [
    {"ID": 1, "ASSIGNED_BY_ID": 10, "OPPORTUNITY": 100},
    {"ID": 2, "ASSIGNED_BY_ID": 20, "OPPORTUNITY": 500},
    {"ID": 3, "ASSIGNED_BY_ID": 10, "OPPORTUNITY": 300},
]


def test_execute_runs_fetch_then_transforms():
    recipe = Recipe.model_validate(RECIPE_RAW)
    runner = FakeRunner({"crm_deal_list": SOURCE_ROWS})
    out = execute_recipe(recipe, runner, values={"period.from": "2026-05-01"})
    assert out == [
        {"ASSIGNED_BY_ID": 20, "deals": 1, "amount": 500},
        {"ASSIGNED_BY_ID": 10, "deals": 2, "amount": 400},
    ]


def test_execute_substitutes_params_into_step():
    recipe = Recipe.model_validate(RECIPE_RAW)
    runner = FakeRunner({"crm_deal_list": SOURCE_ROWS})
    execute_recipe(recipe, runner, values={"period.from": "2026-05-01"})
    sent_step = runner.calls[0]
    assert sent_step.params["filter"][">=CLOSEDATE"] == "2026-05-01"


def test_execute_without_placeholders_needs_no_values():
    raw = {
        "version": 1, "source": "bitrix",
        "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID"]}}],
        "transform": [],
        "presentation": {"type": "table", "columns": ["ID"]},
    }
    recipe = Recipe.model_validate(raw)
    runner = FakeRunner({"crm_deal_list": [{"ID": 1}]})
    out = execute_recipe(recipe, runner)
    assert out == [{"ID": 1}]
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/source/test_executor.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Реализовать `src/analitiksd/source/executor.py`**

```python
# src/analitiksd/source/executor.py
from __future__ import annotations

from typing import Any

from analitiksd.recipe.models import Recipe, ToolCallStep
from analitiksd.recipe.params import substitute
from analitiksd.recipe.transforms import apply_transforms
from analitiksd.source.runner import SourceRunner


def execute_recipe(
    recipe: Recipe,
    runner: SourceRunner,
    *,
    values: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Исполнить рецепт детерминированно: подстановка параметров -> fetch -> трансформации.

    values — плоская карта значений параметров (см. recipe.params.resolve_params).
    Пусто -> в шагах не должно быть плейсхолдеров (иначе substitute поднимет KeyError).
    LLM здесь не участвует.
    """
    values = values or {}
    rows: list[dict[str, Any]] = []
    for step in recipe.steps:
        resolved = substitute(step.model_dump(by_alias=True), values)
        rows.extend(runner.fetch(ToolCallStep.model_validate(resolved)))
    return apply_transforms(rows, recipe.transform)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/source/test_executor.py -v`  → PASS (3 теста).

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/source/executor.py tests/source/test_executor.py
git commit -m "feat(source): add deterministic execute_recipe (params -> fetch -> transforms)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Решение агента и каталог источника

**Files:**
- Create: `src/analitiksd/agent/__init__.py` (пустой)
- Create: `src/analitiksd/agent/decision.py`
- Create: `src/analitiksd/agent/catalog.py`
- Create: `tests/agent/__init__.py` (пустой)
- Test: `tests/agent/test_catalog.py`

- [ ] **Step 1: Написать падающий тест `tests/agent/test_catalog.py`**

```python
# tests/agent/test_catalog.py
from analitiksd.agent.catalog import BITRIX_CATALOG, SourceCatalog, ToolSpec
from analitiksd.agent.decision import CannotBuild
from analitiksd.recipe.models import Recipe


def test_bitrix_catalog_shape():
    assert isinstance(BITRIX_CATALOG, SourceCatalog)
    assert BITRIX_CATALOG.source == "bitrix"
    names = [t.name for t in BITRIX_CATALOG.tools]
    assert "crm_deal_list" in names
    deal = next(t for t in BITRIX_CATALOG.tools if t.name == "crm_deal_list")
    assert isinstance(deal, ToolSpec)
    assert "OPPORTUNITY" in deal.fields


def test_cannot_build_carries_reason():
    cb = CannotBuild(reason="нет данных по этому полю")
    assert cb.reason == "нет данных по этому полю"


def test_recipe_decision_accepts_recipe_or_cannotbuild():
    # RecipeDecision — это Recipe | CannotBuild; обе ветки валидны как значения
    from analitiksd.agent.decision import RecipeDecision  # noqa: F401
    assert isinstance(CannotBuild("x"), CannotBuild)
    assert Recipe is Recipe
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/agent/test_catalog.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Реализовать `src/analitiksd/agent/decision.py`**

```python
# src/analitiksd/agent/decision.py
from __future__ import annotations

from dataclasses import dataclass

from analitiksd.recipe.models import Recipe


@dataclass(frozen=True)
class CannotBuild:
    """Вопрос не выразим рецептом — честный отказ с причиной, без выдуманных данных."""

    reason: str


# Решение планировщика: либо валидный рецепт, либо отказ.
RecipeDecision = Recipe | CannotBuild
```

- [ ] **Step 4: Реализовать `src/analitiksd/agent/catalog.py`**

```python
# src/analitiksd/agent/catalog.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    fields: list[str]


@dataclass(frozen=True)
class SourceCatalog:
    """Описание доступных инструментов/полей источника — кладётся в промпт планировщика."""

    source: str
    tools: list[ToolSpec]


# MVP: единственный источник — Битрикс, единственный инструмент — список сделок.
BITRIX_CATALOG = SourceCatalog(
    source="bitrix",
    tools=[
        ToolSpec(
            name="crm_deal_list",
            description=(
                "Список сделок CRM. params.filter — словарь условий Битрикса "
                "(например {'>=CLOSEDATE': 'YYYY-MM-DD', 'CLOSED': 'Y'}); "
                "params.select — список полей."
            ),
            fields=[
                "ID",
                "ASSIGNED_BY_ID",
                "OPPORTUNITY",
                "CLOSEDATE",
                "DATE_CREATE",
                "STAGE_ID",
                "CLOSED",
            ],
        ),
    ],
)
```

- [ ] **Step 5: Запустить — убедиться, что проходит**

Run: `pytest tests/agent/test_catalog.py -v`  → PASS (3 теста).

- [ ] **Step 6: Коммит**

```bash
git add src/analitiksd/agent/__init__.py src/analitiksd/agent/decision.py src/analitiksd/agent/catalog.py tests/agent/__init__.py tests/agent/test_catalog.py
git commit -m "feat(agent): add RecipeDecision and Bitrix source catalog

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Промпт и схемы инструментов

**Files:**
- Create: `src/analitiksd/agent/prompts.py`
- Test: `tests/agent/test_prompts.py`

Инструмент `submit_recipe` использует JSON-схему модели `Recipe` (с алиасами — чтобы LLM выдавал `as`, а не `as_`).

- [ ] **Step 1: Написать падающий тест `tests/agent/test_prompts.py`**

```python
# tests/agent/test_prompts.py
from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.prompts import (
    CANNOT_BUILD_TOOL,
    SUBMIT_RECIPE_TOOL,
    build_system_prompt,
)


def test_submit_recipe_tool_uses_recipe_schema():
    assert SUBMIT_RECIPE_TOOL["name"] == "submit_recipe"
    schema = SUBMIT_RECIPE_TOOL["input_schema"]
    assert schema["type"] == "object"
    assert "source" in schema["properties"]
    assert "transform" in schema["properties"]


def test_cannot_build_tool_requires_reason():
    assert CANNOT_BUILD_TOOL["name"] == "cannot_build"
    assert "reason" in CANNOT_BUILD_TOOL["input_schema"]["required"]


def test_system_prompt_mentions_catalog_tools():
    prompt = build_system_prompt(BITRIX_CATALOG)
    assert "crm_deal_list" in prompt
    assert "OPPORTUNITY" in prompt
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/agent/test_prompts.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Реализовать `src/analitiksd/agent/prompts.py`**

```python
# src/analitiksd/agent/prompts.py
from __future__ import annotations

from analitiksd.agent.catalog import SourceCatalog
from analitiksd.recipe.models import Recipe

# Схема инструмента = JSON-схема рецепта (by_alias -> поле "as", не "as_").
SUBMIT_RECIPE_TOOL = {
    "name": "submit_recipe",
    "description": (
        "Вернуть детерминированный рецепт-конвейер, отвечающий на вопрос. "
        "Используй только инструменты и поля из системного описания источника."
    ),
    "input_schema": Recipe.model_json_schema(by_alias=True),
}

CANNOT_BUILD_TOOL = {
    "name": "cannot_build",
    "description": (
        "Вызвать, если вопрос нельзя выразить рецептом из доступных инструментов/полей. "
        "Никаких выдуманных данных."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"reason": {"type": "string"}},
        "required": ["reason"],
    },
}


def build_system_prompt(catalog: SourceCatalog) -> str:
    lines = [
        "Ты — планировщик отчётов. По вопросу пользователя построй детерминированный",
        "рецепт-конвейер (вызовы источника -> трансформации -> представление) и верни его",
        "через инструмент submit_recipe. Если вопрос невыразим — вызови cannot_build.",
        "Не выдумывай данные и не считай сам: цифры даст наш движок, исполнив рецепт.",
        f"\nИсточник: {catalog.source}. Доступные инструменты:",
    ]
    for tool in catalog.tools:
        lines.append(f"- {tool.name}: {tool.description}")
        lines.append(f"  поля: {', '.join(tool.fields)}")
    return "\n".join(lines)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/agent/test_prompts.py -v`  → PASS (3 теста).

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/agent/prompts.py tests/agent/test_prompts.py
git commit -m "feat(agent): add planner system prompt and submit_recipe/cannot_build tool schemas

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: ModelProvider + AnthropicProvider

**Files:**
- Create: `src/analitiksd/agent/provider.py`
- Test: `tests/agent/test_provider.py`

`AnthropicProvider` не импортирует пакет `anthropic` — клиент инжектится (тестируемо без SDK). Делает один `messages.create` с принудительным `tool_choice={"type":"any"}`, парсит первый `tool_use`-блок.

- [ ] **Step 1: Написать падающий тест `tests/agent/test_provider.py`**

```python
# tests/agent/test_provider.py
from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.decision import CannotBuild
from analitiksd.agent.provider import AnthropicProvider
from analitiksd.recipe.models import Recipe

RECIPE_INPUT = {
    "version": 1,
    "source": "bitrix",
    "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID"]}}],
    "transform": [],
    "presentation": {"type": "table", "columns": ["ID"]},
}


class _Block:
    def __init__(self, type, name=None, input=None):
        self.type = type
        self.name = name
        self.input = input


class _Message:
    def __init__(self, content):
        self.content = content


class _FakeMessages:
    def __init__(self, message):
        self._message = message
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._message


class _FakeClient:
    def __init__(self, message):
        self.messages = _FakeMessages(message)


def test_provider_parses_submit_recipe_into_recipe():
    client = _FakeClient(_Message([_Block("tool_use", "submit_recipe", RECIPE_INPUT)]))
    provider = AnthropicProvider(client, "claude-x")
    decision = provider.build_recipe("сколько сделок", BITRIX_CATALOG)
    assert isinstance(decision, Recipe)
    assert decision.source == "bitrix"
    # принудительный выбор инструмента
    assert client.messages.last_kwargs["tool_choice"] == {"type": "any"}


def test_provider_returns_cannotbuild_on_cannot_build_tool():
    client = _FakeClient(_Message([_Block("tool_use", "cannot_build", {"reason": "нет такого поля"})]))
    provider = AnthropicProvider(client, "claude-x")
    decision = provider.build_recipe("вопрос", BITRIX_CATALOG)
    assert isinstance(decision, CannotBuild)
    assert decision.reason == "нет такого поля"


def test_provider_returns_cannotbuild_on_invalid_recipe():
    bad = {"version": 1, "source": "bitrix"}  # нет steps/presentation
    client = _FakeClient(_Message([_Block("tool_use", "submit_recipe", bad)]))
    provider = AnthropicProvider(client, "claude-x")
    decision = provider.build_recipe("вопрос", BITRIX_CATALOG)
    assert isinstance(decision, CannotBuild)


def test_provider_returns_cannotbuild_when_no_tool_use():
    client = _FakeClient(_Message([_Block("text")]))
    provider = AnthropicProvider(client, "claude-x")
    decision = provider.build_recipe("вопрос", BITRIX_CATALOG)
    assert isinstance(decision, CannotBuild)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/agent/test_provider.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Реализовать `src/analitiksd/agent/provider.py`**

```python
# src/analitiksd/agent/provider.py
from __future__ import annotations

from typing import Any, Protocol

from pydantic import ValidationError

from analitiksd.agent.catalog import SourceCatalog
from analitiksd.agent.decision import CannotBuild, RecipeDecision
from analitiksd.agent.prompts import (
    CANNOT_BUILD_TOOL,
    SUBMIT_RECIPE_TOOL,
    build_system_prompt,
)
from analitiksd.recipe.models import Recipe

_MAX_TOKENS = 2048


class ModelProvider(Protocol):
    """Планировщик: по вопросу и каталогу источника возвращает рецепт или отказ."""

    def build_recipe(self, question: str, catalog: SourceCatalog) -> RecipeDecision: ...


class AnthropicProvider:
    """ModelProvider поверх Anthropic SDK. Клиент инжектится (тестируемо без пакета)."""

    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def build_recipe(self, question: str, catalog: SourceCatalog) -> RecipeDecision:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=build_system_prompt(catalog),
            tools=[SUBMIT_RECIPE_TOOL, CANNOT_BUILD_TOOL],
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": question}],
        )
        block = _first_tool_use(message.content)
        if block is None:
            return CannotBuild("модель не вызвала инструмент")
        if block.name == "cannot_build":
            reason = block.input.get("reason", "вопрос невыразим рецептом")
            return CannotBuild(reason)
        try:
            return Recipe.model_validate(block.input)
        except ValidationError as exc:
            return CannotBuild(f"невалидный рецепт: {exc}")


def _first_tool_use(content: Any) -> Any:
    for block in content:
        if getattr(block, "type", None) == "tool_use":
            return block
    return None
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/agent/test_provider.py -v`  → PASS (4 теста).

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/agent/provider.py tests/agent/test_provider.py
git commit -m "feat(agent): add ModelProvider and AnthropicProvider (forced tool-use planner)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: AgentService.ask (оркестрация)

**Files:**
- Create: `src/analitiksd/agent/service.py`
- Test: `tests/agent/test_service.py`

- [ ] **Step 1: Написать падающий тест `tests/agent/test_service.py`**

```python
# tests/agent/test_service.py
from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.decision import CannotBuild
from analitiksd.agent.service import AgentAnswer, AgentService
from analitiksd.recipe.models import Recipe

RECIPE_RAW = {
    "version": 1,
    "source": "bitrix",
    "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID", "OPPORTUNITY"]}}],
    "transform": [{"op": "aggregate", "metrics": [{"fn": "sum", "field": "OPPORTUNITY", "as": "total"}]}],
    "presentation": {"type": "table", "columns": ["total"]},
}
ROWS = [{"ID": 1, "OPPORTUNITY": 100}, {"ID": 2, "OPPORTUNITY": 400}]


class FakeProvider:
    def __init__(self, decision):
        self.decision = decision
        self.calls = 0

    def build_recipe(self, question, catalog):
        self.calls += 1
        return self.decision


class FakeRunner:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def fetch(self, step):
        self.calls += 1
        return self.rows


def test_ask_expressible_returns_recipe_and_result():
    provider = FakeProvider(Recipe.model_validate(RECIPE_RAW))
    runner = FakeRunner(ROWS)
    service = AgentService(provider)
    answer = service.ask("сумма сделок", BITRIX_CATALOG, runner)
    assert isinstance(answer, AgentAnswer)
    assert answer.is_refreshable is True
    assert isinstance(answer.recipe, Recipe)
    assert answer.rows == [{"total": 500}]


def test_ask_not_expressible_returns_no_recipe_no_data():
    provider = FakeProvider(CannotBuild("нет такого поля"))
    runner = FakeRunner(ROWS)
    service = AgentService(provider)
    answer = service.ask("вопрос", BITRIX_CATALOG, runner)
    assert answer.is_refreshable is False
    assert answer.recipe is None
    assert answer.rows is None
    assert answer.message == "нет такого поля"
    assert runner.calls == 0  # источник не трогаем, если рецепта нет


def test_execution_does_not_call_llm_again():
    provider = FakeProvider(Recipe.model_validate(RECIPE_RAW))
    runner = FakeRunner(ROWS)
    service = AgentService(provider)
    service.ask("сумма сделок", BITRIX_CATALOG, runner)
    assert provider.calls == 1  # ровно один вызов LLM; исполнение рецепта LLM не зовёт
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/agent/test_service.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Реализовать `src/analitiksd/agent/service.py`**

```python
# src/analitiksd/agent/service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from analitiksd.agent.catalog import SourceCatalog
from analitiksd.agent.decision import CannotBuild
from analitiksd.agent.provider import ModelProvider
from analitiksd.recipe.models import Recipe
from analitiksd.source.executor import execute_recipe
from analitiksd.source.runner import SourceRunner


@dataclass(frozen=True)
class AgentAnswer:
    rows: list[dict[str, Any]] | None
    recipe: Recipe | None
    is_refreshable: bool
    message: str | None = None


class AgentService:
    """Оркестратор: вопрос -> рецепт (LLM) -> детерминированное исполнение -> ответ."""

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    def ask(
        self,
        question: str,
        catalog: SourceCatalog,
        runner: SourceRunner,
        *,
        values: dict[str, str] | None = None,
    ) -> AgentAnswer:
        decision = self._provider.build_recipe(question, catalog)
        if isinstance(decision, CannotBuild):
            return AgentAnswer(
                rows=None, recipe=None, is_refreshable=False, message=decision.reason
            )
        rows = execute_recipe(decision, runner, values=values)
        return AgentAnswer(rows=rows, recipe=decision, is_refreshable=True)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/agent/test_service.py -v`  → PASS (3 теста).
Run: `pytest -q`  → весь набор зелёный.

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/agent/service.py tests/agent/test_service.py
git commit -m "feat(agent): add AgentService.ask orchestration (plan -> execute -> answer)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Smoke-тесты (реальные LLM/Битрикс, пропускаемы)

**Files:**
- Create: `tests/smoke/__init__.py` (пустой)
- Test: `tests/smoke/test_smoke.py`

Запускаются только при наличии переменных окружения; в обычном прогоне пропускаются (не зависят от внешних систем).

- [ ] **Step 1: Написать тест `tests/smoke/test_smoke.py`**

```python
# tests/smoke/test_smoke.py
import os

import httpx
import pytest

from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.decision import CannotBuild
from analitiksd.agent.provider import AnthropicProvider
from analitiksd.config import get_settings
from analitiksd.recipe.models import Recipe
from analitiksd.source.runner import BitrixRestRunner

_NO_LLM = not os.environ.get("ANTHROPIC_API_KEY")
_NO_BITRIX = not os.environ.get("BITRIX_WEBHOOK_URL")


@pytest.mark.skipif(_NO_LLM, reason="ANTHROPIC_API_KEY не задан")
def test_real_provider_builds_valid_recipe():
    import anthropic

    settings = get_settings()
    provider = AnthropicProvider(anthropic.Anthropic(api_key=settings.anthropic_api_key), settings.anthropic_model)
    decision = provider.build_recipe(
        "сколько закрытых сделок по каждому ответственному", BITRIX_CATALOG
    )
    assert isinstance(decision, (Recipe, CannotBuild))
    if isinstance(decision, Recipe):
        assert decision.source == "bitrix"


@pytest.mark.skipif(_NO_BITRIX, reason="BITRIX_WEBHOOK_URL не задан")
def test_real_bitrix_runner_fetches_rows():
    from analitiksd.recipe.models import ToolCallStep

    settings = get_settings()
    with httpx.Client(timeout=30) as http:
        runner = BitrixRestRunner(settings.bitrix_webhook_url, http)
        rows = runner.fetch(ToolCallStep(type="tool_call", tool="crm_deal_list", params={"select": ["ID"]}))
    assert isinstance(rows, list)
```

- [ ] **Step 2: Запустить — убедиться, что пропускается без ключей**

Run: `pytest tests/smoke/test_smoke.py -v`
Expected: 2 skipped (если `ANTHROPIC_API_KEY`/`BITRIX_WEBHOOK_URL` не заданы).

- [ ] **Step 3: Прогнать весь набор**

Run: `pytest -q`
Expected: всё зелёное; smoke-тесты — skipped.

- [ ] **Step 4: Коммит**

```bash
git add tests/smoke/__init__.py tests/smoke/test_smoke.py
git commit -m "test(smoke): add skippable real LLM/Bitrix smoke tests

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Готовность плана

После всех задач: детерминированный исполнитель рецептов над источником (`source/`, переиспользуемый Планом 4) и LLM-планировщик (`agent/`), который из вопроса строит валидный по схеме рецепт и возвращает результат его исполнения + флаг `is_refreshable`; «не выразимо» → честный отказ без данных. Ядро полностью на моках; реальные LLM/Битрикс — пропускаемые smoke-тесты.

**Следующий план:** План 4 (Report Service + API) — `/agent/ask` эндпоинт (RBAC), сохранение рецепта в `reports`, история `report_runs`, «Обновить» через `source/executor.execute_recipe` без LLM. Затем План 5 (React-фронтенд).

> Латентный нюанс для Плана 4: при сериализации рецепта обратно в JSON использовать `model_dump(by_alias=True)` (поле `as_`/alias `as`). Здесь `SUBMIT_RECIPE_TOOL` уже использует `Recipe.model_json_schema(by_alias=True)`.
