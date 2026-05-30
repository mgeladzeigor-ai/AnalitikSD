import pytest
from pydantic import ValidationError

from analitiksd.recipe.models import AggregateOp, FilterOp, LimitOp, Recipe


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


def test_limit_rejects_negative_n():
    # n<0 дал бы rows[:-1] (тихо отбросил бы строки) — отвергаем на валидации
    with pytest.raises(ValidationError):
        LimitOp(op="limit", n=-1)


def test_limit_allows_zero():
    assert LimitOp(op="limit", n=0).n == 0


def test_recipe_rejects_unknown_version():
    raw = {
        "version": 99,
        "source": "bitrix",
        "steps": [{"type": "tool_call", "tool": "t", "params": {}}],
        "presentation": {"type": "table", "columns": ["x"]},
    }
    with pytest.raises(ValidationError):
        Recipe.model_validate(raw)
