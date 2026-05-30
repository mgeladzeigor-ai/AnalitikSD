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
    """SourceRunner поверх входящего вебхука Битрикса (REST), с постраничной выборкой.

    Внимание: переданный httpx.Client ДОЛЖЕН иметь конечный timeout — пагинация
    делает несколько запросов в цикле, и timeout=None может подвесить выборку.
    """

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
            self._raise_for_status(response)
            data = response.json()
            # Битрикс отдаёт result=false при нуле записей -> приводим к [].
            rows.extend(data.get("result") or [])
            next_start = data.get("next")
            # next отсутствует -> конец; защита от зацикливания, если сервер вернул
            # не возрастающий next (например 0) на кривом ответе.
            if next_start is None or next_start <= start:
                break
            start = next_start
        return rows

    def _raise_for_status(self, response: httpx.Response) -> None:
        """raise_for_status, но без утечки секретного токена вебхука в сообщение/лог."""
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            scrubbed = str(exc).replace(self._webhook_url, "<webhook>")
            raise httpx.HTTPStatusError(
                scrubbed, request=exc.request, response=exc.response
            ) from None
