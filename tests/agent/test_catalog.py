# tests/agent/test_catalog.py
from analitiksd.agent.catalog import BITRIX_CATALOG, SourceCatalog, ToolSpec
from analitiksd.agent.decision import CannotBuild, RecipeDecision
from analitiksd.recipe.models import Recipe


def test_bitrix_catalog_shape():
    assert isinstance(BITRIX_CATALOG, SourceCatalog)
    assert BITRIX_CATALOG.source == "bitrix"
    names = [t.name for t in BITRIX_CATALOG.tools]
    assert "crm_deal_list" in names
    deal = next(t for t in BITRIX_CATALOG.tools if t.name == "crm_deal_list")
    assert isinstance(deal, ToolSpec)
    assert "OPPORTUNITY" in deal.fields


def test_cannot_build_carries_reason():
    cb = CannotBuild(reason="нет данных по этому полю")
    assert cb.reason == "нет данных по этому полю"


def test_recipe_decision_accepts_recipe_or_cannotbuild():
    # обе ветки RecipeDecision (Recipe | CannotBuild) — валидные значения
    recipe = Recipe.model_validate(
        {
            "version": 1,
            "source": "bitrix",
            "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {}}],
            "transform": [],
            "presentation": {"type": "table", "columns": ["ID"]},
        }
    )
    decisions: list[RecipeDecision] = [recipe, CannotBuild("нет данных")]
    assert isinstance(decisions[0], Recipe)
    assert isinstance(decisions[1], CannotBuild)
