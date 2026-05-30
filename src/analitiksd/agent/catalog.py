# src/analitiksd/agent/catalog.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    fields: list[str]


@dataclass(frozen=True)
class SourceCatalog:
    """Описание доступных инструментов/полей источника — кладётся в промпт планировщика."""

    source: str
    tools: list[ToolSpec]


# MVP: единственный источник — Битрикс, единственный инструмент — список сделок.
BITRIX_CATALOG = SourceCatalog(
    source="bitrix",
    tools=[
        ToolSpec(
            name="crm_deal_list",
            description=(
                "Список сделок CRM. params.filter — словарь условий Битрикса "
                "(например {'>=CLOSEDATE': 'YYYY-MM-DD', 'CLOSED': 'Y'}); "
                "params.select — список полей."
            ),
            fields=[
                "ID",
                "ASSIGNED_BY_ID",
                "OPPORTUNITY",
                "CLOSEDATE",
                "DATE_CREATE",
                "STAGE_ID",
                "CLOSED",
            ],
        ),
    ],
)
