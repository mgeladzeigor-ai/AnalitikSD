# tests/conftest.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ПРИНУДИТЕЛЬНО направляем приложение на тест-БД (даже если в shell экспортирован
# dev-DATABASE_URL) — иначе тесты пошли бы по рабочей базе.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg2://localhost/analitiksd_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-key-at-least-32-bytes!!")

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


@pytest.fixture
def db(db_session):
    return db_session
