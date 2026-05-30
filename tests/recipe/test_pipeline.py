from analitiksd.recipe.models import Recipe
from analitiksd.recipe.params import resolve_params, substitute
from analitiksd.recipe.transforms import apply_transforms

RECIPE_RAW = {
    "version": 1,
    "source": "bitrix",
    "steps": [
        {"type": "tool_call", "tool": "crm_deal_list",
         "params": {"filter": {">=CLOSEDATE": "{{period.from}}",
                               "<=CLOSEDATE": "{{period.to}}", "CLOSED": "Y"},
                    "select": ["ID", "ASSIGNED_BY_ID", "OPPORTUNITY"]}}
    ],
    "transform": [
        {"op": "group_by", "keys": ["ASSIGNED_BY_ID"]},
        {"op": "aggregate", "metrics": [
            {"fn": "count", "as": "deals"},
            {"fn": "sum", "field": "OPPORTUNITY", "as": "amount"}]},
        {"op": "sort", "sort": [{"by": "amount", "dir": "desc"}]},
    ],
    "presentation": {"type": "table",
                     "columns": ["ASSIGNED_BY_ID", "deals", "amount"],
                     "sort": [{"by": "amount", "dir": "desc"}]},
}

PARAMS = {"period": {"type": "date_range",
                     "default": {"from": "2026-05-01", "to": "2026-05-31"}}}

# Имитация ответа источника (в следующих планах его отдаёт MCP-раннер):
SOURCE_ROWS = [
    {"ID": 1, "ASSIGNED_BY_ID": 10, "OPPORTUNITY": 100},
    {"ID": 2, "ASSIGNED_BY_ID": 20, "OPPORTUNITY": 500},
    {"ID": 3, "ASSIGNED_BY_ID": 10, "OPPORTUNITY": 300},
]


def test_param_substitution_into_steps():
    recipe = Recipe.model_validate(RECIPE_RAW)
    values = resolve_params(PARAMS, overrides=None)
    step = substitute(recipe.steps[0].model_dump(), values)
    assert step["params"]["filter"][">=CLOSEDATE"] == "2026-05-01"
    assert step["params"]["filter"]["<=CLOSEDATE"] == "2026-05-31"
    # не-плейсхолдерное содержимое должно пережить подстановку без изменений
    assert step["params"]["filter"]["CLOSED"] == "Y"
    assert step["params"]["select"] == ["ID", "ASSIGNED_BY_ID", "OPPORTUNITY"]


def test_param_override_flows_through_pipeline():
    recipe = Recipe.model_validate(RECIPE_RAW)
    overrides = {"period": {"from": "2026-06-01", "to": "2026-06-30"}}
    values = resolve_params(PARAMS, overrides)
    step = substitute(recipe.steps[0].model_dump(), values)
    assert step["params"]["filter"][">=CLOSEDATE"] == "2026-06-01"
    assert step["params"]["filter"]["<=CLOSEDATE"] == "2026-06-30"


def test_full_pipeline_produces_expected_report():
    recipe = Recipe.model_validate(RECIPE_RAW)
    out = apply_transforms(SOURCE_ROWS, recipe.transform)
    assert out == [
        {"ASSIGNED_BY_ID": 20, "deals": 1, "amount": 500},
        {"ASSIGNED_BY_ID": 10, "deals": 2, "amount": 400},
    ]


def test_pipeline_is_deterministic():
    recipe = Recipe.model_validate(RECIPE_RAW)
    first = apply_transforms(SOURCE_ROWS, recipe.transform)
    second = apply_transforms(SOURCE_ROWS, recipe.transform)
    assert first == second


def test_pipeline_independent_of_input_row_order():
    # детерминизм сильнее тавтологии: результат не должен зависеть от порядка
    # прихода строк из источника (group_by + сортировка дают стабильный отчёт).
    recipe = Recipe.model_validate(RECIPE_RAW)
    reordered = [SOURCE_ROWS[2], SOURCE_ROWS[0], SOURCE_ROWS[1]]
    assert apply_transforms(reordered, recipe.transform) == apply_transforms(
        SOURCE_ROWS, recipe.transform
    )
