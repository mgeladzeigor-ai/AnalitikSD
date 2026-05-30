# tests/test_db_smoke.py
from sqlalchemy import text


def test_tables_exist(db_session):
    rows = db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public'"
        )
    ).scalars().all()
    assert {"users", "roles", "data_sources", "report_perms"} <= set(rows)
