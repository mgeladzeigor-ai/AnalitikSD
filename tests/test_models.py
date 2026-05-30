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
