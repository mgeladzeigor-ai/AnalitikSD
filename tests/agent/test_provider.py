# tests/agent/test_provider.py
from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.decision import CannotBuild
from analitiksd.agent.provider import AnthropicProvider
from analitiksd.recipe.models import Recipe

RECIPE_INPUT = {
    "version": 1,
    "source": "bitrix",
    "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID"]}}],
    "transform": [],
    "presentation": {"type": "table", "columns": ["ID"]},
}


class _Block:
    def __init__(self, type, name=None, input=None):
        self.type = type
        self.name = name
        self.input = input


class _Message:
    def __init__(self, content):
        self.content = content


class _FakeMessages:
    def __init__(self, message):
        self._message = message
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._message


class _FakeClient:
    def __init__(self, message):
        self.messages = _FakeMessages(message)


def test_provider_parses_submit_recipe_into_recipe():
    client = _FakeClient(_Message([_Block("tool_use", "submit_recipe", RECIPE_INPUT)]))
    provider = AnthropicProvider(client, "claude-x")
    decision = provider.build_recipe("сколько сделок", BITRIX_CATALOG)
    assert isinstance(decision, Recipe)
    assert decision.source == "bitrix"
    assert client.messages.last_kwargs["tool_choice"] == {"type": "any"}


def test_provider_returns_cannotbuild_on_cannot_build_tool():
    client = _FakeClient(_Message([_Block("tool_use", "cannot_build", {"reason": "нет такого поля"})]))
    provider = AnthropicProvider(client, "claude-x")
    decision = provider.build_recipe("вопрос", BITRIX_CATALOG)
    assert isinstance(decision, CannotBuild)
    assert decision.reason == "нет такого поля"


def test_provider_returns_cannotbuild_on_invalid_recipe():
    bad = {"version": 1, "source": "bitrix"}  # нет steps/presentation
    client = _FakeClient(_Message([_Block("tool_use", "submit_recipe", bad)]))
    provider = AnthropicProvider(client, "claude-x")
    decision = provider.build_recipe("вопрос", BITRIX_CATALOG)
    assert isinstance(decision, CannotBuild)


def test_provider_returns_cannotbuild_when_no_tool_use():
    client = _FakeClient(_Message([_Block("text")]))
    provider = AnthropicProvider(client, "claude-x")
    decision = provider.build_recipe("вопрос", BITRIX_CATALOG)
    assert isinstance(decision, CannotBuild)
