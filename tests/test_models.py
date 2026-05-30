# tests/test_models.py
from analitiksd.db.base import Base
from analitiksd.db.models import (
    DataSource,
    ReportPerm,
    Role,
    RoleSource,
    User,
    UserRole,
)


def test_all_tables_registered():
    tables = set(Base.metadata.tables)
    assert tables == {
        "users", "roles", "user_roles",
        "data_sources", "role_sources", "report_perms",
        "reports", "report_runs",
    }


def test_user_columns():
    cols = {c.name for c in User.__table__.columns}
    assert {"id", "email", "password_hash", "name", "is_active", "created_at"} <= cols


def test_email_is_unique():
    assert User.__table__.c.email.unique is True


def test_relationship_user_roles():
    # many-to-many через user_roles (строковый secondary резолвится при конфигурации мапперов)
    from sqlalchemy.orm import configure_mappers

    configure_mappers()
    assert User.roles.property.secondary.name == "user_roles"


def test_role_and_source_keys_unique():
    assert Role.__table__.c.name.unique is True
    assert DataSource.__table__.c.key.unique is True


def test_role_sources_relationship_symmetry():
    from sqlalchemy.orm import configure_mappers

    configure_mappers()
    assert Role.sources.property.secondary.name == "role_sources"
    assert DataSource.roles.property.secondary.name == "role_sources"


def test_report_perm_constraints():
    constraints = {c.name for c in ReportPerm.__table__.constraints}
    assert "uq_report_perms_report_role" in constraints
    assert "ck_report_perms_access" in constraints
    # role_id остаётся внешним ключом на roles
    fk_targets = {fk.column.table.name for fk in ReportPerm.__table__.foreign_keys}
    assert fk_targets == {"roles"}


def test_data_source_type_check_constraint():
    constraints = {c.name for c in DataSource.__table__.constraints}
    assert "ck_data_sources_type" in constraints


def test_reports_tables_registered():
    from analitiksd.db.base import Base
    assert "reports" in Base.metadata.tables
    assert "report_runs" in Base.metadata.tables


def test_report_columns():
    from analitiksd.db.models import Report
    cols = {c.name for c in Report.__table__.columns}
    assert {"id", "name", "description", "owner_id", "source", "recipe",
            "params", "is_refreshable", "created_at", "updated_at"} <= cols


def test_report_run_columns_and_status_check():
    from analitiksd.db.models import ReportRun
    cols = {c.name for c in ReportRun.__table__.columns}
    assert {"id", "report_id", "started_at", "finished_at", "status",
            "row_count", "result", "error", "triggered_by"} <= cols
    constraints = {c.name for c in ReportRun.__table__.constraints}
    assert "ck_report_runs_status" in constraints
