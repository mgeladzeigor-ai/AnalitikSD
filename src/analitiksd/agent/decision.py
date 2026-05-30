# src/analitiksd/agent/decision.py
from __future__ import annotations

from dataclasses import dataclass

from analitiksd.recipe.models import Recipe


@dataclass(frozen=True)
class CannotBuild:
    """Вопрос не выразим рецептом — честный отказ с причиной, без выдуманных данных."""

    reason: str


# Решение планировщика: либо валидный рецепт, либо отказ.
RecipeDecision = Recipe | CannotBuild
