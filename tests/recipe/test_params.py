import pytest

from analitiksd.recipe.params import resolve_params, substitute


def test_resolve_date_range_uses_default():
    params = {"period": {"type": "date_range",
                         "default": {"from": "2026-05-01", "to": "2026-05-31"}}}
    assert resolve_params(params, overrides=None) == {
        "period.from": "2026-05-01", "period.to": "2026-05-31"}


def test_resolve_date_range_applies_override():
    params = {"period": {"type": "date_range",
                         "default": {"from": "2026-05-01", "to": "2026-05-31"}}}
    overrides = {"period": {"from": "2026-06-01", "to": "2026-06-30"}}
    assert resolve_params(params, overrides) == {
        "period.from": "2026-06-01", "period.to": "2026-06-30"}


def test_substitute_replaces_exact_placeholder_keeping_type():
    obj = {"filter": {">=CLOSEDATE": "{{period.from}}", "LIMIT": 50}}
    out = substitute(obj, {"period.from": "2026-05-01"})
    assert out == {"filter": {">=CLOSEDATE": "2026-05-01", "LIMIT": 50}}


def test_substitute_replaces_inside_nested_lists():
    obj = {"select": ["ID"], "ranges": ["{{period.from}}", "{{period.to}}"]}
    out = substitute(obj, {"period.from": "a", "period.to": "b"})
    assert out == {"select": ["ID"], "ranges": ["a", "b"]}


def test_substitute_raises_on_unknown_placeholder():
    with pytest.raises(KeyError):
        substitute({"x": "{{missing.key}}"}, {})
