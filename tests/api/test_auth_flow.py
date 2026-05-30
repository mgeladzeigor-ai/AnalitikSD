# tests/api/test_auth_flow.py
import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from analitiksd.api.app import create_app
from analitiksd.api.deps import get_db
from analitiksd.auth.password import hash_password
from analitiksd.db.models import User


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


def test_me_with_nonnumeric_sub_is_401(client):
    # валидно подписанный токен с нечисловым sub не должен валить 500
    token = jwt.encode(
        {
            "sub": "not-a-number",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )
    client.cookies.set("access_token", token)
    r = client.get("/auth/me")
    assert r.status_code == 401


def _make_user(db_session, email="u@e.com", password="pw", active=True):
    user = User(email=email, password_hash=hash_password(password), name="U", is_active=active)
    db_session.add(user)
    db_session.flush()
    return user


def test_login_sets_cookie_and_me_returns_profile(client, db_session):
    _make_user(db_session)
    r = client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    assert r.status_code == 200
    assert client.cookies.get("access_token") is not None
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


def test_login_unknown_email_401(client, db_session):
    # незарегистрированный email -> тот же 401 (без утечки причины)
    r = client.post("/auth/login", json={"email": "nobody@e.com", "password": "pw"})
    assert r.status_code == 401


def test_login_overlong_password_rejected(client, db_session):
    # слишком длинный пароль отвергается валидацией (422), не доходит до bcrypt
    r = client.post(
        "/auth/login", json={"email": "u@e.com", "password": "a" * 1000}
    )
    assert r.status_code == 422


def test_logout_clears_cookie(client, db_session):
    _make_user(db_session)
    client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    csrf = client.cookies.get("csrf_token")
    r = client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    me = client.get("/auth/me")
    assert me.status_code == 401


# --- Безопасность cookie: флаг Secure управляется настройкой COOKIE_SECURE ---


def test_login_cookie_secure_flag_honored(client, db_session, monkeypatch):
    _make_user(db_session)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    r = client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    assert r.status_code == 200
    access = next(
        c for c in r.headers.get_list("set-cookie") if c.startswith("access_token=")
    )
    assert "Secure" in access


def test_login_cookie_not_secure_by_default(client, db_session, monkeypatch):
    _make_user(db_session)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    r = client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    assert r.status_code == 200
    access = next(
        c for c in r.headers.get_list("set-cookie") if c.startswith("access_token=")
    )
    assert "Secure" not in access


# --- CSRF: double-submit токен (cookie + заголовок) для изменяющих маршрутов ---


def test_login_sets_csrf_cookie_readable_by_js(client, db_session):
    _make_user(db_session)
    r = client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    assert client.cookies.get("csrf_token") is not None
    csrf_cookie = next(
        c for c in r.headers.get_list("set-cookie") if c.startswith("csrf_token=")
    )
    # JS должен прочитать токен, чтобы отправить его в заголовке -> не HttpOnly
    assert "HttpOnly" not in csrf_cookie


def test_logout_without_csrf_header_is_403(client, db_session):
    _make_user(db_session)
    client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    r = client.post("/auth/logout")
    assert r.status_code == 403
    # сессия не очищена — пользователь всё ещё авторизован
    assert client.get("/auth/me").status_code == 200


def test_logout_csrf_token_mismatch_is_403(client, db_session):
    _make_user(db_session)
    client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    r = client.post("/auth/logout", headers={"X-CSRF-Token": "not-the-real-token"})
    assert r.status_code == 403


def test_logout_clears_csrf_cookie_too(client, db_session):
    _make_user(db_session)
    client.post("/auth/login", json={"email": "u@e.com", "password": "pw"})
    csrf = client.cookies.get("csrf_token")
    client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
    assert client.cookies.get("csrf_token") is None
