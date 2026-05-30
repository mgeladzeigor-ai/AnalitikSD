# src/analitiksd/source/executor.py
from __future__ import annotations

from typing import Any

from analitiksd.recipe.models import Recipe, ToolCallStep
from analitiksd.recipe.params import substitute
from analitiksd.recipe.transforms import apply_transforms
from analitiksd.source.runner import SourceRunner


def execute_recipe(
    recipe: Recipe,
    runner: SourceRunner,
    *,
    values: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Исполнить рецепт детерминированно: подстановка параметров -> fetch -> трансформации.

    values — плоская карта значений параметров (см. recipe.params.resolve_params).
    Пусто -> в шагах не должно быть плейсхолдеров (иначе substitute поднимет KeyError).
    LLM здесь не участвует.
    """
    values = values or {}
    rows: list[dict[str, Any]] = []
    for step in recipe.steps:
        resolved = substitute(step.model_dump(by_alias=True), values)
        rows.extend(runner.fetch(ToolCallStep.model_validate(resolved)))
    return apply_transforms(rows, recipe.transform)
