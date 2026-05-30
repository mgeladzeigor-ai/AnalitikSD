# src/analitiksd/agent/service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from analitiksd.agent.catalog import SourceCatalog
from analitiksd.agent.decision import CannotBuild
from analitiksd.agent.provider import ModelProvider
from analitiksd.recipe.models import Recipe
from analitiksd.source.executor import execute_recipe
from analitiksd.source.runner import SourceRunner


@dataclass(frozen=True)
class AgentAnswer:
    rows: list[dict[str, Any]] | None
    recipe: Recipe | None
    is_refreshable: bool
    message: str | None = None


class AgentService:
    """Оркестратор: вопрос -> рецепт (LLM) -> детерминированное исполнение -> ответ."""

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    def ask(
        self,
        question: str,
        catalog: SourceCatalog,
        runner: SourceRunner,
        *,
        values: dict[str, str] | None = None,
    ) -> AgentAnswer:
        decision = self._provider.build_recipe(question, catalog)
        if isinstance(decision, CannotBuild):
            return AgentAnswer(
                rows=None, recipe=None, is_refreshable=False, message=decision.reason
            )
        rows = execute_recipe(decision, runner, values=values)
        return AgentAnswer(rows=rows, recipe=decision, is_refreshable=True)
