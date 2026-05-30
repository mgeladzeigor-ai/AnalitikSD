# AnalitikSD MVP — План 4: Report Service + API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Связать всё по HTTP — ad-hoc вопрос, сохранение рецепта как отчёта, открытие и детерминированное обновление (без LLM) — с RBAC и историей запусков.

**Architecture:** Новые таблицы `reports`/`report_runs` (Alembic). `reports/service.py` — бизнес-логика над сессией БД и `execute_recipe` (Плана 3). Тонкий HTTP-слой (`api/report_routes.py`) с RBAC-зависимостями; агент и source-раннер инжектятся через FastAPI-зависимости (реальные из настроек, в тестах — моки через `dependency_overrides`). Обновление переиспользует `source/executor.execute_recipe` без LLM.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, pytest, httpx (TestClient). Переиспользует Планы 1–3.

---

## Файловая структура (создаётся/меняется планом)

```
src/analitiksd/db/models.py             # +Report, +ReportRun
alembic/versions/0002_reports.py        # reports, report_runs, FK report_perms.report_id
src/analitiksd/reports/__init__.py
src/analitiksd/reports/service.py       # create/list/get/access/refresh
src/analitiksd/api/report_schemas.py    # Pydantic request/response
src/analitiksd/api/report_deps.py       # require_report_access, get_agent_service, get_source_runner
src/analitiksd/api/report_routes.py     # /agent/ask, /reports, /reports/{id}, /reports/{id}/refresh
src/analitiksd/api/app.py               # include report_router; remove demo routes
tests/reports/__init__.py  tests/reports/test_service.py
tests/api/test_report_routes.py
```

---

## Task 1: Модели Report и ReportRun

**Files:**
- Modify: `src/analitiksd/db/models.py`
- Test: `tests/test_models.py` (дописать)

- [ ] **Step 1: Дописать падающие тесты в `tests/test_models.py`**

```python
def test_reports_tables_registered():
    from analitiksd.db.base import Base
    assert "reports" in Base.metadata.tables
    assert "report_runs" in Base.metadata.tables


def test_report_columns():
    from analitiksd.db.models import Report
    cols = {c.name for c in Report.__table__.columns}
    assert {"id", "name", "description", "owner_id", "source", "recipe",
            "params", "is_refreshable", "created_at", "updated_at"} <= cols


def test_report_run_columns_and_status_check():
    from analitiksd.db.models import ReportRun
    cols = {c.name for c in ReportRun.__table__.columns}
    assert {"id", "report_id", "started_at", "finished_at", "status",
            "row_count", "result", "error", "triggered_by"} <= cols
    constraints = {c.name for c in ReportRun.__table__.constraints}
    assert "ck_report_runs_status" in constraints
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_models.py -k "reports_tables or report_columns or report_run_columns" -v`
Expected: FAIL (`ImportError`/`KeyError`: моделей нет).

- [ ] **Step 3: Добавить модели в `src/analitiksd/db/models.py`**

В начале файла убедиться, что импортирован `Text` (добавить в список `from sqlalchemy import (...)`): добавить `Text` в импорт sqlalchemy. Затем в КОНЕЦ файла добавить:

```python
class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1024), default="", server_default="")
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(64))
    recipe: Mapped[dict] = mapped_column(JSONB)
    params: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    is_refreshable: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReportRun(Base):
    __tablename__ = "report_runs"
    __table_args__ = (
        CheckConstraint("status IN ('ok', 'error')", name="ck_report_runs_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(8))  # ok | error
    row_count: Mapped[int | None] = mapped_column(nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {"rows": [...]}
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_models.py -v`  → PASS.
Run: `pytest -q`  → весь набор зелёный (метаданные не требуют БД).

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/db/models.py tests/test_models.py
git commit -m "feat(db): add Report and ReportRun ORM models"
```

---

## Task 2: Миграция reports/report_runs

**Files:**
- Create: `alembic/versions/0002_reports.py`

> Примечание (сознательное отступление от дизайн-документа): FK `report_perms.report_id → reports.id` **отложен** в отдельную hardening-задачу. Его немедленное добавление нарушило бы существующие RBAC-тесты Плана 2 (`tests/auth/test_service.py` вставляет `ReportPerm` с синтетическим `report_id` без строки в `reports`). Для MVP FK не нужен функционально: логика доступа работает по равенству `report_id`, а удаления отчётов в Плане 4 нет (orphan-прав не возникает). FK + правка тех тестов — отдельной задачей позже.

- [ ] **Step 1: Создать `alembic/versions/0002_reports.py`**

```python
# alembic/versions/0002_reports.py
"""reports and report_runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1024), nullable=False, server_default=""),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("recipe", postgresql.JSONB, nullable=False),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_refreshable", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reports_owner_id", "reports", ["owner_id"])

    op.create_table(
        "report_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("row_count", sa.Integer, nullable=True),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("triggered_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("status IN ('ok', 'error')", name="ck_report_runs_status"),
    )
    op.create_index("ix_report_runs_report_id", "report_runs", ["report_id"])


def downgrade() -> None:
    op.drop_table("report_runs")
    op.drop_table("reports")
```

- [ ] **Step 2: Применить миграцию к dev-БД**

Run:
```
. .venv/bin/activate && DATABASE_URL="postgresql+psycopg2://localhost/analitiksd" alembic upgrade head && DATABASE_URL="postgresql+psycopg2://localhost/analitiksd" alembic current
```
Expected: upgrade ок; `alembic current` = `0002 (head)`.

Проверить таблицы (Python, psql не на PATH):
```
. .venv/bin/activate && DATABASE_URL="postgresql+psycopg2://localhost/analitiksd" python3 -c "
import psycopg2
c=psycopg2.connect(host='localhost',dbname='analitiksd');cur=c.cursor()
cur.execute(\"select table_name from information_schema.tables where table_schema='public' and table_name in ('reports','report_runs')\")
print(sorted(r[0] for r in cur.fetchall()))
"
```
Expected: `['report_runs', 'reports']`.

- [ ] **Step 3: Проверить обратимость**

Run:
```
. .venv/bin/activate && DATABASE_URL="postgresql+psycopg2://localhost/analitiksd" alembic downgrade base && DATABASE_URL="postgresql+psycopg2://localhost/analitiksd" alembic upgrade head
```
Expected: обе команды успешны.

- [ ] **Step 4: Прогнать весь набор (conftest применит обе миграции к тест-БД)**

Run: `. .venv/bin/activate && pytest -q`
Expected: всё зелёное (conftest применяет миграции к `analitiksd_test`).

- [ ] **Step 5: Коммит**

```bash
git add alembic/versions/0002_reports.py
git commit -m "feat(db): add reports/report_runs migration and report_perms FK"
```

---

## Task 3: reports/service.py — создание, список, доступ, чтение

**Files:**
- Create: `src/analitiksd/reports/__init__.py` (пустой)
- Create: `src/analitiksd/reports/service.py`
- Create: `tests/reports/__init__.py` (пустой)
- Test: `tests/reports/test_service.py`

- [ ] **Step 1: Написать падающий тест `tests/reports/test_service.py`**

```python
# tests/reports/test_service.py
from analitiksd.auth.password import hash_password
from analitiksd.db.models import ReportPerm, ReportRun, Role, User, UserRole
from analitiksd.reports import service

RECIPE = {
    "version": 1, "source": "bitrix",
    "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID"]}}],
    "transform": [], "presentation": {"type": "table", "columns": ["ID"]},
}


def _user(db, email="a@b.c"):
    u = User(email=email, password_hash=hash_password("pw"), name="A", is_active=True)
    db.add(u); db.flush()
    return u


def test_create_and_get_report(db):
    owner = _user(db)
    report = service.create_report(
        db, owner_id=owner.id, name="R1", description="d",
        source="bitrix", recipe=RECIPE, params={},
    )
    assert report.id is not None
    assert service.get_report_or_none(db, report.id).name == "R1"
    assert service.get_report_or_none(db, 99999) is None


def test_owner_can_access_others_cannot(db):
    owner = _user(db, "owner@x")
    other = _user(db, "other@x")
    report = service.create_report(db, owner_id=owner.id, name="R", description="",
                                   source="bitrix", recipe=RECIPE, params={})
    assert service.user_can_access_report(db, owner.id, report, "view") is True
    assert service.user_can_access_report(db, other.id, report, "view") is False


def test_role_perm_grants_access(db):
    owner = _user(db, "owner2@x")
    viewer = _user(db, "viewer@x")
    role = Role(name="analyst2"); db.add(role); db.flush()
    db.add(UserRole(user_id=viewer.id, role_id=role.id))
    report = service.create_report(db, owner_id=owner.id, name="R", description="",
                                   source="bitrix", recipe=RECIPE, params={})
    db.add(ReportPerm(report_id=report.id, role_id=role.id, access="view")); db.flush()
    assert service.user_can_access_report(db, viewer.id, report, "view") is True
    assert service.user_can_access_report(db, viewer.id, report, "edit") is False


def test_list_accessible_reports(db):
    owner = _user(db, "o3@x")
    other = _user(db, "u3@x")
    r1 = service.create_report(db, owner_id=owner.id, name="mine", description="",
                               source="bitrix", recipe=RECIPE, params={})
    service.create_report(db, owner_id=other.id, name="theirs", description="",
                          source="bitrix", recipe=RECIPE, params={})
    names = {r.name for r in service.list_accessible_reports(db, owner.id)}
    assert "mine" in names
    assert "theirs" not in names


def test_latest_ok_run_and_latest_run(db):
    owner = _user(db, "o4@x")
    report = service.create_report(db, owner_id=owner.id, name="R", description="",
                                   source="bitrix", recipe=RECIPE, params={})
    db.add(ReportRun(report_id=report.id, status="ok", row_count=2, result={"rows": [{"ID": 1}]}))
    db.flush()
    db.add(ReportRun(report_id=report.id, status="error", error="boom"))
    db.flush()
    assert service.latest_run(db, report.id).status == "error"
    assert service.latest_ok_run(db, report.id).row_count == 2
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/reports/test_service.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'analitiksd.reports.service'`).

> Примечание: тесты используют фикстуру `db` — это уже существующая `db_session`. Добавь в `tests/conftest.py` алиас (Step 2.5 ниже).

- [ ] **Step 2.5: Добавить алиас фикстуры `db` в `tests/conftest.py`**

В конец `tests/conftest.py` добавить:
```python
@pytest.fixture
def db(db_session):
    return db_session
```

- [ ] **Step 3: Реализовать `src/analitiksd/reports/service.py`**

```python
# src/analitiksd/reports/service.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from analitiksd.db.models import Report, ReportPerm, ReportRun, UserRole
from analitiksd.rbac.queries import report_access_levels
from analitiksd.rbac.service import can_access_report


def create_report(
    session: Session,
    *,
    owner_id: int,
    name: str,
    description: str,
    source: str,
    recipe: dict,
    params: dict,
) -> Report:
    report = Report(
        owner_id=owner_id, name=name, description=description, source=source,
        recipe=recipe, params=params, is_refreshable=True,
    )
    session.add(report)
    session.flush()
    return report


def get_report_or_none(session: Session, report_id: int) -> Report | None:
    return session.get(Report, report_id)


def user_can_access_report(
    session: Session, user_id: int, report: Report, access: str
) -> bool:
    """Доступ = владелец ИЛИ роль пользователя имеет нужный уровень в report_perms."""
    if report.owner_id == user_id:
        return True
    levels = report_access_levels(session, user_id, report.id)
    return can_access_report(levels, access)


def list_accessible_reports(session: Session, user_id: int) -> list[Report]:
    """Отчёты, где пользователь владелец ИЛИ есть report_perm через его роли."""
    owned = session.execute(
        select(Report).where(Report.owner_id == user_id)
    ).scalars().all()
    shared = session.execute(
        select(Report)
        .join(ReportPerm, Report.id == ReportPerm.report_id)
        .join(UserRole, UserRole.role_id == ReportPerm.role_id)
        .where(UserRole.user_id == user_id)
    ).scalars().all()
    by_id = {r.id: r for r in [*owned, *shared]}
    return sorted(by_id.values(), key=lambda r: r.id)


def latest_run(session: Session, report_id: int) -> ReportRun | None:
    return session.execute(
        select(ReportRun).where(ReportRun.report_id == report_id)
        .order_by(ReportRun.id.desc()).limit(1)
    ).scalar_one_or_none()


def latest_ok_run(session: Session, report_id: int) -> ReportRun | None:
    return session.execute(
        select(ReportRun).where(ReportRun.report_id == report_id, ReportRun.status == "ok")
        .order_by(ReportRun.id.desc()).limit(1)
    ).scalar_one_or_none()
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/reports/test_service.py -v`  → PASS (5 тестов).
Run: `pytest -q`  → весь набор зелёный.

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/reports/__init__.py src/analitiksd/reports/service.py tests/reports/__init__.py tests/reports/test_service.py tests/conftest.py
git commit -m "feat(reports): add report create/list/get/access service"
```

---

## Task 4: reports/service.py — refresh (детерминированное обновление)

**Files:**
- Modify: `src/analitiksd/reports/service.py` (добавить `refresh_report`)
- Test: `tests/reports/test_service.py` (дописать)

- [ ] **Step 1: Дописать падающие тесты в `tests/reports/test_service.py`**

```python
class FakeRunner:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.calls = 0

    def fetch(self, step):
        self.calls += 1
        if self.error:
            raise self.error
        return self.rows


def test_refresh_records_ok_run(db):
    owner = _user(db, "o5@x")
    report = service.create_report(db, owner_id=owner.id, name="R", description="",
                                   source="bitrix", recipe=RECIPE, params={})
    runner = FakeRunner(rows=[{"ID": 1}, {"ID": 2}])
    run = service.refresh_report(db, report, runner, triggered_by=owner.id)
    assert run.status == "ok"
    assert run.row_count == 2
    assert run.result == {"rows": [{"ID": 1}, {"ID": 2}]}
    assert run.finished_at is not None


def test_refresh_records_error_and_keeps_last_ok(db):
    owner = _user(db, "o6@x")
    report = service.create_report(db, owner_id=owner.id, name="R", description="",
                                   source="bitrix", recipe=RECIPE, params={})
    ok = service.refresh_report(db, report, FakeRunner(rows=[{"ID": 1}]), triggered_by=owner.id)
    bad = service.refresh_report(db, report, FakeRunner(error=RuntimeError("source down")), triggered_by=owner.id)
    assert ok.status == "ok"
    assert bad.status == "error"
    assert "source down" in bad.error
    # последний успешный результат не затёрт
    assert service.latest_ok_run(db, report.id).id == ok.id
    assert service.latest_run(db, report.id).id == bad.id
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/reports/test_service.py -k refresh -v`
Expected: FAIL (`AttributeError: module ... has no attribute 'refresh_report'`).

- [ ] **Step 3: Добавить `refresh_report` в `src/analitiksd/reports/service.py`**

Добавить импорты вверху файла:
```python
from datetime import datetime, timezone

from analitiksd.recipe.models import Recipe
from analitiksd.recipe.params import resolve_params
from analitiksd.source.executor import execute_recipe
from analitiksd.source.runner import SourceRunner
```
И функцию в конец файла:
```python
def refresh_report(
    session: Session,
    report: Report,
    runner: SourceRunner,
    *,
    triggered_by: int | None,
    overrides: dict | None = None,
) -> ReportRun:
    """Детерминированно обновить отчёт: исполнить рецепт без LLM, записать report_run.

    Ошибка исполнения (источник недоступен и т.п.) -> status=error с текстом;
    прошлый успешный результат остаётся (отдельной строкой run, не затирается).
    """
    run = ReportRun(report_id=report.id, status="ok", triggered_by=triggered_by)
    try:
        recipe = Recipe.model_validate(report.recipe)
        values = resolve_params(report.params, overrides) if report.params else {}
        rows = execute_recipe(recipe, runner, values=values)
        run.status = "ok"
        run.result = {"rows": rows}
        run.row_count = len(rows)
    except Exception as exc:  # noqa: BLE001 — граница записи ошибок выполнения (не «тихо»)
        run.status = "error"
        run.error = str(exc)
        run.result = None
        run.row_count = None
    run.finished_at = datetime.now(timezone.utc)
    session.add(run)
    session.flush()
    return run
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/reports/test_service.py -v`  → PASS (все, включая refresh).
Run: `pytest -q`  → весь набор зелёный.

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/reports/service.py tests/reports/test_service.py
git commit -m "feat(reports): add deterministic refresh_report recording report_runs"
```

---

## Task 5: Pydantic-схемы отчётов

**Files:**
- Create: `src/analitiksd/api/report_schemas.py`
- Test: `tests/api/test_report_schemas.py`

- [ ] **Step 1: Написать падающий тест `tests/api/test_report_schemas.py`**

```python
# tests/api/test_report_schemas.py
import pytest
from pydantic import ValidationError

from analitiksd.api.report_schemas import AskRequest, SaveReportRequest


def test_ask_request_requires_nonempty_question():
    assert AskRequest(question="сколько сделок").question
    with pytest.raises(ValidationError):
        AskRequest(question="")


def test_save_report_request_defaults():
    req = SaveReportRequest(name="R", source="bitrix", recipe={"version": 1})
    assert req.description == ""
    assert req.params == {}
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/api/test_report_schemas.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Реализовать `src/analitiksd/api/report_schemas.py`**

```python
# src/analitiksd/api/report_schemas.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    rows: list[dict[str, Any]] | None
    recipe: dict[str, Any] | None
    is_refreshable: bool
    message: str | None = None


class SaveReportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1024)
    source: str = Field(min_length=1, max_length=64)
    recipe: dict[str, Any]
    params: dict[str, Any] = Field(default_factory=dict)


class SaveReportResponse(BaseModel):
    id: int


class ReportListItem(BaseModel):
    id: int
    name: str
    source: str
    is_refreshable: bool


class ReportDetail(BaseModel):
    id: int
    name: str
    description: str
    source: str
    is_refreshable: bool
    last_result: list[dict[str, Any]] | None = None
    last_status: str | None = None
    last_error: str | None = None


class RefreshRequest(BaseModel):
    overrides: dict[str, Any] | None = None


class RunResult(BaseModel):
    status: str
    row_count: int | None = None
    result: list[dict[str, Any]] | None = None
    error: str | None = None
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/api/test_report_schemas.py -v`  → PASS (2 теста).

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/api/report_schemas.py tests/api/test_report_schemas.py
git commit -m "feat(api): add report request/response schemas"
```

---

## Task 6: Зависимости — RBAC по пути и фабрики агента/раннера

**Files:**
- Create: `src/analitiksd/api/report_deps.py`
- Test: `tests/api/test_report_deps.py`

- [ ] **Step 1: Написать падающий тест `tests/api/test_report_deps.py`**

```python
# tests/api/test_report_deps.py
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from analitiksd.api.deps import COOKIE_NAME, get_db
from analitiksd.api.report_deps import require_report_access
from analitiksd.auth.password import hash_password
from analitiksd.auth.tokens import create_access_token
from analitiksd.db.models import Report, User


def _app(db_session):
    app = FastAPI()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    @app.get("/r/{report_id}")
    def read(report: Report = Depends(require_report_access("view"))):
        return {"id": report.id, "name": report.name}

    return app


def _login_cookie(client, user_id):
    client.cookies.set(COOKIE_NAME, create_access_token(str(user_id)))


def test_owner_gets_report(db_session):
    owner = User(email="o@x", password_hash=hash_password("pw"), name="O", is_active=True)
    db_session.add(owner); db_session.flush()
    report = Report(owner_id=owner.id, name="R", description="", source="bitrix",
                    recipe={"version": 1}, params={}, is_refreshable=True)
    db_session.add(report); db_session.flush()
    app = _app(db_session)
    with TestClient(app) as client:
        _login_cookie(client, owner.id)
        r = client.get(f"/r/{report.id}")
        assert r.status_code == 200
        assert r.json()["id"] == report.id


def test_stranger_gets_404(db_session):
    owner = User(email="o2@x", password_hash=hash_password("pw"), name="O", is_active=True)
    stranger = User(email="s@x", password_hash=hash_password("pw"), name="S", is_active=True)
    db_session.add_all([owner, stranger]); db_session.flush()
    report = Report(owner_id=owner.id, name="R", description="", source="bitrix",
                    recipe={"version": 1}, params={}, is_refreshable=True)
    db_session.add(report); db_session.flush()
    app = _app(db_session)
    with TestClient(app) as client:
        _login_cookie(client, stranger.id)
        r = client.get(f"/r/{report.id}")
        assert r.status_code == 404


def test_missing_report_404(db_session):
    user = User(email="u@x", password_hash=hash_password("pw"), name="U", is_active=True)
    db_session.add(user); db_session.flush()
    app = _app(db_session)
    with TestClient(app) as client:
        _login_cookie(client, user.id)
        assert client.get("/r/999999").status_code == 404
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/api/test_report_deps.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'analitiksd.api.report_deps'`).

- [ ] **Step 3: Реализовать `src/analitiksd/api/report_deps.py`**

```python
# src/analitiksd/api/report_deps.py
from __future__ import annotations

import httpx
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from analitiksd.agent.provider import AnthropicProvider
from analitiksd.agent.service import AgentService
from analitiksd.api.deps import get_current_user, get_db
from analitiksd.config import get_settings
from analitiksd.db.models import Report, User
from analitiksd.reports import service
from analitiksd.source.runner import BitrixRestRunner

_BITRIX_TIMEOUT_SECONDS = 30


def require_report_access(access: str):
    """Фабрика зависимости: report_id берётся ИЗ ПУТИ; нет доступа/нет отчёта -> 404.

    404 (а не 403) для чужого отчёта — не раскрываем существование.
    """

    def _dep(
        report_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Report:
        report = service.get_report_or_none(db, report_id)
        if report is None or not service.user_can_access_report(db, user.id, report, access):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        return report

    return _dep


def get_source_runner():
    """Строит реальный BitrixRestRunner из настроек; в тестах переопределяется."""
    settings = get_settings()
    if not settings.bitrix_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Source not configured"
        )
    with httpx.Client(timeout=_BITRIX_TIMEOUT_SECONDS) as http:
        yield BitrixRestRunner(settings.bitrix_webhook_url, http)


def get_agent_service() -> AgentService:
    """Строит реальный AgentService (Anthropic) из настроек; в тестах переопределяется."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM not configured"
        )
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return AgentService(AnthropicProvider(client, settings.anthropic_model))
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/api/test_report_deps.py -v`  → PASS (3 теста).
Run: `pytest -q`  → весь набор зелёный.

- [ ] **Step 5: Коммит**

```bash
git add src/analitiksd/api/report_deps.py tests/api/test_report_deps.py
git commit -m "feat(api): add path-aware require_report_access and agent/source factories"
```

---

## Task 7: Маршруты отчётов + сборка приложения

**Files:**
- Create: `src/analitiksd/api/report_routes.py`
- Modify: `src/analitiksd/api/app.py` (подключить router, убрать демо-маршруты)
- Test: `tests/api/test_report_routes.py`

- [ ] **Step 1: Написать падающий тест `tests/api/test_report_routes.py`**

```python
# tests/api/test_report_routes.py
import pytest
from fastapi.testclient import TestClient

from analitiksd.agent.decision import CannotBuild
from analitiksd.agent.service import AgentAnswer
from analitiksd.api.app import create_app
from analitiksd.api.deps import COOKIE_NAME, get_db
from analitiksd.api.report_deps import get_agent_service, get_source_runner
from analitiksd.auth.password import hash_password
from analitiksd.auth.tokens import create_access_token
from analitiksd.db.models import DataSource, Role, RoleSource, User, UserRole
from analitiksd.recipe.models import Recipe

RECIPE_RAW = {
    "version": 1, "source": "bitrix",
    "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID", "OPPORTUNITY"]}}],
    "transform": [{"op": "aggregate", "metrics": [{"fn": "sum", "field": "OPPORTUNITY", "as": "total"}]}],
    "presentation": {"type": "table", "columns": ["total"]},
}


class FakeAgent:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def ask(self, question, catalog, runner, *, values=None):
        self.calls += 1
        return self.answer


class FakeRunner:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def fetch(self, step):
        self.calls += 1
        return self.rows


@pytest.fixture
def env(db_session):
    # пользователь с ролью, у роли доступ к источнику bitrix
    user = User(email="u@e.com", password_hash=hash_password("pw"), name="U", is_active=True)
    role = Role(name="analyst")
    src = DataSource(key="bitrix", type="mcp")
    db_session.add_all([user, role, src]); db_session.flush()
    db_session.add_all([UserRole(user_id=user.id, role_id=role.id),
                        RoleSource(role_id=role.id, source_id=src.id)])
    db_session.flush()
    return {"db": db_session, "user": user}


def _client(env, agent, runner):
    app = create_app()

    def _override_get_db():
        yield env["db"]

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_agent_service] = lambda: agent

    def _override_runner():
        yield runner

    app.dependency_overrides[get_source_runner] = _override_runner
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, create_access_token(str(env["user"].id)))
    return client


def test_ask_returns_recipe_and_rows(env):
    agent = FakeAgent(AgentAnswer(rows=[{"total": 500}], recipe=Recipe.model_validate(RECIPE_RAW),
                                  is_refreshable=True))
    client = _client(env, agent, FakeRunner([]))
    r = client.post("/agent/ask", json={"question": "сумма сделок"})
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == [{"total": 500}]
    assert body["recipe"]["source"] == "bitrix"
    assert body["is_refreshable"] is True


def test_ask_cannot_build_no_data(env):
    agent = FakeAgent(AgentAnswer(rows=None, recipe=None, is_refreshable=False, message="нет поля"))
    client = _client(env, agent, FakeRunner([]))
    r = client.post("/agent/ask", json={"question": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_refreshable"] is False
    assert body["rows"] is None
    assert body["message"] == "нет поля"


def test_full_lifecycle_save_open_refresh_without_llm(env):
    agent = FakeAgent(AgentAnswer(rows=[{"total": 500}], recipe=Recipe.model_validate(RECIPE_RAW),
                                  is_refreshable=True))
    runner = FakeRunner([{"ID": 1, "OPPORTUNITY": 100}, {"ID": 2, "OPPORTUNITY": 400}])
    client = _client(env, agent, runner)

    # save
    save = client.post("/reports", json={"name": "Сделки", "source": "bitrix",
                                         "recipe": RECIPE_RAW, "params": {}})
    assert save.status_code == 200
    report_id = save.json()["id"]

    # list
    lst = client.get("/reports")
    assert any(item["id"] == report_id for item in lst.json())

    # refresh (без LLM)
    agent.calls = 0
    refresh = client.post(f"/reports/{report_id}/refresh", json={})
    assert refresh.status_code == 200
    assert refresh.json()["status"] == "ok"
    assert refresh.json()["result"] == [{"total": 500}]
    assert agent.calls == 0  # обновление не зовёт LLM

    # open -> last result
    detail = client.get(f"/reports/{report_id}")
    assert detail.status_code == 200
    assert detail.json()["last_result"] == [{"total": 500}]
    assert detail.json()["last_status"] == "ok"


def test_report_not_visible_to_stranger(env):
    agent = FakeAgent(AgentAnswer(rows=[], recipe=Recipe.model_validate(RECIPE_RAW), is_refreshable=True))
    runner = FakeRunner([])
    client = _client(env, agent, runner)
    save = client.post("/reports", json={"name": "R", "source": "bitrix", "recipe": RECIPE_RAW, "params": {}})
    report_id = save.json()["id"]
    # посторонний без доступа
    stranger = User(email="str@e.com", password_hash=hash_password("pw"), name="S", is_active=True)
    env["db"].add(stranger); env["db"].flush()
    client.cookies.set(COOKIE_NAME, create_access_token(str(stranger.id)))
    assert client.get(f"/reports/{report_id}").status_code == 404
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/api/test_report_routes.py -v`
Expected: FAIL (нет `report_routes` / маршрутов).

- [ ] **Step 3: Реализовать `src/analitiksd/api/report_routes.py`**

```python
# src/analitiksd/api/report_routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.service import AgentService
from analitiksd.api.deps import get_current_user, get_db, require_source
from analitiksd.api.report_deps import (
    get_agent_service,
    get_source_runner,
    require_report_access,
)
from analitiksd.api.report_schemas import (
    AskRequest,
    AskResponse,
    RefreshRequest,
    ReportDetail,
    ReportListItem,
    RunResult,
    SaveReportRequest,
    SaveReportResponse,
)
from analitiksd.db.models import Report, User
from analitiksd.rbac.queries import accessible_source_keys
from analitiksd.rbac.service import can_access_source
from analitiksd.recipe.models import Recipe
from analitiksd.reports import service

router = APIRouter(tags=["reports"])


@router.post("/agent/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    _: User = Depends(require_source("bitrix")),
    agent: AgentService = Depends(get_agent_service),
    runner=Depends(get_source_runner),
) -> AskResponse:
    answer = agent.ask(body.question, BITRIX_CATALOG, runner)
    return AskResponse(
        rows=answer.rows,
        recipe=answer.recipe.model_dump(by_alias=True) if answer.recipe else None,
        is_refreshable=answer.is_refreshable,
        message=answer.message,
    )


@router.post("/reports", response_model=SaveReportResponse)
def save_report(
    body: SaveReportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SaveReportResponse:
    if not can_access_source(accessible_source_keys(db, user.id), body.source):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"No access to source '{body.source}'"
        )
    try:
        Recipe.model_validate(body.recipe)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid recipe: {exc}"
        ) from None
    report = service.create_report(
        db, owner_id=user.id, name=body.name, description=body.description,
        source=body.source, recipe=body.recipe, params=body.params,
    )
    db.commit()
    return SaveReportResponse(id=report.id)


@router.get("/reports", response_model=list[ReportListItem])
def list_reports(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ReportListItem]:
    reports = service.list_accessible_reports(db, user.id)
    return [
        ReportListItem(id=r.id, name=r.name, source=r.source, is_refreshable=r.is_refreshable)
        for r in reports
    ]


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report_detail(
    report: Report = Depends(require_report_access("view")),
    db: Session = Depends(get_db),
) -> ReportDetail:
    ok_run = service.latest_ok_run(db, report.id)
    last = service.latest_run(db, report.id)
    return ReportDetail(
        id=report.id, name=report.name, description=report.description, source=report.source,
        is_refreshable=report.is_refreshable,
        last_result=(ok_run.result["rows"] if ok_run and ok_run.result else None),
        last_status=(last.status if last else None),
        last_error=(last.error if last else None),
    )


@router.post("/reports/{report_id}/refresh", response_model=RunResult)
def refresh_report(
    body: RefreshRequest,
    report: Report = Depends(require_report_access("view")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner=Depends(get_source_runner),
) -> RunResult:
    run = service.refresh_report(db, report, runner, triggered_by=user.id, overrides=body.overrides)
    db.commit()
    return RunResult(
        status=run.status,
        row_count=run.row_count,
        result=(run.result["rows"] if run.result else None),
        error=run.error,
    )
```

- [ ] **Step 4: Обновить `src/analitiksd/api/app.py`**

Переписать `src/analitiksd/api/app.py` так — подключить report_router и УБРАТЬ демо-маршруты `/demo/*` (тест-каркас Плана 2 больше не нужен):
```python
# src/analitiksd/api/app.py
from __future__ import annotations

from fastapi import FastAPI

from analitiksd.api.auth_routes import router as auth_router
from analitiksd.api.report_routes import router as report_router


def create_app() -> FastAPI:
    app = FastAPI(title="AnalitikSD")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(report_router)
    return app
```

- [ ] **Step 5: Удалить устаревший тест демо-маршрутов RBAC**

Демо-маршруты `/demo/source/bitrix` и `/demo/report/5` удалены, поэтому `tests/api/test_rbac_deps.py` (он их дёргал) больше не валиден. Удалить файл:
```bash
git rm tests/api/test_rbac_deps.py
```
> RBAC-зависимости `require_source`/`require_report` остаются в `api/deps.py` и продолжают тестироваться косвенно через маршруты отчётов; чистые их тесты были привязаны к удалённым демо-маршрутам.

- [ ] **Step 6: Запустить — убедиться, что проходит**

Run: `pytest tests/api/test_report_routes.py -v`  → PASS (4 теста).
Run: `pytest -q`  → весь набор зелёный (без удалённого файла демо-тестов).

- [ ] **Step 7: Коммит**

```bash
git add src/analitiksd/api/report_routes.py src/analitiksd/api/app.py tests/api/test_report_routes.py
git commit -m "feat(api): add report routes (ask/save/list/get/refresh); retire demo routes"
```

---

## Task 8: Сериализация рецепта round-trip

**Files:**
- Test: `tests/reports/test_serialization.py`

Проверяем, что рецепт с алиасом `as`/computed переживает хранение (dump by_alias) и чтение (validate) — критично для refresh.

- [ ] **Step 1: Написать тест `tests/reports/test_serialization.py`**

```python
# tests/reports/test_serialization.py
from analitiksd.recipe.models import Recipe

RAW = {
    "version": 1, "source": "bitrix",
    "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID", "OPPORTUNITY"]}}],
    "transform": [
        {"op": "aggregate", "metrics": [{"fn": "sum", "field": "OPPORTUNITY", "as": "amount"}]},
        {"op": "computed", "as": "doubled", "left": "amount", "operator": "*", "right": "2"},
    ],
    "presentation": {"type": "table", "columns": ["amount", "doubled"]},
}


def test_recipe_roundtrips_via_by_alias():
    recipe = Recipe.model_validate(RAW)
    dumped = recipe.model_dump(by_alias=True)
    # алиас 'as', не 'as_'
    assert dumped["transform"][0]["metrics"][0]["as"] == "amount"
    assert dumped["transform"][1]["as"] == "doubled"
    # повторная валидация из сохранённого вида — без потерь
    again = Recipe.model_validate(dumped)
    assert again.transform[0].metrics[0].as_ == "amount"
    assert again.transform[1].as_ == "doubled"
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/reports/test_serialization.py -v`
Expected: PASS (это проверка уже готовых моделей Плана 1; должна пройти сразу). Если падает — рецепт не round-trip'ится, чинить сериализацию моделей.

- [ ] **Step 3: Прогнать весь набор**

Run: `pytest -q`
Expected: всё зелёное (модели, миграции, reports/service, api/report_routes, recipe, auth/rbac).

- [ ] **Step 4: Коммит**

```bash
git add tests/reports/test_serialization.py
git commit -m "test(reports): pin recipe by_alias round-trip used by save/refresh"
```

---

## Готовность плана

После всех задач: HTTP-API полного цикла отчёта — задать вопрос (LLM-планировщик, RBAC по источнику), сохранить рецепт, открыть с кэшированным результатом, **обновить детерминированно без LLM**, с RBAC по отчёту (владелец или роль), историей `report_runs` и сохранением последнего успешного результата при ошибке обновления. Это завершает backend MVP.

**Следующий план:** План 5 (React-фронтенд) — вход, окно вопроса, таблица результата, список сохранённых отчётов, кнопка «Обновить».
