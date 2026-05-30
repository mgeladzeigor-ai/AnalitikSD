# src/analitiksd/agent/prompts.py
from __future__ import annotations

from analitiksd.agent.catalog import SourceCatalog
from analitiksd.recipe.models import Recipe

# Схема инструмента = JSON-схема рецепта (by_alias -> поле "as", не "as_").
SUBMIT_RECIPE_TOOL = {
    "name": "submit_recipe",
    "description": (
        "Вернуть детерминированный рецепт-конвейер, отвечающий на вопрос. "
        "Используй только инструменты и поля из системного описания источника."
    ),
    "input_schema": Recipe.model_json_schema(by_alias=True),
}

CANNOT_BUILD_TOOL = {
    "name": "cannot_build",
    "description": (
        "Вызвать, если вопрос нельзя выразить рецептом из доступных инструментов/полей. "
        "Никаких выдуманных данных."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"reason": {"type": "string"}},
        "required": ["reason"],
    },
}


def build_system_prompt(catalog: SourceCatalog) -> str:
    lines = [
        "Ты — планировщик отчётов. По вопросу пользователя построй детерминированный",
        "рецепт-конвейер (вызовы источника -> трансформации -> представление) и верни его",
        "через инструмент submit_recipe. Если вопрос невыразим — вызови cannot_build.",
        "Не выдумывай данные и не считай сам: цифры даст наш движок, исполнив рецепт.",
        f"\nИсточник: {catalog.source}. Доступные инструменты:",
    ]
    for tool in catalog.tools:
        lines.append(f"- {tool.name}: {tool.description}")
        lines.append(f"  поля: {', '.join(tool.fields)}")
    return "\n".join(lines)
