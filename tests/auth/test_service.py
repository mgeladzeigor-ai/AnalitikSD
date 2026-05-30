# tests/auth/test_service.py
from analitiksd.auth.password import hash_password
from analitiksd.auth.service import authenticate_user, role_names
from analitiksd.db.models import (
    DataSource,
    ReportPerm,
    Role,
    RoleSource,
    User,
    UserRole,
)
from analitiksd.rbac.queries import accessible_source_keys, report_access_levels


def _seed(session):
    user = User(email="a@b.c", password_hash=hash_password("pw"), name="A", is_active=True)
    inactive = User(email="x@y.z", password_hash=hash_password("pw"), name="X", is_active=False)
    analyst = Role(name="analyst")
    src = DataSource(key="bitrix", type="mcp")
    session.add_all([user, inactive, analyst, src])
    session.flush()
    session.add_all([
        UserRole(user_id=user.id, role_id=analyst.id),
        RoleSource(role_id=analyst.id, source_id=src.id),
        ReportPerm(report_id=7, role_id=analyst.id, access="edit"),
    ])
    session.flush()
    return user, inactive, analyst


def test_authenticate_success(db_session):
    user, _, _ = _seed(db_session)
    result = authenticate_user(db_session, "a@b.c", "pw")
    assert result is not None and result.id == user.id


def test_authenticate_wrong_password(db_session):
    _seed(db_session)
    assert authenticate_user(db_session, "a@b.c", "nope") is None


def test_authenticate_unknown_email(db_session):
    _seed(db_session)
    assert authenticate_user(db_session, "missing@b.c", "pw") is None


def test_authenticate_inactive_user(db_session):
    _seed(db_session)
    assert authenticate_user(db_session, "x@y.z", "pw") is None


def test_role_names(db_session):
    user, _, _ = _seed(db_session)
    assert role_names(db_session, user.id) == ["analyst"]


def test_accessible_source_keys(db_session):
    user, _, _ = _seed(db_session)
    assert accessible_source_keys(db_session, user.id) == {"bitrix"}


def test_report_access_levels(db_session):
    user, _, _ = _seed(db_session)
    assert report_access_levels(db_session, user.id, 7) == ["edit"]
    assert report_access_levels(db_session, user.id, 999) == []


def test_queries_isolated_per_user(db_session):
    # другой пользователь без ролей не видит чужих источников/прав
    _user, inactive, _analyst = _seed(db_session)
    assert accessible_source_keys(db_session, inactive.id) == set()
    assert report_access_levels(db_session, inactive.id, 7) == []
    assert role_names(db_session, inactive.id) == []


def test_report_access_levels_unions_multiple_roles(db_session):
    # две роли пользователя дают разные уровни на один отчёт -> объединение
    user, _inactive, analyst = _seed(db_session)  # analyst даёт edit на отчёт 7
    viewer = Role(name="viewer")
    db_session.add(viewer)
    db_session.flush()
    db_session.add_all([
        UserRole(user_id=user.id, role_id=viewer.id),
        ReportPerm(report_id=7, role_id=viewer.id, access="view"),
    ])
    db_session.flush()
    assert set(report_access_levels(db_session, user.id, 7)) == {"view", "edit"}
