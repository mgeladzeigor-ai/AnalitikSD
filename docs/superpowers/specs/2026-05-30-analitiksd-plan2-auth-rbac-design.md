# AnalitikSD — План 2: Auth + RBAC (дизайн-дополнение)

**Дата:** 2026-05-30
**Статус:** дизайн утверждён
**Базовый документ:** [`2026-05-29-analitiksd-platform-design.md`](2026-05-29-analitiksd-platform-design.md). Здесь детализируются только тактические решения среза Auth + RBAC; архитектура и модель данных заданы базовой спекой (разделы 4–8).

## 1. Цель среза

Дать платформе вход и разграничение прав: свою авторизацию (JWT-в-cookie + роли) и RBAC-проверки доступа к источникам и отчётам как переиспользуемые FastAPI-зависимости. Ядро RBAC — чистые функции над данными ролей/прав, тестируются без HTTP (как движок рецептов в Плане 1). После этого План 3 (Agent Service) и План 4 (Report Service) встают на готовый auth-слой.

## 2. Закрытые проектные развилки

| Тема | Решение | Почему |
|------|---------|--------|
| Механизм авторизации | JWT (HS256, PyJWT) в httpOnly + `SameSite=Lax` cookie; срок жизни ~8 ч | Stateless, просто с FastAPI + React SPA; httpOnly защищает от XSS-кражи токена; нет хранилища сессий. Жёсткий отзыв — позже (серверные сессии), если потребуется |
| Контроль активности | Проверка `users.is_active` на каждый запрос | Неактивного пользователя не пускаем даже с валидным неистёкшим токеном |
| Хеширование паролей | bcrypt (библиотека `bcrypt`) | Зрелый, battle-tested; для ~50 пользователей достаточно |
| Доступ к БД | SQLAlchemy 2.0 (typed `Mapped[]`) | Стандарт для FastAPI; типобезопасные модели |
| Миграции | Alembic | Версионирование схемы, согласуется с SQLAlchemy |
| БД для тестов | Реальный Postgres (как в проде), отдельная тест-БД; каждый тест — в транзакции с откатом | Нет расхождений диалектов (jsonb, типы, будущий RLS); изоляция и скорость через rollback |
| Scope | `users, roles, user_roles, data_sources, role_sources, report_perms`; endpoints `login/logout/me`; RBAC-зависимости | `reports/report_runs` и их endpoints — План 4 (Report Service) |

## 3. Файловая структура (добавляется этим планом)

```
src/analitiksd/db/base.py            # engine, SessionLocal, Base, get_session
src/analitiksd/db/models.py          # ORM-модели: User, Role, UserRole, DataSource, RoleSource, ReportPerm
src/analitiksd/auth/password.py      # hash_password / verify_password (bcrypt)
src/analitiksd/auth/tokens.py        # create_access_token / decode_access_token (JWT)
src/analitiksd/auth/service.py       # authenticate_user, load_user_roles
src/analitiksd/rbac/service.py       # can_access_source / can_access_report (чистая логика)
src/analitiksd/api/deps.py           # get_db, get_current_user, require_source, require_report
src/analitiksd/api/schemas.py        # Pydantic-схемы запросов/ответов auth
src/analitiksd/api/auth_routes.py    # POST /auth/login, POST /auth/logout, GET /auth/me
src/analitiksd/api/app.py            # сборка FastAPI-приложения
src/analitiksd/config.py             # настройки из окружения (DATABASE_URL, JWT_SECRET, ...)
alembic.ini, alembic/env.py, alembic/versions/*  # миграции
tests/auth/, tests/rbac/, tests/api/, tests/conftest.py
```

Принцип спеки: один файл — одна ответственность. HTTP-слой (`api/`) тонкий и оборачивает чистую логику (`auth/service.py`, `rbac/service.py`) в коды ответов.

## 4. Модель данных (подмножество базовой спеки, раздел 6)

Таблицы этого среза:
```
users        (id, email UNIQUE, password_hash, name, is_active, created_at)
roles        (id, name UNIQUE)                      -- admin, analyst, viewer
user_roles   (user_id FK, role_id FK)               -- many-to-many
data_sources (id, key UNIQUE, type[mcp|sql], config jsonb)  -- MVP: bitrix(mcp)
role_sources (role_id FK, source_id FK)             -- RBAC: источники роли
report_perms (report_id, role_id FK, access[view|edit])     -- RBAC по отчётам
```
`report_perms.report_id` пока без FK на `reports` (таблица появится в Плане 4) — хранится как идентификатор; FK добавим миграцией в Плане 4. Это осознанная развязка планов, а не упущение.

## 5. Поток авторизации и RBAC

1. `POST /auth/login {email, password}` → `authenticate_user`: найти по email, `verify_password`, проверить `is_active` → `create_access_token(sub=user_id)` → JWT в httpOnly+SameSite=Lax cookie. Неверный пароль / нет юзера / неактивен → **401 без различия причины** (не утекаем, какой случай).
2. Защищённый запрос → `get_current_user`: достать JWT из cookie, `decode_access_token`, загрузить пользователя, проверить `is_active`; иначе 401.
3. `require_source("bitrix")` → загрузить роли пользователя, вызвать чистый `rbac.can_access_source(roles, source)`; отказ → 403 + лог попытки.
4. `require_report(report_id, "view"|"edit")` → `rbac.can_access_report(...)`; отказ → 403 + лог.
5. `POST /auth/logout` → удаление cookie. `GET /auth/me` → профиль + роли текущего пользователя.

## 6. Обработка ошибок (раздел 7 базовой спеки)

- **401** — нет/просрочен/невалиден токен, либо `is_active=false`. Редирект на вход — на стороне SPA (План 5).
- **403** — нет доступа к источнику/отчёту; попытка логируется (аудит).
- **400** — невалидное тело запроса (Pydantic).
- Никаких тихих fallback-ов; различие «пустой результат» vs «ошибка» соблюдается; секреты (`JWT_SECRET`, доступы) — только из окружения, не в БД открытым текстом и не в логах.

## 7. Тестирование (ядро — через TDD)

1. **RBAC (важнейшее, юнит):** табличные тесты матриц «роль × источник» и «роль × отчёт» на чистом `rbac.service` без HTTP.
2. **Password / tokens (юнит):** хеш ≠ пароль и verify true/false; JWT round-trip, просроченный/битый/с чужой подписью → ошибка декода.
3. **Auth (интеграционные, тест-БД):** логин ок / неверный пароль / неактивный / просроченный токен → 200/401; `/me` возвращает роли.
4. **RBAC через API (интеграционные):** роль без источника → 403; роль без доступа к отчёту → 403; happy-path → 200.

Тест-инфраструктура: `tests/conftest.py` поднимает соединение к тест-Postgres, **один раз за сессию применяет Alembic-миграции к head** (это заодно проверяет сами миграции на актуальной схеме), затем оборачивает каждый тест в транзакцию с откатом; фикстуры для пользователей/ролей/прав.

## 8. Вне рамок Плана 2

- `reports` / `report_runs` и их API — План 4.
- Row-level права (RLS) — заложены, реализуются позже.
- SSO / вход через Битрикс / AD — вне MVP.
- Регистрация пользователей через UI, сброс пароля по email — позже; в Плане 2 пользователи/роли заводятся сидингом/миграцией и админ-скриптом.
