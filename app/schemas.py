from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: str | None = None
    error: str | None = None


class QueryResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCall]
    iterations: int
    model: str
