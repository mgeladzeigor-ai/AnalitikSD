# tests/reports/test_serialization.py
from analitiksd.recipe.models import Recipe

RAW = {
    "version": 1, "source": "bitrix",
    "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID", "OPPORTUNITY"]}}],
    "transform": [
        {"op": "aggregate", "metrics": [{"fn": "sum", "field": "OPPORTUNITY", "as": "amount"}]},
        {"op": "computed", "as": "doubled", "left": "amount", "operator": "*", "right": "2"},
    ],
    "presentation": {"type": "table", "columns": ["amount", "doubled"]},
}


def test_recipe_roundtrips_via_by_alias():
    recipe = Recipe.model_validate(RAW)
    dumped = recipe.model_dump(by_alias=True)
    # алиас 'as', не 'as_'
    assert dumped["transform"][0]["metrics"][0]["as"] == "amount"
    assert dumped["transform"][1]["as"] == "doubled"
    # повторная валидация из сохранённого вида — без потерь
    again = Recipe.model_validate(dumped)
    assert again.transform[0].metrics[0].as_ == "amount"
    assert again.transform[1].as_ == "doubled"
