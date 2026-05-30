# tests/agent/test_service.py
from analitiksd.agent.catalog import BITRIX_CATALOG
from analitiksd.agent.decision import CannotBuild
from analitiksd.agent.service import AgentAnswer, AgentService
from analitiksd.recipe.models import Recipe

RECIPE_RAW = {
    "version": 1,
    "source": "bitrix",
    "steps": [{"type": "tool_call", "tool": "crm_deal_list", "params": {"select": ["ID", "OPPORTUNITY"]}}],
    "transform": [{"op": "aggregate", "metrics": [{"fn": "sum", "field": "OPPORTUNITY", "as": "total"}]}],
    "presentation": {"type": "table", "columns": ["total"]},
}
ROWS = [{"ID": 1, "OPPORTUNITY": 100}, {"ID": 2, "OPPORTUNITY": 400}]


class FakeProvider:
    def __init__(self, decision):
        self.decision = decision
        self.calls = 0

    def build_recipe(self, question, catalog):
        self.calls += 1
        return self.decision


class FakeRunner:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def fetch(self, step):
        self.calls += 1
        return self.rows


def test_ask_expressible_returns_recipe_and_result():
    provider = FakeProvider(Recipe.model_validate(RECIPE_RAW))
    runner = FakeRunner(ROWS)
    service = AgentService(provider)
    answer = service.ask("сумма сделок", BITRIX_CATALOG, runner)
    assert isinstance(answer, AgentAnswer)
    assert answer.is_refreshable is True
    assert isinstance(answer.recipe, Recipe)
    assert answer.rows == [{"total": 500}]


def test_ask_not_expressible_returns_no_recipe_no_data():
    provider = FakeProvider(CannotBuild("нет такого поля"))
    runner = FakeRunner(ROWS)
    service = AgentService(provider)
    answer = service.ask("вопрос", BITRIX_CATALOG, runner)
    assert answer.is_refreshable is False
    assert answer.recipe is None
    assert answer.rows is None
    assert answer.message == "нет такого поля"
    assert runner.calls == 0  # источник не трогаем, если рецепта нет


def test_execution_does_not_call_llm_again():
    provider = FakeProvider(Recipe.model_validate(RECIPE_RAW))
    runner = FakeRunner(ROWS)
    service = AgentService(provider)
    service.ask("сумма сделок", BITRIX_CATALOG, runner)
    assert provider.calls == 1  # ровно один вызов LLM; исполнение рецепта LLM не зовёт
