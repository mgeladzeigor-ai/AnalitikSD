# AnalitikSD — План 3: Agent Service + источники (дизайн-дополнение)

**Дата:** 2026-05-30
**Статус:** дизайн утверждён (решения делегированы исполнителю)
**Базовый документ:** [`2026-05-29-analitiksd-platform-design.md`](2026-05-29-analitiksd-platform-design.md), разделы 4–8. Здесь детализируется срез «вопрос → рецепт → результат».

## 1. Цель среза

Превратить вопрос на естественном языке в **детерминированный рецепт** и его результат: LLM выступает *планировщиком* (за один structured-output вызов выдаёт рецепт по схеме Pydantic из Плана 1), а наш код исполняет рецепт — тянет строки из источника и применяет трансформации Плана 1. Пользователь видит **результат конвейера**, а не свободный текст LLM (гарантия детерминизма из спеки). Если вопрос не выразим рецептом — честный ad-hoc-ответ без кнопки «Сохранить» и без выдуманных цифр.

## 2. Закрытые проектные развилки

| Тема | Решение | Почему |
|------|---------|--------|
| Как агент строит рецепт | **Планировщик**: один вызов LLM с принудительным tool-use (`submit_recipe` / `cannot_build`); вход инструмента = JSON-схема `Recipe` | Дёшево, тестируемо, детерминированно; результат = исполнение рецепта движком, а не пересказ LLM |
| Доступ к источнику | Интерфейс **`SourceRunner`**; реализация для Битрикса — прямой REST-webhook с пагинацией | Меньше движущихся частей, чем MCP-сервер в бэкенде; то же, что MCP делает внутри; легко мокается. MCP-клиент — альтернативная реализация того же интерфейса |
| LLM-провайдер | Интерфейс **`ModelProvider`**; одна реализация — `AnthropicProvider` (Anthropic SDK) | Задел под мульти-модельность за тонким интерфейсом (спека) |
| «Не выразимо» | Провайдер возвращает решение `cannot_build(reason)` → ответ помечается `is_refreshable=False`, рецепта нет, данные не выдумываются | Честнее, чем сохранить нерабочий рецепт (гарантия 2 спеки) |
| Scope | Ядро агента + источники, **без HTTP**; всё на моках | HTTP-эндпоинт `/agent/ask` и сохранение (`reports`) — План 4 |
| Тесты | Ядро — на моках (mock provider, mock runner); реальные LLM/Битрикс — отдельные smoke-тесты (пропускаются без ключа/вебхука) | Принцип спеки: ядро тщательно, LLM/внешнее — на моках |

## 3. Файловая структура (добавляется планом)

```
src/analitiksd/source/__init__.py
src/analitiksd/source/runner.py        # SourceRunner (Protocol) + BitrixRestRunner (REST + пагинация)
src/analitiksd/source/executor.py      # execute_recipe(recipe, runner, overrides) -> list[dict]
src/analitiksd/agent/__init__.py
src/analitiksd/agent/catalog.py        # описание источника (инструменты/поля Битрикса) для LLM
src/analitiksd/agent/decision.py       # RecipeDecision: Recipe | CannotBuild(reason)
src/analitiksd/agent/provider.py       # ModelProvider (Protocol) + AnthropicProvider
src/analitiksd/agent/prompts.py        # системный промпт + JSON-схема инструмента submit_recipe
src/analitiksd/agent/service.py        # AgentService.ask(...) -> AgentAnswer
src/analitiksd/config.py               # +ANTHROPIC_API_KEY, +BITRIX_WEBHOOK_URL (опциональные)
tests/source/, tests/agent/            # юнит/интеграционные на моках; smoke помечены и пропускаемы
```

**Разделение ответственности:** `source/` — детерминированное исполнение рецепта над источником (без LLM), переиспользуется Планом 4 для «Обновить». `agent/` — планирование рецепта LLM. Границы чистые: `executor` зависит от `SourceRunner` (интерфейс) и движка Плана 1; `service` — от `ModelProvider` и `executor`.

## 4. Поток данных (ad-hoc вопрос)

1. `AgentService.ask(question, catalog, runner, params=None)`.
2. `provider.build_recipe(question, catalog)` → `RecipeDecision`:
   - **Recipe** (валиден по схеме Pydantic Плана 1) — выразимо;
   - **CannotBuild(reason)** — не выразимо.
3. Если Recipe → `execute_recipe(recipe, runner, overrides=params)`:
   - `resolve_params` + `substitute` подставляют период в `steps` (Плана 1, `params.py`);
   - для каждого `tool_call`-шага `runner.fetch(step)` тянет **все страницы** → `list[dict]`;
   - `apply_transforms(rows, recipe.transform)` (Плана 1) → итоговые строки.
   - Возврат `AgentAnswer(rows=..., recipe=recipe, is_refreshable=True)`.
4. Если CannotBuild → `AgentAnswer(rows=None, recipe=None, is_refreshable=False, message=reason)`. **Без выдуманных данных.**

`AgentAnswer` — простая dataclass: `rows: list[dict] | None`, `recipe: Recipe | None`, `is_refreshable: bool`, `message: str | None`.

## 5. Интерфейсы (контуры)

- `SourceRunner` (Protocol): `fetch(step: ToolCallStep) -> list[dict]`. Реализует пагинацию и нормализацию ответа источника в плоские строки. `BitrixRestRunner(webhook_url, http_client)` — маппит `tool` (`crm_deal_list`) на REST-метод (`crm.deal.list`), гоняет `start`-пагинацию до конца.
- `ModelProvider` (Protocol): `build_recipe(question: str, catalog: SourceCatalog) -> RecipeDecision`. `AnthropicProvider(client, model)` — один `messages.create` с `tools=[submit_recipe, cannot_build]`, `tool_choice` принудительный; парсит tool-use вход в `Recipe`/`CannotBuild`.
- `SourceCatalog` — статическое описание доступных инструментов и полей источника (для MVP — Битрикс: `crm_deal_list` с полями ID/ASSIGNED_BY_ID/OPPORTUNITY/CLOSEDATE/STAGE_ID и т.п.), которое кладётся в промпт.

## 6. Обработка ошибок (раздел 7 спеки)

- **Источник недоступен / таймаут / rate-limit** → `SourceRunner` поднимает понятную ошибку; ретраи с экспоненциальной задержкой на сетевые/limit (не на логические). На уровне `ask` — пробрасывается как ошибка выполнения (в Плане 4 пишется в `report_runs`).
- **LLM не смог построить** → `CannotBuild`, без выдуманных цифр.
- **Рецепт не прошёл схему** (LLM выдал мусор) → ошибка валидации Pydantic, трактуется как `CannotBuild` (с причиной), не падение.
- **Пустой результат ≠ ошибка** — разные состояния.
- Секреты (`ANTHROPIC_API_KEY`, `BITRIX_WEBHOOK_URL`) — только из окружения.

## 7. Тестирование (ядро — на моках)

1. **`execute_recipe` (важнейшее):** mock `SourceRunner` отдаёт фиксированные строки → проверяем подстановку параметров в шаги, конкатенацию страниц, итог трансформаций; детерминизм.
2. **`BitrixRestRunner` пагинация:** mock HTTP отдаёт 3 «страницы» (`next`/`start`) → собраны все строки; маппинг tool→метод; ошибка/таймаут → понятная ошибка + ретрай.
3. **`AnthropicProvider`:** mock Anthropic-клиента отдаёт принудительный tool-use с рецептом → парсится в `Recipe`; ветка `cannot_build` → `CannotBuild`; мусорный вход → ошибка валидации → CannotBuild.
4. **`AgentService.ask`:** mock provider (рецепт) + mock runner → `AgentAnswer` с рецептом, результатом, `is_refreshable=True`; provider `cannot_build` → `is_refreshable=False`, без данных и рецепта. Мок-провайдер со счётчиком вызовов подтверждает: исполнение рецепта **не зовёт LLM**.
5. **Smoke (по флагу окружения):** реальный Anthropic строит валидный по схеме рецепт; реальный Битрикс отдаёт строки. Не в основном прогоне.

## 8. Вне рамок Плана 3

- HTTP-эндпоинт `/agent/ask`, сохранение рецепта, `reports`/`report_runs`, «Обновить» — План 4 (переиспользует `source/executor.py`).
- Несколько источников/SQL (УТ, СД), мульти-модельность, живое MCP-исследование Битрикса агентом — позже.
- Бюджеты шагов/токенов агента — минимально (одношаговый планировщик их почти не требует).
