# src/analitiksd/source/runner.py
from __future__ import annotations

from typing import Any, Protocol

import httpx

from analitiksd.recipe.models import ToolCallStep

# Маппинг имён инструментов рецепта на REST-методы Битрикса.
_TOOL_METHODS = {
    "crm_deal_list": "crm.deal.list",
}


class SourceRunner(Protocol):
    """Тянет строки источника для одного tool_call-шага рецепта."""

    def fetch(self, step: ToolCallStep) -> list[dict[str, Any]]: ...


class BitrixRestRunner:
    """SourceRunner поверх входящего вебхука Битрикса (REST), с постраничной выборкой."""

    def __init__(self, webhook_url: str, http: httpx.Client) -> None:
        self._webhook_url = webhook_url.rstrip("/")
        self._http = http

    def fetch(self, step: ToolCallStep) -> list[dict[str, Any]]:
        method = _TOOL_METHODS.get(step.tool)
        if method is None:
            raise ValueError(f"Unknown tool: {step.tool}")
        rows: list[dict[str, Any]] = []
        start = 0
        while True:
            payload = {**step.params, "start": start}
            response = self._http.post(f"{self._webhook_url}/{method}", json=payload)
            response.raise_for_status()
            data = response.json()
            rows.extend(data.get("result", []))
            next_start = data.get("next")
            if next_start is None:
                break
            start = next_start
        return rows
