from analitiksd.recipe.models import Recipe, FilterOp, AggregateOp


def test_parse_recipe_from_dict():
    raw = {
        "version": 1,
        "source": "bitrix",
        "steps": [
            {"type": "tool_call", "tool": "crm_deal_list",
             "params": {"filter": {"CLOSED": "Y"}, "select": ["ID", "ASSIGNED_BY_ID", "OPPORTUNITY"]}}
        ],
        "transform": [
            {"op": "filter", "where": [{"field": "CLOSED", "operator": "==", "value": "Y"}]},
            {"op": "group_by", "keys": ["ASSIGNED_BY_ID"]},
            {"op": "aggregate", "metrics": [
                {"fn": "count", "as": "deals"},
                {"fn": "sum", "field": "OPPORTUNITY", "as": "amount"}]},
        ],
        "presentation": {"type": "table", "columns": ["ASSIGNED_BY_ID", "deals", "amount"],
                         "sort": [{"by": "amount", "dir": "desc"}]},
    }

    recipe = Recipe.model_validate(raw)

    assert recipe.source == "bitrix"
    assert recipe.steps[0].tool == "crm_deal_list"
    assert isinstance(recipe.transform[0], FilterOp)
    assert recipe.transform[0].where[0].field == "CLOSED"
    assert isinstance(recipe.transform[2], AggregateOp)
    assert recipe.transform[2].metrics[0].as_ == "deals"
    assert recipe.transform[2].metrics[1].field == "OPPORTUNITY"
    assert recipe.presentation.sort[0].by == "amount"
    assert recipe.presentation.sort[0].dir == "desc"
