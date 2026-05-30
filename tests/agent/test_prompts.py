# tests/agent/test_prompts.py
from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.prompts import (
    CANNOT_BUILD_TOOL,
    SUBMIT_RECIPE_TOOL,
    build_system_prompt,
)


def test_submit_recipe_tool_uses_recipe_schema():
    assert SUBMIT_RECIPE_TOOL["name"] == "submit_recipe"
    schema = SUBMIT_RECIPE_TOOL["input_schema"]
    assert schema["type"] == "object"
    assert "source" in schema["properties"]
    assert "transform" in schema["properties"]


def test_cannot_build_tool_requires_reason():
    assert CANNOT_BUILD_TOOL["name"] == "cannot_build"
    assert "reason" in CANNOT_BUILD_TOOL["input_schema"]["required"]


def test_system_prompt_mentions_catalog_tools():
    prompt = build_system_prompt(BITRIX_CATALOG)
    assert "crm_deal_list" in prompt
    assert "OPPORTUNITY" in prompt
