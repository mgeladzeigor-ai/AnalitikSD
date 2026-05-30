# src/analitiksd/api/report_deps.py
from __future__ import annotations

import httpx
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from analitiksd.agent.provider import AnthropicProvider
from analitiksd.agent.service import AgentService
from analitiksd.api.deps import get_current_user, get_db
from analitiksd.config import get_settings
from analitiksd.db.models import Report, User
from analitiksd.rbac.service import ACCESS_LEVELS
from analitiksd.reports import service
from analitiksd.source.runner import BitrixRestRunner

_BITRIX_TIMEOUT_SECONDS = 30


def require_report_access(access: str):
    """Фабрика зависимости: report_id берётся ИЗ ПУТИ; нет доступа/нет отчёта -> 404.

    404 (а не 403) для чужого отчёта — не раскрываем существование.
    Уровень access проверяется сразу (на старте): неизвестное значение -> ValueError
    при регистрации маршрута, а не KeyError/500 на первом запросе.
    """
    if access not in ACCESS_LEVELS:
        raise ValueError(f"Unknown access level: {access!r}")

    def _dep(
        report_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Report:
        report = service.get_report_or_none(db, report_id)
        if report is None or not service.user_can_access_report(db, user.id, report, access):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        return report

    return _dep


def get_source_runner():
    """Строит реальный BitrixRestRunner из настроек; в тестах переопределяется."""
    settings = get_settings()
    if not settings.bitrix_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Source not configured"
        )
    with httpx.Client(timeout=_BITRIX_TIMEOUT_SECONDS) as http:
        yield BitrixRestRunner(settings.bitrix_webhook_url, http)


def get_agent_service() -> AgentService:
    """Строит реальный AgentService (Anthropic) из настроек; в тестах переопределяется."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM not configured"
        )
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return AgentService(AnthropicProvider(client, settings.anthropic_model))
