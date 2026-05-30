# tests/api/test_report_routes.py
import pytest
from fastapi.testclient import TestClient

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

    save = client.post("/reports", json={"name": "Сделки", "source": "bitrix",
                                         "recipe": RECIPE_RAW, "params": {}})
    assert save.status_code == 200
    report_id = save.json()["id"]

    lst = client.get("/reports")
    assert any(item["id"] == report_id for item in lst.json())

    agent.calls = 0
    refresh = client.post(f"/reports/{report_id}/refresh", json={})
    assert refresh.status_code == 200
    assert refresh.json()["status"] == "ok"
    assert refresh.json()["result"] == [{"total": 500}]
    assert agent.calls == 0  # обновление не зовёт LLM

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
    stranger = User(email="str@e.com", password_hash=hash_password("pw"), name="S", is_active=True)
    env["db"].add(stranger); env["db"].flush()
    client.cookies.set(COOKIE_NAME, create_access_token(str(stranger.id)))
    assert client.get(f"/reports/{report_id}").status_code == 404
