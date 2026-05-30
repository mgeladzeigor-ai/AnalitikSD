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
