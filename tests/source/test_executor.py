# tests/source/test_executor.py
import pytest

from analitiksd.recipe.models import Recipe
from analitiksd.source.executor import execute_recipe


class FakeRunner:
    def __init__(self, rows_by_tool):
        self.rows_by_tool = rows_by_tool
        self.calls = []

    def fetch(self, step):
        self.calls.append(step)
        return self.rows_by_tool[step.tool]


RECIPE_RAW = {
    "version": 1,
    "source": "bitrix",
    "steps": [
        {"type": "tool_call", "tool": "crm_deal_list",
         "params": {"filter": {">=CLOSEDATE": "{{period.from}}", "CLOSED": "Y"},
                    "select": ["ID", "ASSIGNED_BY_ID", "OPPORTUNITY"]}}
    ],
    "transform": [
        {"op": "group_by", "keys": ["ASSIGNED_BY_ID"]},
        {"op": "aggregate", "metrics": [
            {"fn": "count", "as": "deals"},
            {"fn": "sum", "field": "OPPORTUNITY", "as": "amount"}]},
        {"op": "sort", "sort": [{"by": "amount", "dir": "desc"}]},
    ],
    "presentation": {"type": "table", "columns": ["ASSIGNED_BY_ID", "deals", "amount"]},
}

SOURCE_ROWS = [
    {"ID": 1, "ASSIGNED_BY_ID": 10, "OPPORTUNITY": 100},
    {"ID": 2, "ASSIGNED_BY_ID": 20, "OPPORTUNITY": 500},
    {"ID": 3, "ASSIGNED_BY_ID": 10, "OPPORTUNITY": 300},
]


def test_execute_runs_fetch_then_transforms():
    recipe = Recipe.model_validate(RECIPE_RAW)
    runner = FakeRunner({"crm_deal_list": SOURCE_ROWS})
    out = execute_recipe(recipe, runner, values={"period.from": "2026-05-01"})
    assert out == [
        {"ASSIGNED_BY_ID": 20, "deals": 1, "amount": 500},
        {"ASSIGNED_BY_ID": 10, "deals": 2, "amount": 400},
    ]


def test_execute_substitutes_params_into_step():
    recipe = Recipe.model_validate(RECIPE_RAW)
    runner = FakeRunner({"crm_deal_list": SOURCE_ROWS})
    execute_recipe(recipe, runner, values={"period.from": "2026-05-01"})
    sent_step = runner.calls[0]
    assert sent_step.params["filter"][">=CLOSEDATE"] == "2026-05-01"


def test_execute_without_placeholders_needs_no_values():
    raw = {
        "version": 1, "source": "bitrix",
        "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID"]}}],
        "transform": [],
        "presentation": {"type": "table", "columns": ["ID"]},
    }
    recipe = Recipe.model_validate(raw)
    runner = FakeRunner({"crm_deal_list": [{"ID": 1}]})
    out = execute_recipe(recipe, runner)
    assert out == [{"ID": 1}]


def test_execute_concatenates_rows_across_steps():
    raw = {
        "version": 1, "source": "bitrix",
        "steps": [
            {"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID"]}},
            {"type": "tool_call", "tool": "crm_lead_list", "params": {"select": ["ID"]}},
        ],
        "transform": [],
        "presentation": {"type": "table", "columns": ["ID"]},
    }
    recipe = Recipe.model_validate(raw)
    runner = FakeRunner({"crm_deal_list": [{"ID": 1}], "crm_lead_list": [{"ID": 2}]})
    out = execute_recipe(recipe, runner)
    assert out == [{"ID": 1}, {"ID": 2}]


def test_execute_empty_steps_returns_empty():
    raw = {
        "version": 1, "source": "bitrix", "steps": [],
        "transform": [], "presentation": {"type": "table", "columns": ["ID"]},
    }
    recipe = Recipe.model_validate(raw)
    runner = FakeRunner({})
    assert execute_recipe(recipe, runner) == []


def test_execute_missing_placeholder_value_raises_keyerror():
    # контракт для Плана 4: плейсхолдер без значения -> KeyError, не тихая подмена
    recipe = Recipe.model_validate(RECIPE_RAW)
    runner = FakeRunner({"crm_deal_list": SOURCE_ROWS})
    with pytest.raises(KeyError):
        execute_recipe(recipe, runner, values={})
