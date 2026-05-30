# AnalitikSD — План 4: Report Service + API (дизайн-дополнение)

**Дата:** 2026-05-30
**Статус:** дизайн утверждён (объём делегирован исполнителю → полный срез)
**Базовый документ:** [`2026-05-29-analitiksd-platform-design.md`](2026-05-29-analitiksd-platform-design.md), разделы 4–8. Здесь детализируется срез «HTTP + сохранение/обновление отчётов».

## 1. Цель среза

Связать всё по HTTP: задать ad-hoc вопрос, **сохранить** рецепт как отчёт, открыть его и **обновить детерминированно (без LLM)** — с RBAC и историей запусков. Это последний backend-срез перед фронтендом (План 5).

## 2. Закрытые проектные развилки

| Тема | Решение | Почему |
|------|---------|--------|
| Таблицы | `reports` + `report_runs` (Alembic-миграция `0002`); той же миграцией — FK `report_perms.report_id → reports.id` (заглушка из Плана 2) | Завершает модель данных спеки (раздел 6) |
| RBAC по отчёту | Новая зависимость `require_report_access(access)`, читает `report_id` **из пути**; доступ = (владелец) **ИЛИ** (роль пользователя имеет `report_perm` нужного уровня) | Закрывает IDOR-замечание ревью Плана 2 (там id был константой); владелец всегда видит свой отчёт без авто-выдачи прав |
| Инъекция агента/раннера | FastAPI-зависимости `get_agent_service` / `get_source_runner` строят реальные Anthropic/Битрикс из настроек; в тестах подменяются моками через `app.dependency_overrides` | Ядро (Планы 1/3) тестируется без внешних систем |
| Обновление | `/reports/{id}/refresh` берёт сохранённый рецепт + params, зовёт `execute_recipe` (Плана 3) **без LLM**; пишет `report_run` | Гарантия детерминизма спеки: «та же логика, свежие данные» |
| Ошибки обновления | Ошибка → `report_run(status=error, error=...)`; **последний УСПЕШНЫЙ результат не затирается** | Спека: неудачный запуск не портит кэш |
| Кэш результата | `GET /reports/{id}` отдаёт результат **последнего успешного** прогона + статус/ошибку **последнего** прогона | Открыл отчёт — мгновенно видишь последние данные; видно, если последнее обновление упало |
| Сериализация рецепта | Хранить/отдавать через `recipe.model_dump(by_alias=True)`; читать через `Recipe.model_validate` | Поле `as_`/alias `as` + дискриминатор (латентный нюанс из Планов 1/3) |

## 3. Файловая структура (добавляется планом)

```
src/analitiksd/db/models.py             # +Report, +ReportRun
alembic/versions/0002_reports.py        # reports, report_runs, FK report_perms.report_id
src/analitiksd/reports/__init__.py
src/analitiksd/reports/service.py       # create/list/get/refresh — DB + execute_recipe
src/analitiksd/api/report_schemas.py    # Pydantic request/response
src/analitiksd/api/report_deps.py       # require_report_access, get_agent_service, get_source_runner
src/analitiksd/api/report_routes.py     # /agent/ask, /reports, /reports/{id}, /reports/{id}/refresh
src/analitiksd/api/app.py               # include report_router; убрать демо-маршруты Плана 2
tests/reports/, tests/api/test_report_routes.py
```

`reports/service.py` — чистая бизнес-логика над сессией БД и `execute_recipe`; HTTP-слой (`api/`) тонкий. Демо-маршруты `/demo/*` (тест-каркас Плана 2) удаляются — их роль выполняют реальные RBAC-маршруты отчётов.

## 4. Модель данных (раздел 6 спеки)

```
reports      (id, name, description, owner_id FK users, source, recipe jsonb,
              params jsonb, is_refreshable bool, created_at, updated_at)
report_runs  (id, report_id FK reports ON DELETE CASCADE, started_at, finished_at,
              status[ok|error], row_count int|null, result jsonb|null, error text|null,
              triggered_by FK users|null)
+ FK: report_perms.report_id -> reports.id (ON DELETE CASCADE)
```

## 5. Поток данных

**Ad-hoc (`POST /agent/ask`):** RBAC `require_source("bitrix")` → `AgentService.ask(question, BITRIX_CATALOG, runner)` → `{rows, recipe (by_alias), is_refreshable, message}`. Не сохраняет.

**Сохранить (`POST /reports`):** RBAC `require_source(source)` → `create_report(owner=current_user, name, source, recipe, params)` → `{id}`. Только выразимые (`is_refreshable=true`) рецепты сохраняемы.

**Список (`GET /reports`):** вернуть отчёты, где пользователь владелец ИЛИ есть `report_perm` через роли.

**Открыть (`GET /reports/{id}`):** RBAC `require_report_access("view")` → отчёт + результат последнего успешного прогона + статус последнего прогона.

**Обновить (`POST /reports/{id}/refresh`):** RBAC `require_report_access("view")` → опц. override периода → `execute_recipe(recipe, runner, values)` (без LLM) → записать `report_run`. Успех → `status=ok, result, row_count`. Ошибка источника → `status=error, error`, прошлый успешный результат сохраняется. Вернуть итог прогона.

## 6. Обработка ошибок (раздел 7 спеки)

- **401/403** — из Плана 2 (аутентификация / нет доступа к источнику или отчёту).
- **404** — отчёт не существует (или пользователь его не видит — отдаём 404, не раскрывая существование).
- **400** — невалидное тело (Pydantic), несохраняемый рецепт (`is_refreshable=false`), кривой override периода.
- **Ошибка обновления** (источник недоступен) → не 5xx «наружу как краш», а `report_run(status=error)` + понятный ответ; кэш цел.
- **Различие «честный отказ» (`CannotBuild`) vs «ошибка выполнения»** (исключение раннера) — сохраняется (из Плана 3).
- Секреты (`ANTHROPIC_API_KEY`, `BITRIX_WEBHOOK_URL`, `JWT_SECRET`) — только из окружения.

## 7. Тестирование (раздел 8 спеки)

1. **`reports/service.py` (интеграционные, тест-БД):** create → list (видит владелец; чужой не видит); get отдаёт последний успешный результат; refresh пишет run и **не зовёт LLM** (мок-провайдер/раннер со счётчиком); ошибка раннера → `status=error`, прошлый ok-результат цел.
2. **RBAC по пути (`require_report_access`):** владелец → ok; роль с `report_perm` → ok; посторонний → 404/403; матрица view/edit.
3. **API (интеграционные, через TestClient + override провайдера/раннера):** полный цикл вход → ask → сохранить → открыть → обновить → 200; обновление не зовёт LLM.
4. **Сериализация:** рецепт с `as`/computed round-trip через `model_dump(by_alias=True)` ↔ `model_validate`.
5. Реальные LLM/Битрикс — только smoke (из Плана 3), не в основном прогоне.

## 8. Вне рамок Плана 4

- Редактирование/удаление отчётов, «пересобрать через LLM» при дрейфе схемы (кнопка заложена), шаринг прав через UI — позже.
- Графики/экспорт (MVP — таблицы), несколько источников, фоновые/планируемые обновления — План 5+.
- Подписанный CSRF и прочие pre-production пункты — в отдельных задачах.
