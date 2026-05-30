# tests/api/test_report_schemas.py
import pytest
from pydantic import ValidationError

from analitiksd.api.report_schemas import AskRequest, SaveReportRequest


def test_ask_request_requires_nonempty_question():
    assert AskRequest(question="сколько сделок").question
    with pytest.raises(ValidationError):
        AskRequest(question="")


def test_save_report_request_defaults():
    req = SaveReportRequest(name="R", source="bitrix", recipe={"version": 1})
    assert req.description == ""
    assert req.params == {}
