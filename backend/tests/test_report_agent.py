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
