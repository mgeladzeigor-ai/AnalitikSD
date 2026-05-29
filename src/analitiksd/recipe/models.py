from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class ToolCallStep(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)


class FilterCondition(BaseModel):
    field: str
    operator: Literal["==", "!=", ">", ">=", "<", "<=", "in", "contains"]
    value: Any


class Metric(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    fn: Literal["count", "sum", "avg", "min", "max"]
    field: str | None = None
    as_: str = Field(alias="as")


class SortKey(BaseModel):
    by: str
    dir: Literal["asc", "desc"] = "asc"


class FilterOp(BaseModel):
    op: Literal["filter"]
    where: list[FilterCondition]


class GroupByOp(BaseModel):
    op: Literal["group_by"]
    keys: list[str]


class AggregateOp(BaseModel):
    op: Literal["aggregate"]
    metrics: list[Metric]


class SortOp(BaseModel):
    op: Literal["sort"]
    sort: list[SortKey]


class ComputedOp(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    op: Literal["computed"]
    as_: str = Field(alias="as")
    left: str
    operator: Literal["+", "-", "*", "/"]
    right: str


class LimitOp(BaseModel):
    op: Literal["limit"]
    n: int


Transform = Annotated[
    Union[FilterOp, GroupByOp, AggregateOp, SortOp, ComputedOp, LimitOp],
    Field(discriminator="op"),
]


class Presentation(BaseModel):
    type: Literal["table"] = "table"
    columns: list[str]
    sort: list[SortKey] = Field(default_factory=list)


class Recipe(BaseModel):
    version: int = 1
    source: str
    steps: list[ToolCallStep]
    transform: list[Transform] = Field(default_factory=list)
    presentation: Presentation
