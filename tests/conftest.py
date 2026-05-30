# tests/conftest.py
from __future__ import annotations

import os
import subprocess

import pytest

# ПРИНУДИТЕЛЬНО направляем приложение на тест-БД (даже если в shell экспортирован
# dev-DATABASE_URL) — иначе тесты пошли бы по рабочей базе.
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
        env={**os.environ},
    )
    engine = create_engine(os.environ["DATABASE_URL"], future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(_engine):
    """Каждый тест — во вложенной транзакции с откатом (изоляция + скорость)."""
    connection = _engine.connect()
    trans = connection.begin()
    factory = sessionmaker(bind=connection, expire_on_commit=False, future=True)
    session: Session = factory()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
