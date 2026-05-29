import pytest

from analitiksd.recipe.models import AggregateOp, FilterOp, GroupByOp
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
