# src/analitiksd/api/report_schemas.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    rows: list[dict[str, Any]] | None
    recipe: dict[str, Any] | None
    is_refreshable: bool
    message: str | None = None


class SaveReportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1024)
    source: str = Field(min_length=1, max_length=64)
    recipe: dict[str, Any]
    params: dict[str, Any] = Field(default_factory=dict)


class SaveReportResponse(BaseModel):
    id: int


class ReportListItem(BaseModel):
    id: int
    name: str
    source: str
    is_refreshable: bool


class ReportDetail(BaseModel):
    id: int
    name: str
    description: str
    source: str
    is_refreshable: bool
    last_result: list[dict[str, Any]] | None = None
    last_status: str | None = None
    last_error: str | None = None


class RefreshRequest(BaseModel):
    overrides: dict[str, Any] | None = None


class RunResult(BaseModel):
    status: str
    row_count: int | None = None
    result: list[dict[str, Any]] | None = None
    error: str | None = None
