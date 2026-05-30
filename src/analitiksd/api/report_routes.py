# src/analitiksd/api/report_routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.service import AgentService
from analitiksd.api.deps import get_current_user, get_db, require_source
from analitiksd.api.report_deps import (
    get_agent_service,
    get_source_runner,
    require_report_access,
)
from analitiksd.api.report_schemas import (
    AskRequest,
    AskResponse,
    RefreshRequest,
    ReportDetail,
    ReportListItem,
    RunResult,
    SaveReportRequest,
    SaveReportResponse,
)
from analitiksd.db.models import Report, User
from analitiksd.rbac.queries import accessible_source_keys
from analitiksd.rbac.service import can_access_source
from analitiksd.recipe.models import Recipe
from analitiksd.reports import service

router = APIRouter(tags=["reports"])


@router.post("/agent/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    _: User = Depends(require_source("bitrix")),
    agent: AgentService = Depends(get_agent_service),
    runner=Depends(get_source_runner),
) -> AskResponse:
    answer = agent.ask(body.question, BITRIX_CATALOG, runner)
    return AskResponse(
        rows=answer.rows,
        recipe=answer.recipe.model_dump(by_alias=True) if answer.recipe else None,
        is_refreshable=answer.is_refreshable,
        message=answer.message,
    )


@router.post("/reports", response_model=SaveReportResponse)
def save_report(
    body: SaveReportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SaveReportResponse:
    if not can_access_source(accessible_source_keys(db, user.id), body.source):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"No access to source '{body.source}'"
        )
    try:
        Recipe.model_validate(body.recipe)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid recipe: {exc}"
        ) from None
    report = service.create_report(
        db, owner_id=user.id, name=body.name, description=body.description,
        source=body.source, recipe=body.recipe, params=body.params,
    )
    db.commit()
    return SaveReportResponse(id=report.id)


@router.get("/reports", response_model=list[ReportListItem])
def list_reports(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ReportListItem]:
    reports = service.list_accessible_reports(db, user.id)
    return [
        ReportListItem(id=r.id, name=r.name, source=r.source, is_refreshable=r.is_refreshable)
        for r in reports
    ]


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report_detail(
    report: Report = Depends(require_report_access("view")),
    db: Session = Depends(get_db),
) -> ReportDetail:
    ok_run = service.latest_ok_run(db, report.id)
    last = service.latest_run(db, report.id)
    return ReportDetail(
        id=report.id, name=report.name, description=report.description, source=report.source,
        is_refreshable=report.is_refreshable,
        last_result=(ok_run.result["rows"] if ok_run and ok_run.result else None),
        last_status=(last.status if last else None),
        last_error=(last.error if last else None),
    )


@router.post("/reports/{report_id}/refresh", response_model=RunResult)
def refresh_report(
    body: RefreshRequest,
    report: Report = Depends(require_report_access("view")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner=Depends(get_source_runner),
) -> RunResult:
    run = service.refresh_report(db, report, runner, triggered_by=user.id, overrides=body.overrides)
    db.commit()
    return RunResult(
        status=run.status,
        row_count=run.row_count,
        result=(run.result["rows"] if run.result else None),
        error=run.error,
    )
