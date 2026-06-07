import asyncio
from unittest.mock import AsyncMock

from app.agents import market_data_agent


def test_financial_intent_fetches_structured_statements(monkeypatch) -> None:
    monkeypatch.setattr(
        market_data_agent.market_data_service,
        "get_market_data",
        AsyncMock(return_value={"price": "INR 1.00", "source": "Yahoo Finance"}),
    )
    monkeypatch.setattr(
        market_data_agent.financial_statement_service,
        "get_statements",
        AsyncMock(return_value={"ticker": "AAPL", "statements": {}}),
    )

    result = asyncio.run(
        market_data_agent.run_market_data_agent(
            {
                "query": "financial statements for Apple",
                "ticker": "AAPL",
                "company": "Apple",
                "intent": "financial_statement_analysis",
                "articles": [],
            }
        )
    )

    assert result["financial_statements"]["ticker"] == "AAPL"
    market_data_agent.financial_statement_service.get_statements.assert_awaited_once_with(
        "AAPL"
    )
