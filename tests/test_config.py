# tests/test_config.py
import pytest

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
    with pytest.raises(KeyError):
        get_settings()
