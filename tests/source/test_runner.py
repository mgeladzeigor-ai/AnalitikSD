# tests/source/test_runner.py
import httpx
import pytest

from analitiksd.recipe.models import ToolCallStep
from analitiksd.source.runner import BitrixRestRunner


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://p.bitrix24.ru/rest/1/tok")


def test_fetch_collects_all_pages():
    pages = {
        0: {"result": [{"ID": "1"}, {"ID": "2"}], "next": 2, "total": 3},
        2: {"result": [{"ID": "3"}], "total": 3},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.content)
        assert request.url.path.endswith("/crm.deal.list")
        return httpx.Response(200, json=pages[body["start"]])

    runner = BitrixRestRunner("https://p.bitrix24.ru/rest/1/tok", _client(handler))
    step = ToolCallStep(type="tool_call", tool="crm_deal_list", params={"select": ["ID"]})
    rows = runner.fetch(step)
    assert [r["ID"] for r in rows] == ["1", "2", "3"]


def test_fetch_unknown_tool_raises():
    runner = BitrixRestRunner("https://p.bitrix24.ru/rest/1/tok", _client(lambda r: httpx.Response(200, json={"result": []})))
    step = ToolCallStep(type="tool_call", tool="unknown_tool", params={})
    with pytest.raises(ValueError):
        runner.fetch(step)


def test_fetch_http_error_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    runner = BitrixRestRunner("https://p.bitrix24.ru/rest/1/tok", _client(handler))
    step = ToolCallStep(type="tool_call", tool="crm_deal_list", params={})
    with pytest.raises(httpx.HTTPStatusError):
        runner.fetch(step)
