from typing import Any, Literal

from pydantic import BaseModel


class StreamEvent(BaseModel):
    type: Literal[
        "status",
        "section",
        "delta",
        "citation",
        "financial_statements",
        "done",
        "error",
    ]
    content: str | None = None
    title: str | None = None
    agent: str | None = None
    message: str | None = None
    url: str | None = None
    data: dict[str, Any] | None = None
