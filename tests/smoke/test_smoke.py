# tests/smoke/test_smoke.py
import os

import httpx
import pytest

from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.decision import CannotBuild
from analitiksd.agent.provider import AnthropicProvider
from analitiksd.config import get_settings
from analitiksd.recipe.models import Recipe
from analitiksd.source.runner import BitrixRestRunner

_NO_LLM = not os.environ.get("ANTHROPIC_API_KEY")
_NO_BITRIX = not os.environ.get("BITRIX_WEBHOOK_URL")


@pytest.mark.skipif(_NO_LLM, reason="ANTHROPIC_API_KEY не задан")
def test_real_provider_builds_valid_recipe():
    import anthropic

    settings = get_settings()
    provider = AnthropicProvider(anthropic.Anthropic(api_key=settings.anthropic_api_key), settings.anthropic_model)
    decision = provider.build_recipe(
        "сколько закрытых сделок по каждому ответственному", BITRIX_CATALOG
    )
    assert isinstance(decision, (Recipe, CannotBuild))
    if isinstance(decision, Recipe):
        assert decision.source == "bitrix"


@pytest.mark.skipif(_NO_BITRIX, reason="BITRIX_WEBHOOK_URL не задан")
def test_real_bitrix_runner_fetches_rows():
    from analitiksd.recipe.models import ToolCallStep

    settings = get_settings()
    with httpx.Client(timeout=30) as http:
        runner = BitrixRestRunner(settings.bitrix_webhook_url, http)
        rows = runner.fetch(ToolCallStep(type="tool_call", tool="crm_deal_list", params={"select": ["ID"]}))
    assert isinstance(rows, list)
