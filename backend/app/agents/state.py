from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    session_id: str
    query: str
    ticker: str
    company: str
    intent: str
    timeframe: str
    region: str
    entities: list[dict[str, Any]]
    comparison_data: list[dict[str, Any]]
    research_comparison_data: list[dict[str, Any]]
    market_comparison_data: list[dict[str, Any]]
    sentiment_comparison_data: list[dict[str, Any]]
    financial_evidence: dict[str, Any]
    financial_statements: dict[str, Any]
    needs_clarification: bool
    clarification_question: str
    clarification_options: list[str]
    articles: list[dict[str, Any]]
    market_data: dict[str, Any]
    sentiment: dict[str, Any]
    memory_context: list[dict[str, Any]]
    report: str
    citations: list[dict[str, Any]]
    errors: list[dict[str, Any]]
