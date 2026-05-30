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
