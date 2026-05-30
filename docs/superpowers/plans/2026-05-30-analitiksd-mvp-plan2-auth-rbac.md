# AnalitikSD MVP — План 2: Auth + RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать платформе вход и разграничение прав — свою авторизацию (JWT в httpOnly-cookie + роли) и RBAC-проверки доступа к источникам и отчётам как переиспользуемые FastAPI-зависимости, с чистым ядром RBAC, покрытым TDD.

**Architecture:** FastAPI поверх PostgreSQL (SQLAlchemy 2.0 + Alembic). Тонкий HTTP-слой (`api/`) оборачивает чистую логику: хеширование паролей (bcrypt), JWT (PyJWT) и **чистые RBAC-решения** (`rbac/service.py`) над данными ролей/прав — как движок рецептов в Плане 1, тестируется без HTTP. Запросы к БД, питающие RBAC, изолированы в `rbac/queries.py` и `auth/service.py`.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic, PyJWT, bcrypt, PostgreSQL, pytest, httpx (TestClient).

---

## Предусловие (выполнить ДО Task 4 — первой задачи с БД)

«Postgres везде» требует запущенного PostgreSQL. На «голой» машине без Homebrew/Docker рекомендуется **Postgres.app**:

1. Скачать https://postgresapp.com/ → перетащить в `/Applications` → открыть → **Initialize/Start** (поднимает сервер на `localhost:5432`, пользователь — текущий системный, без пароля).
2. Добавить CLI в PATH (для `psql`/`createdb`):
   ```bash
   sudo mkdir -p /etc/paths.d && echo /Applications/Postgres.app/Contents/Versions/latest/bin | sudo tee /etc/paths.d/postgresapp
   ```
   (или добавить этот путь в `~/.zshrc`). Перезапустить терминал.
3. Создать рабочую и тестовую БД:
   ```bash
   createdb analitiksd
   createdb analitiksd_test
   ```
4. Экспортировать переменные окружения (положить в `~/.zshrc` или `.env`, который читается перед запуском):
   ```bash
   export DATABASE_URL="postgresql+psycopg2://localhost/analitiksd"
   export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
   ```
   Для тестов используется отдельная `DATABASE_URL` (`.../analitiksd_test`) — задаётся в `tests/conftest.py` автоматически (см. Task 4), переопределять вручную не нужно.

Если Postgres недоступен — задачи 1–3, 5, 6, 7 (чистая логика и схема) выполнимы, но задачи 4, 8–11 (БД/HTTP-интеграция) будут заблокированы до установки.

---

## Файловая структура (создаётся этим планом)

```
src/analitiksd/config.py             # Settings из окружения
src/analitiksd/db/__init__.py
src/analitiksd/db/base.py            # engine, sessionmaker, Base, get_session
src/analitiksd/db/models.py          # ORM: User, Role, UserRole, DataSource, RoleSource, ReportPerm
src/analitiksd/auth/__init__.py
src/analitiksd/auth/password.py      # hash_password / verify_password (bcrypt)
src/analitiksd/auth/tokens.py        # create_access_token / decode_access_token (JWT)
src/analitiksd/auth/service.py       # authenticate_user, role_names
src/analitiksd/rbac/__init__.py
src/analitiksd/rbac/service.py       # ЧИСТО: can_access_source / can_access_report
src/analitiksd/rbac/queries.py       # accessible_source_keys / report_access_levels (DB)
src/analitiksd/api/__init__.py
src/analitiksd/api/schemas.py        # LoginRequest, UserOut
src/analitiksd/api/deps.py           # get_db, get_current_user, require_source, require_report
src/analitiksd/api/auth_routes.py    # /auth/login, /logout, /me
src/analitiksd/api/app.py            # create_app()
alembic.ini, alembic/env.py, alembic/versions/0001_initial.py
tests/conftest.py
tests/auth/__init__.py  tests/auth/test_password.py  tests/auth/test_tokens.py  tests/auth/test_service.py
tests/rbac/__init__.py  tests/rbac/test_service.py
tests/api/__init__.py   tests/api/test_auth_flow.py  tests/api/test_rbac_deps.py
```

---

## Task 1: Зависимости и конфигурация

**Files:**
- Modify: `pyproject.toml`
- Create: `src/analitiksd/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Добавить зависимости в `pyproject.toml`**

Заменить блок `dependencies` и `optional-dependencies` на:
```toml
dependencies = [
    "pydantic>=2.6",
    "fastapi>=0.110",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg2-binary>=2.9",
    "pyjwt>=2.8",
    "bcrypt>=4.1",
    "email-validator>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
    "uvicorn>=0.29",
]
```

- [ ] **Step 2: Установить**

Run: `. .venv/bin/activate && pip install -e ".[dev]"`
Expected: установка успешна.

- [ ] **Step 3: Написать падающий тест конфигурации**

```python
# tests/test_config.py
import importlib

from analitiksd.config import Settings, get_settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://localhost/x")
    monkeypatch.setenv("JWT_SECRET", "secret")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    s = get_settings()
    assert isinstance(s, Settings)
    assert s.database_url == "postgresql+psycopg2://localhost/x"
    assert s.jwt_secret == "secret"
    assert s.jwt_algorithm == "HS256"
    assert s.jwt_expire_minutes == 60


def test_settings_missing_required_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    import pytest
    with pytest.raises(KeyError):
        get_settings()
```

- [ ] **Step 4: Запустить — убедиться, что падает**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'analitiksd.config'`).

- [ ] **Step 5: Реализовать `config.py`**

```python
# src/analitiksd/config.py
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 часов


def get_settings() -> Settings:
    """Считать настройки из окружения. Обязательные: DATABASE_URL, JWT_SECRET."""
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        jwt_secret=os.environ["JWT_SECRET"],
        jwt_algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        jwt_expire_minutes=int(os.environ.get("JWT_EXPIRE_MINUTES", "480")),
    )
```

- [ ] **Step 6: Запустить — убедиться, что проходит**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 теста).

- [ ] **Step 7: Коммит**

```bash
git add pyproject.toml src/analitiksd/config.py tests/test_config.py
git commit -m "feat(config): add settings loaded from environment + auth/db dependencies"
```

---

## Task 2: База БД и ORM-модели

**Files:**
- Create: `src/analitiksd/db/__init__.py` (пустой)
- Create: `src/analitiksd/db/base.py`
- Create: `src/analitiksd/db/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Написать падающий тест (метаданные таблиц, без подключения к БД)**

```python
# tests/test_models.py
from analitiksd.db.base import Base
from analitiksd.db.models import (
    DataSource,
    ReportPerm,
    Role,
    RoleSource,
    User,
    UserRole,
)


def test_all_tables_registered():
    tables = set(Base.metadata.tables)
    assert tables == {
        "users", "roles", "user_roles",
        "data_sources", "role_sources", "report_perms",
    }


def test_user_columns():
    cols = {c.name for c in User.__table__.columns}
    assert {"id", "email", "password_hash", "name", "is_active", "created_at"} <= cols


def test_email_is_unique():
    assert User.__table__.c.email.unique is True


def test_relationship_user_roles():
    # many-to-many через user_roles (строковый secondary резолвится при конфигурации мапперов)
    from sqlalchemy.orm import configure_mappers

    configure_mappers()
    assert User.roles.property.secondary.name == "user_roles"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'analitiksd.db.base'`).

- [ ] **Step 3: Реализовать `db/base.py`**

```python
# src/analitiksd/db/base.py
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from analitiksd.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Ленивый синглтон движка — создаётся при первом обращении (требует DATABASE_URL)."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, future=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), expire_on_commit=False, future=True
        )
    return _SessionLocal


def get_session() -> Iterator[Session]:
    sm = get_sessionmaker()
    with sm() as session:
        yield session
```

- [ ] **Step 4: Реализовать `db/models.py`**

```python
# src/analitiksd/db/models.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from analitiksd.db.base import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    roles: Mapped[list["Role"]] = relationship(
        secondary="user_roles", back_populates="users"
    )


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    users: Mapped[list["User"]] = relationship(
        secondary="user_roles", back_populates="roles"
    )
    sources: Mapped[list["DataSource"]] = relationship(
        secondary="role_sources", back_populates="roles"
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class DataSource(Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint("type IN ('mcp', 'sql')", name="ck_data_sources_type"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    type: Mapped[str] = mapped_column(String(16))  # mcp | sql
    config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    roles: Mapped[list["Role"]] = relationship(
        secondary="role_sources", back_populates="sources"
    )


class RoleSource(Base):
    __tablename__ = "role_sources"
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True
    )


class ReportPerm(Base):
    __tablename__ = "report_perms"
    __table_args__ = (
        UniqueConstraint("report_id", "role_id", name="uq_report_perms_report_role"),
        CheckConstraint("access IN ('view', 'edit')", name="ck_report_perms_access"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    # FK на reports появится миграцией в Плане 4; пока просто индексированный id
    report_id: Mapped[int] = mapped_column(index=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )
    access: Mapped[str] = mapped_column(String(8))  # view | edit
```

> Примечание: тесты `tests/test_models.py` дополнены проверками этих constraints/индексов и симметрии m2m-связей (`Role.sources`/`DataSource.roles`), уникальности `Role.name`/`DataSource.key` — см. итоговый код.

- [ ] **Step 5: Создать пустой `src/analitiksd/db/__init__.py`**

- [ ] **Step 6: Запустить — убедиться, что проходит**

Run: `pytest tests/test_models.py -v`
Expected: PASS (4 теста). Тесты читают только метаданные — подключение к БД не требуется.

- [ ] **Step 7: Коммит**

```bash
git add src/analitiksd/db/ tests/test_models.py
git commit -m "feat(db): add SQLAlchemy base and RBAC ORM models"
```

---

## Task 3: Alembic и начальная миграция

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/0001_initial.py`
- Modify: `pyproject.toml` (исключить `alembic/` из пакетов)

- [ ] **Step 1: Создать `alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = src

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Создать `alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 3: Создать `alembic/env.py`**

```python
# alembic/env.py
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from analitiksd.db.base import Base
from analitiksd.db import models  # noqa: F401  -- регистрирует таблицы в Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Миграции зависят только от DATABASE_URL — не требуют JWT_SECRET и прочих
# настроек приложения, поэтому читаем переменную напрямую, а не через get_settings().
database_url = os.environ["DATABASE_URL"]
config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Создать начальную миграцию `alembic/versions/0001_initial.py`**

```python
# alembic/versions/0001_initial.py
"""initial auth+rbac schema

Revision ID: 0001
Revises:
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # email: уникальность задаётся UNIQUE-constraint на колонке (отдельный индекс не нужен)

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("type IN ('mcp', 'sql')", name="ck_data_sources_type"),
    )

    op.create_table(
        "role_sources",
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "report_perms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("report_id", sa.Integer, nullable=False),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access", sa.String(8), nullable=False),
        sa.UniqueConstraint("report_id", "role_id", name="uq_report_perms_report_role"),
        sa.CheckConstraint("access IN ('view', 'edit')", name="ck_report_perms_access"),
    )
    op.create_index("ix_report_perms_report_id", "report_perms", ["report_id"])
    op.create_index("ix_report_perms_role_id", "report_perms", ["role_id"])


def downgrade() -> None:
    # индексы и constraints удаляются вместе со своими таблицами
    op.drop_table("report_perms")
    op.drop_table("role_sources")
    op.drop_table("data_sources")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
```

- [ ] **Step 5: Исключить `alembic/` из автопоиска пакетов**

В `pyproject.toml` секция `[tool.setuptools.packages.find]` уже `where = ["src"]`, поэтому `alembic/` (в корне) не попадает в пакет — менять не нужно. Убедиться, что это так.

- [ ] **Step 6: Применить миграцию к рабочей БД (требует Postgres из «Предусловия»)**

Run: `. .venv/bin/activate && alembic upgrade head`
Expected: создаются 6 таблиц, без ошибок. Проверка: `psql analitiksd -c "\dt"` показывает users, roles, user_roles, data_sources, role_sources, report_perms.

- [ ] **Step 7: Проверить откат и повторное применение**

Run: `alembic downgrade base && alembic upgrade head`
Expected: обе команды успешны (миграция обратима).

- [ ] **Step 8: Коммит**

```bash
git add alembic.ini alembic/
git commit -m "feat(db): add alembic config and initial auth+rbac migration"
```

---

## Task 4: Тестовая инфраструктура (conftest)

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/auth/__init__.py`, `tests/rbac/__init__.py`, `tests/api/__init__.py` (пустые)

**Требует Postgres и БД `analitiksd_test` (см. «Предусловие»).**

- [ ] **Step 1: Создать пустые `__init__.py` в `tests/auth/`, `tests/rbac/`, `tests/api/`**

- [ ] **Step 2: Создать `tests/conftest.py`**

```python
# tests/conftest.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Тестовая БД и секрет задаются ДО импорта приложения (config читает окружение).
# ПРИНУДИТЕЛЬНО направляем приложение на тест-БД (даже если в shell экспортирован
# dev-DATABASE_URL из «Предусловия») — иначе тесты пошли бы по рабочей базе.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg2://localhost/analitiksd_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402


@pytest.fixture(scope="session")
def _engine():
    """Применяет миграции к тест-БД один раз за сессию (заодно проверяя сами миграции)."""
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        cwd=_PROJECT_ROOT,  # чтобы alembic нашёл alembic.ini независимо от cwd запуска
        env={**os.environ},
    )
    engine = create_engine(os.environ["DATABASE_URL"])
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(_engine):
    """Каждый тест — во внешней транзакции с откатом (изоляция + скорость).

    join_transaction_mode="create_savepoint": session.commit() в коде приложения
    освобождает и заново создаёт SAVEPOINT (объекты остаются привязанными, без
    DetachedInstanceError), а внешний trans.rollback() в teardown откатывает всё.
    """
    connection = _engine.connect()
    trans = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session: Session = factory()
    try:
        yield session
    finally:
        # вложенные try/finally — чтобы сбой одного шага не оставил ресурс незакрытым
        try:
            session.close()
        finally:
            try:
                trans.rollback()
            finally:
                connection.close()
```

- [ ] **Step 3: Проверить, что conftest применяет миграции (sanity-тест)**

Создать временный тест в памяти — добавить в `tests/conftest.py` ничего не нужно; вместо этого выполнить быстрый тест существования таблиц прямо сейчас, добавив файл `tests/test_db_smoke.py`:

```python
# tests/test_db_smoke.py
from sqlalchemy import text


def test_tables_exist(db_session):
    rows = db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public'"
        )
    ).scalars().all()
    assert {"users", "roles", "data_sources", "report_perms"} <= set(rows)
```

- [ ] **Step 4: Запустить — убедиться, что проходит (нужен запущенный Postgres)**

Run: `. .venv/bin/activate && pytest tests/test_db_smoke.py -v`
Expected: PASS. Если падает с ошибкой подключения — Postgres не запущен / нет БД `analitiksd_test` (см. «Предусловие»).

- [ ] **Step 5: Коммит**

```bash
git add tests/conftest.py tests/auth/__init__.py tests/rbac/__init__.py tests/api/__init__.py tests/test_db_smoke.py
git commit -m "test: add postgres test fixtures with per-test transaction rollback"
```

---

## Task 5: Хеширование паролей (bcrypt)

**Files:**
- Create: `src/analitiksd/auth/__init__.py` (пустой)
- Create: `src/analitiksd/auth/password.py`
- Test: `tests/auth/test_password.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/auth/test_password.py
from analitiksd.auth.password import hash_password, verify_password


def test_hash_differs_from_plaintext():
    h = hash_password("secret123")
    assert h != "secret123"
    assert isinstance(h, str)


def test_verify_accepts_correct_password():
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True


def test_verify_rejects_wrong_password():
    h = hash_password("secret123")
    assert verify_password("wrong", h) is False


def test_hash_is_salted_unique():
    assert hash_password("same") != hash_password("same")
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/auth/test_password.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Реализовать `password.py`**

```python
# src/analitiksd/auth/password.py
from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """Вернуть bcrypt-хеш пароля (со случайной солью)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Проверить пароль против хеша. Любая ошибка формата хеша -> False."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False
```

- [ ] **Step 4: Создать пустой `src/analitiksd/auth/__init__.py`**

- [ ] **Step 5: Запустить — убедиться, что проходит**

Run: `pytest tests/auth/test_password.py -v`
Expected: PASS (4 теста).

- [ ] **Step 6: Коммит**

```bash
git add src/analitiksd/auth/__init__.py src/analitiksd/auth/password.py tests/auth/test_password.py
git commit -m "feat(auth): add bcrypt password hashing"
```

---

## Task 6: JWT-токены

**Files:**
- Create: `src/analitiksd/auth/tokens.py`
- Test: `tests/auth/test_tokens.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/auth/test_tokens.py
import jwt
import pytest

from analitiksd.auth.tokens import create_access_token, decode_access_token


def test_roundtrip_returns_subject(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    token = create_access_token("42")
    assert decode_access_token(token) == "42"


def test_expired_token_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    token = create_access_token("42", expires_minutes=-1)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_tampered_signature_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    token = create_access_token("42")
    monkeypatch.setenv("JWT_SECRET", "different-secret")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/auth/test_tokens.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Реализовать `tokens.py`**

```python
# src/analitiksd/auth/tokens.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from analitiksd.config import get_settings


def create_access_token(subject: str, *, expires_minutes: int | None = None) -> str:
    """Создать подписанный JWT с sub=subject и сроком жизни."""
    settings = get_settings()
    minutes = settings.jwt_expire_minutes if expires_minutes is None else expires_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Вернуть subject (sub) из валидного токена. Невалидный/просроченный -> jwt.PyJWTError.

    Токен без claim `sub` тоже считается невалидным (jwt.InvalidTokenError),
    чтобы весь поверхностный контракт ошибок оставался в рамках jwt.PyJWTError.
    """
    settings = get_settings()
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    subject = payload.get("sub")
    if subject is None:
        raise jwt.InvalidTokenError("Token missing 'sub' claim")
    return subject
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/auth/test_tokens.py -v`
Expected: PASS (3 теста).

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/auth/tokens.py tests/auth/test_tokens.py
git commit -m "feat(auth): add JWT access token create/decode"
```

---

## Task 7: Чистые RBAC-решения

**Files:**
- Create: `src/analitiksd/rbac/__init__.py` (пустой)
- Create: `src/analitiksd/rbac/service.py`
- Test: `tests/rbac/test_service.py`

Чистые функции над уже загруженными данными прав — без БД и HTTP. `can_access_report` учитывает иерархию: `edit` сильнее `view` (у кого есть edit, есть и view).

- [ ] **Step 1: Написать падающий тест (табличные матрицы)**

```python
# tests/rbac/test_service.py
import pytest

from analitiksd.rbac.service import can_access_report, can_access_source


@pytest.mark.parametrize(
    "accessible, source, expected",
    [
        ({"bitrix"}, "bitrix", True),
        ({"bitrix", "ut"}, "ut", True),
        (set(), "bitrix", False),
        ({"ut"}, "bitrix", False),
    ],
)
def test_can_access_source(accessible, source, expected):
    assert can_access_source(accessible, source) is expected


@pytest.mark.parametrize(
    "granted, required, expected",
    [
        (["view"], "view", True),
        (["edit"], "view", True),          # edit покрывает view
        (["edit"], "edit", True),
        (["view"], "edit", False),         # view не даёт edit
        ([], "view", False),
        (["view", "edit"], "edit", True),
    ],
)
def test_can_access_report(granted, required, expected):
    assert can_access_report(granted, required) is expected


def test_unknown_required_level_raises():
    with pytest.raises(KeyError):
        can_access_report(["view"], "delete")
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/rbac/test_service.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Реализовать `rbac/service.py`**

```python
# src/analitiksd/rbac/service.py
from __future__ import annotations

from collections.abc import Iterable

_ACCESS_RANK = {"view": 1, "edit": 2}


def can_access_source(accessible_source_keys: Iterable[str], source_key: str) -> bool:
    """True, если ключ источника есть среди доступных ролям пользователя."""
    return source_key in set(accessible_source_keys)


def can_access_report(granted_levels: Iterable[str], required: str) -> bool:
    """True, если хотя бы один выданный уровень >= требуемого (edit покрывает view).

    Неизвестный требуемый уровень -> KeyError (тихо ничего не глотаем).
    """
    required_rank = _ACCESS_RANK[required]
    return any(_ACCESS_RANK.get(level, 0) >= required_rank for level in granted_levels)
```

- [ ] **Step 4: Создать пустой `src/analitiksd/rbac/__init__.py`**

- [ ] **Step 5: Запустить — убедиться, что проходит**

Run: `pytest tests/rbac/test_service.py -v`
Expected: PASS (11 кейсов).

- [ ] **Step 6: Коммит**

```bash
git add src/analitiksd/rbac/__init__.py src/analitiksd/rbac/service.py tests/rbac/test_service.py
git commit -m "feat(rbac): add pure source/report access decision functions"
```

---

## Task 8: Запросы данных RBAC + сервис аутентификации

**Files:**
- Create: `src/analitiksd/rbac/queries.py`
- Create: `src/analitiksd/auth/service.py`
- Test: `tests/auth/test_service.py`

Интеграция с БД (требует Postgres). `auth/service.py` — поиск/проверка пользователя; `rbac/queries.py` — загрузка данных, питающих чистые решения из Task 7.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/auth/test_service.py
from analitiksd.auth.password import hash_password
from analitiksd.auth.service import authenticate_user, role_names
from analitiksd.db.models import (
    DataSource,
    ReportPerm,
    Role,
    RoleSource,
    User,
    UserRole,
)
from analitiksd.rbac.queries import accessible_source_keys, report_access_levels


def _seed(session):
    user = User(email="a@b.c", password_hash=hash_password("pw"), name="A", is_active=True)
    inactive = User(email="x@y.z", password_hash=hash_password("pw"), name="X", is_active=False)
    analyst = Role(name="analyst")
    src = DataSource(key="bitrix", type="mcp")
    session.add_all([user, inactive, analyst, src])
    session.flush()
    session.add_all([
        UserRole(user_id=user.id, role_id=analyst.id),
        RoleSource(role_id=analyst.id, source_id=src.id),
        ReportPerm(report_id=7, role_id=analyst.id, access="edit"),
    ])
    session.flush()
    return user, inactive, analyst


def test_authenticate_success(db_session):
    user, _, _ = _seed(db_session)
    result = authenticate_user(db_session, "a@b.c", "pw")
    assert result is not None and result.id == user.id


def test_authenticate_wrong_password(db_session):
    _seed(db_session)
    assert authenticate_user(db_session, "a@b.c", "nope") is None


def test_authenticate_unknown_email(db_session):
    _seed(db_session)
    assert authenticate_user(db_session, "missing@b.c", "pw") is None


def test_authenticate_inactive_user(db_session):
    _seed(db_session)
    assert authenticate_user(db_session, "x@y.z", "pw") is None


def test_role_names(db_session):
    user, _, _ = _seed(db_session)
    assert role_names(db_session, user.id) == ["analyst"]


def test_accessible_source_keys(db_session):
    user, _, _ = _seed(db_session)
    assert accessible_source_keys(db_session, user.id) == {"bitrix"}


def test_report_access_levels(db_session):
    user, _, _ = _seed(db_session)
    assert report_access_levels(db_session, user.id, 7) == ["edit"]
    assert report_access_levels(db_session, user.id, 999) == []
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/auth/test_service.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'analitiksd.auth.service'`).

- [ ] **Step 3: Реализовать `auth/service.py`**

```python
# src/analitiksd/auth/service.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from analitiksd.auth.password import hash_password, verify_password
from analitiksd.db.models import Role, User, UserRole

# Фиксированный хеш для выравнивания времени ответа: verify_password вызывается
# даже когда юзера нет/он неактивен, чтобы по времени ответа нельзя было определить
# существование email (защита от user-enumeration по тайминг-каналу).
_DUMMY_HASH = hash_password("constant-time-dummy-password")


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """Вернуть пользователя при верных email+пароле и is_active, иначе None.

    Один и тот же None для «нет юзера / неверный пароль / неактивен» — не утекаем причину.
    Время ответа выравнено (bcrypt считается всегда) — нет тайминг-оракула на email.
    """
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        verify_password(password, _DUMMY_HASH)  # выравнивание времени, результат не нужен
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
```

- [ ] **Step 4: Реализовать `rbac/queries.py`**

```python
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
```

- [ ] **Step 5: Запустить — убедиться, что проходит**

Run: `pytest tests/auth/test_service.py -v`
Expected: PASS (7 тестов).

- [ ] **Step 6: Коммит**

```bash
git add src/analitiksd/auth/service.py src/analitiksd/rbac/queries.py tests/auth/test_service.py
git commit -m "feat(auth): add user authentication and RBAC data queries"
```

---

## Task 9: FastAPI-приложение, схемы и базовые зависимости

**Files:**
- Create: `src/analitiksd/api/__init__.py` (пустой)
- Create: `src/analitiksd/api/schemas.py`
- Create: `src/analitiksd/api/deps.py`
- Create: `src/analitiksd/api/app.py`
- Test: `tests/api/test_auth_flow.py` (часть 1 — health + get_current_user)

- [ ] **Step 1: Написать падающий тест (health + защита без токена)**

```python
# tests/api/test_auth_flow.py
import pytest
from fastapi.testclient import TestClient

from analitiksd.api.app import create_app
from analitiksd.api.deps import get_db


@pytest.fixture
def client(db_session):
    app = create_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_me_without_token_is_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/api/test_auth_flow.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'analitiksd.api.app'`).

- [ ] **Step 3: Реализовать `api/schemas.py`**

```python
# src/analitiksd/api/schemas.py
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    roles: list[str]
```

> Примечание: `EmailStr` требует пакет `email-validator` — он уже добавлен в `dependencies` в Task 1 и установлен, отдельных действий не нужно.

- [ ] **Step 4: Реализовать `api/deps.py` (база — get_db, get_current_user)**

```python
# src/analitiksd/api/deps.py
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from analitiksd.auth.tokens import decode_access_token
from analitiksd.db.base import get_session
from analitiksd.db.models import User

COOKIE_NAME = "access_token"

# FastAPI-зависимость сессии БД — единая реализация в db.base.get_session.
# Тесты переопределяют именно этот символ (app.dependency_overrides[get_db]).
get_db = get_session


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        subject = decode_access_token(token)
        user_id = int(subject)  # нечисловой sub -> ValueError -> тоже 401, не 500
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unknown user")
    return user
```

- [ ] **Step 5: Реализовать `api/app.py`**

```python
# src/analitiksd/api/app.py
from __future__ import annotations

from fastapi import FastAPI

from analitiksd.api.auth_routes import router as auth_router


def create_app() -> FastAPI:
    app = FastAPI(title="AnalitikSD")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    return app
```

- [ ] **Step 6: Создать минимальный роутер `api/auth_routes.py` (только `/me`; login/logout — Task 10)**

```python
# src/analitiksd/api/auth_routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analitiksd.api.deps import get_current_user, get_db
from analitiksd.api.schemas import UserOut
from analitiksd.auth.service import role_names
from analitiksd.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserOut)
def me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, name=user.name, roles=role_names(db, user.id)
    )
```

> Импорты не циклические: `auth_routes` → `api.deps`/`auth.service`; ни `deps`, ни `app` не импортируют `auth_routes` обратно (кроме `app.include_router`, что выполняется во время вызова `create_app`, не на уровне модуля проблемно не циклично). В Task 10 этот файл дополняется маршрутами `/login` и `/logout`.

- [ ] **Step 7: Создать пустой `src/analitiksd/api/__init__.py`**

- [ ] **Step 8: Запустить — убедиться, что проходит**

Run: `pytest tests/api/test_auth_flow.py -v`
Expected: PASS (2 теста: health 200, /me без токена 401).

- [ ] **Step 9: Коммит**

```bash
git add src/analitiksd/api/ tests/api/test_auth_flow.py pyproject.toml
git commit -m "feat(api): add FastAPI app, schemas, get_db and get_current_user"
```

---

## Task 10: Маршруты аутентификации (login/logout/me)

**Files:**
- Modify: `src/analitiksd/api/auth_routes.py` (переписать начисто)
- Test: `tests/api/test_auth_flow.py` (дописать)

- [ ] **Step 1: Дописать падающие тесты**

Добавить в конец `tests/api/test_auth_flow.py`:

```python
from analitiksd.auth.password import hash_password
from analitiksd.db.models import User


def _make_user(db_session, email="u@e.com", password="pw", active=True):
    user = User(email=email, password_hash=hash_password(password), name="U", is_active=active)
    db_session.add(user)
    db_session.flush()
    return user


def test_login_sets_cookie_and_me_returns_profile(client, db_session):
    user = _make_user(db_session)
    r = client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    assert r.status_code == 200
    assert client.cookies.get("access_token")
    me = client.get("/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "u@e.com"
    assert body["roles"] == []


def test_login_wrong_password_401(client, db_session):
    _make_user(db_session)
    r = client.post("/auth/login", json={"email": "u@e.com", "password": "bad"})
    assert r.status_code == 401


def test_login_inactive_user_401(client, db_session):
    _make_user(db_session, email="i@e.com", active=False)
    r = client.post("/auth/login", json={"email": "i@e.com", "password": "pw"})
    assert r.status_code == 401


def test_logout_clears_cookie(client, db_session):
    _make_user(db_session)
    client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    r = client.post("/auth/logout")
    assert r.status_code == 200
    me = client.get("/auth/me")
    assert me.status_code == 401
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/api/test_auth_flow.py -v`
Expected: FAIL (нет `/auth/login`).

- [ ] **Step 3: Переписать `api/auth_routes.py` начисто**

```python
# src/analitiksd/api/auth_routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from analitiksd.api.deps import COOKIE_NAME, get_current_user, get_db
from analitiksd.api.schemas import LoginRequest, UserOut
from analitiksd.auth.service import authenticate_user, role_names
from analitiksd.auth.tokens import create_access_token
from analitiksd.config import get_settings
from analitiksd.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    body: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> dict[str, str]:
    user = authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    token = create_access_token(str(user.id))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=get_settings().jwt_expire_minutes * 60,
    )
    return {"status": "ok"}


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(key=COOKIE_NAME)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, name=user.name, roles=role_names(db, user.id)
    )
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/api/test_auth_flow.py -v`
Expected: PASS (6 тестов).

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/api/auth_routes.py tests/api/test_auth_flow.py
git commit -m "feat(api): add login/logout/me auth routes with httpOnly cookie"
```

---

## Task 11: RBAC-зависимости (require_source / require_report)

**Files:**
- Modify: `src/analitiksd/api/deps.py` (добавить зависимости)
- Modify: `src/analitiksd/api/app.py` (добавить защищённые демо-маршруты)
- Test: `tests/api/test_rbac_deps.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/api/test_rbac_deps.py
import pytest
from fastapi.testclient import TestClient

from analitiksd.api.app import create_app
from analitiksd.api.deps import get_db
from analitiksd.auth.password import hash_password
from analitiksd.db.models import (
    DataSource,
    ReportPerm,
    Role,
    RoleSource,
    User,
    UserRole,
)


@pytest.fixture
def client(db_session):
    app = create_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client, db_session, *, with_source=False, report_access=None):
    user = User(email="u@e.com", password_hash=hash_password("pw"), name="U", is_active=True)
    role = Role(name="analyst")
    src = DataSource(key="bitrix", type="mcp")
    db_session.add_all([user, role, src])
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    if with_source:
        db_session.add(RoleSource(role_id=role.id, source_id=src.id))
    if report_access is not None:
        db_session.add(ReportPerm(report_id=5, role_id=role.id, access=report_access))
    db_session.flush()
    client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})


def test_source_allowed(client, db_session):
    _login(client, db_session, with_source=True)
    r = client.get("/demo/source/bitrix")
    assert r.status_code == 200


def test_source_forbidden(client, db_session):
    _login(client, db_session, with_source=False)
    r = client.get("/demo/source/bitrix")
    assert r.status_code == 403


def test_report_view_allowed_with_edit(client, db_session):
    _login(client, db_session, report_access="edit")
    r = client.get("/demo/report/5")
    assert r.status_code == 200


def test_report_forbidden_without_grant(client, db_session):
    _login(client, db_session, report_access=None)
    r = client.get("/demo/report/5")
    assert r.status_code == 403
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/api/test_rbac_deps.py -v`
Expected: FAIL (нет маршрутов `/demo/...`).

- [ ] **Step 3: Добавить зависимости в `api/deps.py`**

Добавить в конец `src/analitiksd/api/deps.py`:

```python
from analitiksd.rbac.queries import accessible_source_keys, report_access_levels
from analitiksd.rbac.service import can_access_report, can_access_source


def require_source(source_key: str):
    """Фабрика зависимости: пускает, только если у пользователя есть доступ к источнику."""

    def _dep(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        keys = accessible_source_keys(db, user.id)
        if not can_access_source(keys, source_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No access to source '{source_key}'",
            )
        return user

    return _dep


def require_report(report_id: int, access: str):
    """Фабрика зависимости: пускает, только если у пользователя есть нужный доступ к отчёту."""

    def _dep(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        levels = report_access_levels(db, user.id, report_id)
        if not can_access_report(levels, access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No '{access}' access to report {report_id}",
            )
        return user

    return _dep
```

- [ ] **Step 4: Добавить демо-маршруты в `api/app.py`**

Заменить тело `create_app` в `src/analitiksd/api/app.py` так, чтобы добавить два защищённых демо-маршрута (демонстрируют RBAC-зависимости; реальные источники/отчёты — Планы 3/4):

```python
# src/analitiksd/api/app.py
from __future__ import annotations

from fastapi import Depends, FastAPI

from analitiksd.api.auth_routes import router as auth_router
from analitiksd.api.deps import require_report, require_source


def create_app() -> FastAPI:
    app = FastAPI(title="AnalitikSD")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/demo/source/bitrix")
    def demo_source(_=Depends(require_source("bitrix"))) -> dict[str, str]:
        return {"ok": "source"}

    @app.get("/demo/report/5")
    def demo_report(_=Depends(require_report(5, "view"))) -> dict[str, str]:
        return {"ok": "report"}

    app.include_router(auth_router)
    return app
```

- [ ] **Step 5: Запустить — убедиться, что проходит**

Run: `pytest tests/api/test_rbac_deps.py -v`
Expected: PASS (4 теста).

- [ ] **Step 6: Прогнать весь набор**

Run: `pytest`
Expected: PASS — все тесты Плана 1 (recipe) и Плана 2 (config, models, db_smoke, password, tokens, rbac, auth service, api).

- [ ] **Step 7: Коммит**

```bash
git add src/analitiksd/api/deps.py src/analitiksd/api/app.py tests/api/test_rbac_deps.py
git commit -m "feat(api): add require_source/require_report RBAC dependencies"
```

---

## Готовность плана

После всех задач: устанавливаемый backend с PostgreSQL-схемой (миграции Alembic), своей авторизацией (JWT в httpOnly-cookie, bcrypt-пароли), чистым ядром RBAC (доступ к источникам и отчётам) и FastAPI-маршрутами `login/logout/me` + переиспользуемыми RBAC-зависимостями. Ядро RBAC и auth покрыты тестами; интеграция проверена на реальном Postgres. Это слой авторизации, на который встают План 3 (Agent Service) и План 4 (Report Service + reports/report_runs).

**Следующие планы:** План 3 (Agent Service + MCP), План 4 (Report Service + API: reports/report_runs, сохранение/обновление), План 5 (React-фронтенд).
```
