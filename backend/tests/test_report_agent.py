import asyncio

from app.agents import report_agent
from app.services.llm_service import GeminiReportResult


def test_comparison_report_fallback_includes_all_companies(monkeypatch) -> None:
    async def fake_generate_report(*, fallback_report: str, state: dict) -> GeminiReportResult:
        return GeminiReportResult(
            report=fallback_report,
            used_fallback=True,
            model="test-model",
            error="test fallback",
        )

    monkeypatch.setattr(report_agent.gemini_report_service, "generate_report", fake_generate_report)

    state = {
        "query": "Compare meta, google and amazon.",
        "intent": "comparison",
        "timeframe": "near term",
        "comparison_data": [
            {
                "ticker": "META",
                "company": "Meta Platforms",
                "articles": [],
                "market_data": {"price": "USD 1.00", "change": "+1.00%", "source": "Yahoo Finance"},
                "sentiment": {"label": "positive", "score": 0.2},
            },
            {
                "ticker": "GOOGL",
                "company": "Alphabet",
                "articles": [],
                "market_data": {"price": "USD 2.00", "change": "+2.00%", "source": "Yahoo Finance"},
                "sentiment": {"label": "neutral", "score": 0},
            },
            {
                "ticker": "AMZN",
                "company": "Amazon",
                "articles": [],
                "market_data": {"price": "USD 3.00", "change": "-1.00%", "source": "Yahoo Finance"},
                "sentiment": {"label": "negative", "score": -0.2},
            },
        ],
    }

    result = asyncio.run(report_agent.run_report_agent(state))

    assert "Meta Platforms vs Alphabet vs Amazon Comparison Report" in result["report"]
    assert "META" in result["report"]
    assert "GOOGL" in result["report"]
    assert "AMZN" in result["report"]
    assert "instead of analyzing only the first ticker" in result["report"]


def test_financial_statement_report_fallback_uses_profit_and_loss_sections(monkeypatch) -> None:
    async def fake_generate_report(*, fallback_report: str, state: dict) -> GeminiReportResult:
        return GeminiReportResult(
            report=fallback_report,
            used_fallback=True,
            model="test-model",
            error="test fallback",
        )

    monkeypatch.setattr(report_agent.gemini_report_service, "generate_report", fake_generate_report)

    state = {
        "query": "generate profit and loss report for Adani Power",
        "ticker": "ADANIPOWER.NS",
        "company": "Adani Power",
        "intent": "financial_statement_analysis",
        "timeframe": "near term",
        "market_data": {"price": "INR 232.30", "change": "-0.09%", "source": "Yahoo Finance"},
        "sentiment": {"label": "neutral", "score": 0},
        "articles": [
            {
                "title": "Adani Power quarterly results",
                "url": "https://example.com/results",
                "source": "Example",
                "published_at": "Latest",
                "snippet": "Revenue, EBITDA and PAT details from quarterly results.",
            }
        ],
        "memory_context": [],
    }

    result = asyncio.run(report_agent.run_report_agent(state))

    assert "Profit and Loss Analysis Report" in result["report"]
    assert "## Profit and Loss Snapshot" in result["report"]
    assert "## Revenue Analysis" in result["report"]
    assert "## Expense Analysis" in result["report"]
    assert "## Profitability Analysis" in result["report"]
    assert "Balance Sheet" not in result["report"]
