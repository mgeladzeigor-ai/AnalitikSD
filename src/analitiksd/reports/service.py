# src/analitiksd/reports/service.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from analitiksd.db.models import Report, ReportPerm, ReportRun, UserRole
from analitiksd.rbac.queries import report_access_levels
from analitiksd.rbac.service import can_access_report


def create_report(
    session: Session,
    *,
    owner_id: int,
    name: str,
    description: str,
    source: str,
    recipe: dict,
    params: dict,
) -> Report:
    report = Report(
        owner_id=owner_id, name=name, description=description, source=source,
        recipe=recipe, params=params, is_refreshable=True,
    )
    session.add(report)
    session.flush()
    return report


def get_report_or_none(session: Session, report_id: int) -> Report | None:
    return session.get(Report, report_id)


def user_can_access_report(
    session: Session, user_id: int, report: Report, access: str
) -> bool:
    """Доступ = владелец ИЛИ роль пользователя имеет нужный уровень в report_perms."""
    if report.owner_id == user_id:
        return True
    levels = report_access_levels(session, user_id, report.id)
    return can_access_report(levels, access)


def list_accessible_reports(session: Session, user_id: int) -> list[Report]:
    """Отчёты, где пользователь владелец ИЛИ есть report_perm через его роли."""
    owned = session.execute(
        select(Report).where(Report.owner_id == user_id)
    ).scalars().all()
    shared = session.execute(
        select(Report)
        .join(ReportPerm, Report.id == ReportPerm.report_id)
        .join(UserRole, UserRole.role_id == ReportPerm.role_id)
        .where(UserRole.user_id == user_id)
    ).scalars().all()
    by_id = {r.id: r for r in [*owned, *shared]}
    return sorted(by_id.values(), key=lambda r: r.id)


def latest_run(session: Session, report_id: int) -> ReportRun | None:
    return session.execute(
        select(ReportRun).where(ReportRun.report_id == report_id)
        .order_by(ReportRun.id.desc()).limit(1)
    ).scalar_one_or_none()


def latest_ok_run(session: Session, report_id: int) -> ReportRun | None:
    return session.execute(
        select(ReportRun).where(ReportRun.report_id == report_id, ReportRun.status == "ok")
        .order_by(ReportRun.id.desc()).limit(1)
    ).scalar_one_or_none()
