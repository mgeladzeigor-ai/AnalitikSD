# tests/rbac/test_service.py
import pytest

from analitiksd.rbac.service import can_access_report, can_access_source


@pytest.mark.parametrize(
    "accessible, source, expected",
    [
        ({"bitrix"}, "bitrix", True),
        ({"bitrix", "ut"}, "ut", True),
        (set(), "bitrix", False),
        ({"ut"}, "bitrix", False),
    ],
)
def test_can_access_source(accessible, source, expected):
    assert can_access_source(accessible, source) is expected


@pytest.mark.parametrize(
    "granted, required, expected",
    [
        (["view"], "view", True),
        (["edit"], "view", True),          # edit покрывает view
        (["edit"], "edit", True),
        (["view"], "edit", False),         # view не даёт edit
        ([], "view", False),
        (["view", "edit"], "edit", True),
    ],
)
def test_can_access_report(granted, required, expected):
    assert can_access_report(granted, required) is expected


def test_unknown_required_level_raises():
    with pytest.raises(KeyError):
        can_access_report(["view"], "delete")
