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


def test_refresh_resolves_params_with_overrides(db):
    owner = _user(db, "o7@x")
    recipe = {
        "version": 1, "source": "bitrix",
        "steps": [{"type": "tool_call", "tool": "crm_deal_list",
                   "params": {"filter": {">=CLOSEDATE": "{{period.from}}"}, "select": ["ID"]}}],
        "transform": [], "presentation": {"type": "table", "columns": ["ID"]},
    }
    params = {"period": {"type": "date_range",
                         "default": {"from": "2026-05-01", "to": "2026-05-31"}}}
    report = service.create_report(db, owner_id=owner.id, name="R", description="",
                                   source="bitrix", recipe=recipe, params=params)

    class CapturingRunner:
        def __init__(self):
            self.steps = []

        def fetch(self, step):
            self.steps.append(step)
            return []

    runner = CapturingRunner()
    run = service.refresh_report(
        db, report, runner, triggered_by=owner.id,
        overrides={"period": {"from": "2026-06-01", "to": "2026-06-30"}},
    )
    assert run.status == "ok"
    # override периода подставился в шаг рецепта
    assert runner.steps[0].params["filter"][">=CLOSEDATE"] == "2026-06-01"
