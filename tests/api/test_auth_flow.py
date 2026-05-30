# tests/api/test_auth_flow.py
import os
from datetime import datetime, timedelta, timezone

import jwt
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
