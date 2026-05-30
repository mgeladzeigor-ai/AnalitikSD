# src/analitiksd/agent/provider.py
from __future__ import annotations

from typing import Any, Protocol

from pydantic import ValidationError

from analitiksd.agent.catalog import SourceCatalog
from analitiksd.agent.decision import CannotBuild, RecipeDecision
from analitiksd.agent.prompts import (
    CANNOT_BUILD_TOOL,
    SUBMIT_RECIPE_TOOL,
    build_system_prompt,
)
from analitiksd.recipe.models import Recipe

_MAX_TOKENS = 2048


class ModelProvider(Protocol):
    """Планировщик: по вопросу и каталогу источника возвращает рецепт или отказ."""

    def build_recipe(self, question: str, catalog: SourceCatalog) -> RecipeDecision: ...


class AnthropicProvider:
    """ModelProvider поверх Anthropic SDK. Клиент инжектится (тестируемо без пакета)."""

    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def build_recipe(self, question: str, catalog: SourceCatalog) -> RecipeDecision:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=build_system_prompt(catalog),
            tools=[SUBMIT_RECIPE_TOOL, CANNOT_BUILD_TOOL],
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": question}],
        )
        block = _first_tool_use(message.content)
        if block is None:
            return CannotBuild("модель не вызвала инструмент")
        if block.name == "cannot_build":
            reason = block.input.get("reason", "вопрос невыразим рецептом")
            return CannotBuild(reason)
        try:
            return Recipe.model_validate(block.input)
        except ValidationError as exc:
            return CannotBuild(f"невалидный рецепт: {exc}")


def _first_tool_use(content: Any) -> Any:
    for block in content:
        if getattr(block, "type", None) == "tool_use":
            return block
    return None
