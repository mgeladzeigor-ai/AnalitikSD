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


def test_require_report_access_rejects_unknown_level():
    import pytest
    with pytest.raises(ValueError):
        require_report_access("bogus")
