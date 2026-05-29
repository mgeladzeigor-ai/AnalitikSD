from analitiksd.recipe.models import FilterOp
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
