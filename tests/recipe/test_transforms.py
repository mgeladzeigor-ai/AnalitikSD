import pytest

from analitiksd.recipe.models import (
    AggregateOp,
    ComputedOp,
    FilterOp,
    GroupByOp,
    LimitOp,
    SortOp,
)
from analitiksd.recipe.transforms import apply_transforms

ROWS = [
    {"id": 1, "manager": "A", "amount": 100, "closed": "Y"},
    {"id": 2, "manager": "B", "amount": 200, "closed": "N"},
    {"id": 3, "manager": "A", "amount": 300, "closed": "Y"},
]


def test_filter_equality():
    t = [FilterOp(op="filter", where=[{"field": "closed", "operator": "==", "value": "Y"}])]
    out = apply_transforms(ROWS, t)
    assert [r["id"] for r in out] == [1, 3]


def test_filter_greater_than():
    t = [FilterOp(op="filter", where=[{"field": "amount", "operator": ">", "value": 150}])]
    out = apply_transforms(ROWS, t)
    assert [r["id"] for r in out] == [2, 3]


def test_filter_in_operator():
    t = [FilterOp(op="filter", where=[{"field": "manager", "operator": "in", "value": ["B"]}])]
    out = apply_transforms(ROWS, t)
    assert [r["id"] for r in out] == [2]


def test_filter_does_not_mutate_input():
    t = [FilterOp(op="filter", where=[{"field": "closed", "operator": "==", "value": "Y"}])]
    apply_transforms(ROWS, t)
    assert len(ROWS) == 3  # исходный список не изменён


def test_group_by_with_count_and_sum():
    t = [
        GroupByOp(op="group_by", keys=["manager"]),
        AggregateOp(op="aggregate", metrics=[
            {"fn": "count", "as": "deals"},
            {"fn": "sum", "field": "amount", "as": "total"}]),
    ]
    out = apply_transforms(ROWS, t)
    assert out == [
        {"manager": "A", "deals": 2, "total": 400},
        {"manager": "B", "deals": 1, "total": 200},
    ]


def test_aggregate_without_group_by_is_single_group():
    t = [AggregateOp(op="aggregate", metrics=[{"fn": "count", "as": "n"}])]
    out = apply_transforms(ROWS, t)
    assert out == [{"n": 3}]


def test_aggregate_avg_min_max():
    t = [AggregateOp(op="aggregate", metrics=[
        {"fn": "avg", "field": "amount", "as": "avg_amount"},
        {"fn": "min", "field": "amount", "as": "min_amount"},
        {"fn": "max", "field": "amount", "as": "max_amount"}])]
    out = apply_transforms(ROWS, t)
    assert out == [{"avg_amount": 200, "min_amount": 100, "max_amount": 300}]


def test_aggregate_non_count_without_field_raises():
    # sum/avg/min/max требуют поле — иначе тихо вернулось бы 0/None (молча неверный отчёт)
    t = [AggregateOp(op="aggregate", metrics=[{"fn": "sum", "as": "total"}])]
    with pytest.raises(ValueError):
        apply_transforms(ROWS, t)


def test_sort_desc_by_amount():
    t = [SortOp(op="sort", sort=[{"by": "amount", "dir": "desc"}])]
    out = apply_transforms(ROWS, t)
    assert [r["amount"] for r in out] == [300, 200, 100]


def test_sort_multi_key_stable():
    rows = [
        {"g": "A", "n": 2}, {"g": "B", "n": 1}, {"g": "A", "n": 1},
    ]
    t = [SortOp(op="sort", sort=[{"by": "g", "dir": "asc"}, {"by": "n", "dir": "asc"}])]
    out = apply_transforms(rows, t)
    assert out == [{"g": "A", "n": 1}, {"g": "A", "n": 2}, {"g": "B", "n": 1}]


def test_computed_division():
    rows = [{"a": 10, "b": 2}, {"a": 9, "b": 3}]
    t = [ComputedOp(op="computed", **{"as": "ratio"}, left="a", operator="/", right="b")]
    out = apply_transforms(rows, t)
    assert [r["ratio"] for r in out] == [5, 3]


def test_computed_division_by_zero_is_none():
    rows = [{"a": 10, "b": 0}]
    t = [ComputedOp(op="computed", **{"as": "ratio"}, left="a", operator="/", right="b")]
    out = apply_transforms(rows, t)
    assert out[0]["ratio"] is None


def test_computed_with_numeric_literal():
    rows = [{"a": 10}]
    t = [ComputedOp(op="computed", **{"as": "doubled"}, left="a", operator="*", right="2")]
    out = apply_transforms(rows, t)
    assert out[0]["doubled"] == 20


def test_limit():
    t = [LimitOp(op="limit", n=2)]
    out = apply_transforms(ROWS, t)
    assert [r["id"] for r in out] == [1, 2]


def test_computed_field_named_like_float_is_not_literal():
    # колонка с именем "inf" должна читаться как поле, а не как float('inf')
    rows = [{"inf": 5, "x": 2}]
    t = [ComputedOp(op="computed", **{"as": "r"}, left="inf", operator="+", right="x")]
    out = apply_transforms(rows, t)
    assert out[0]["r"] == 7  # 5 + 2, а не inf


def test_computed_scientific_token_is_treated_as_field_not_literal():
    # "1e3" не считаем числовым литералом (неоднозначно) -> трактуем как имя поля
    rows = [{"a": 10}]
    t = [ComputedOp(op="computed", **{"as": "r"}, left="a", operator="*", right="1e3")]
    out = apply_transforms(rows, t)
    assert out[0]["r"] is None  # поля "1e3" нет -> операнд None -> результат None


def test_computed_nan_token_is_not_literal():
    # "nan" как литерал сломал бы детерминизм (nan != nan) -> только поле
    rows = [{"a": 10}]
    t = [ComputedOp(op="computed", **{"as": "r"}, left="a", operator="+", right="nan")]
    out = apply_transforms(rows, t)
    assert out[0]["r"] is None
