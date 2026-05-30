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


def test_fetch_single_page_no_next():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": [{"ID": "1"}], "total": 1})

    runner = BitrixRestRunner("https://p.bitrix24.ru/rest/1/tok", _client(handler))
    step = ToolCallStep(type="tool_call", tool="crm_deal_list", params={})
    assert runner.fetch(step) == [{"ID": "1"}]


def test_fetch_empty_result_false_returns_empty_list():
    # Битрикс отдаёт result=false при нуле записей -> не падаем, возвращаем []
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": False, "total": 0})

    runner = BitrixRestRunner("https://p.bitrix24.ru/rest/1/tok", _client(handler))
    step = ToolCallStep(type="tool_call", tool="crm_deal_list", params={})
    assert runner.fetch(step) == []


def test_fetch_stops_on_non_increasing_next():
    # кривой ответ с next=0 не должен зациклить раннер
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": [{"ID": "1"}], "next": 0})

    runner = BitrixRestRunner("https://p.bitrix24.ru/rest/1/tok", _client(handler))
    step = ToolCallStep(type="tool_call", tool="crm_deal_list", params={})
    assert runner.fetch(step) == [{"ID": "1"}]


def test_fetch_error_message_scrubs_webhook_token():
    secret = "https://p.bitrix24.ru/rest/1/SUPERSECRETTOKEN"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    runner = BitrixRestRunner(
        secret, httpx.Client(transport=httpx.MockTransport(handler), base_url=secret)
    )
    step = ToolCallStep(type="tool_call", tool="crm_deal_list", params={})
    with pytest.raises(httpx.HTTPStatusError) as ei:
        runner.fetch(step)
    assert "SUPERSECRETTOKEN" not in str(ei.value)
