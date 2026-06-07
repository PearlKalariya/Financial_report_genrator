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
        "financial_evidence": {
            "facts": [
                {
                    "fact_id": "F1",
                    "metric": "revenue",
                    "value": "13,308",
                    "currency": "INR",
                    "unit": "crore",
                    "period": "Q4 FY25",
                    "source_id": "S1",
                    "confidence": "high",
                },
                {
                    "fact_id": "F2",
                    "metric": "net_profit",
                    "value": "2,599",
                    "currency": "INR",
                    "unit": "crore",
                    "period": "Q4 FY25",
                    "source_id": "S1",
                    "confidence": "high",
                },
            ],
            "confidence": {
                "level": "medium",
                "score": 0.5,
                "verified_metrics": 2,
                "required_metrics": 7,
                "official_sources": 1,
            },
            "freshness": {
                "latest_source_date": "2025-05-01",
                "market_data_as_of": "2025-05-02T00:00:00+00:00",
                "warning": None,
            },
            "source_observations": [
                {
                    "observation_id": "O1",
                    "source_id": "S1",
                    "text": "Revenue growth was 7.1% in constant currency.",
                    "classification": "unclassified_numeric_evidence",
                }
            ],
        },
        "financial_statements": {
            "ticker": "ADANIPOWER.NS",
            "source": "Yahoo Finance",
            "currency": "INR",
            "retrieved_at": "2026-06-07T00:00:00+00:00",
            "statements": {
                "income_statement": {
                    "quarterly": [
                        {
                            "period_end": "2026-03-31",
                            "period_type": "3M",
                            "currency": "INR",
                            "values": {
                                "revenue": 133080000000,
                                "net_income": 25990000000,
                            },
                            "derived": {"net_margin": 0.195295},
                        }
                    ],
                    "annual": [],
                },
                "balance_sheet": {
                    "quarterly": [
                        {
                            "period_end": "2026-03-31",
                            "period_type": "3M",
                            "currency": "INR",
                            "values": {
                                "total_assets": 1000000000000,
                                "total_debt": 250000000000,
                            },
                            "derived": {},
                        }
                    ],
                    "annual": [],
                },
                "cash_flow": {
                    "quarterly": [
                        {
                            "period_end": "2026-03-31",
                            "period_type": "3M",
                            "currency": "INR",
                            "values": {
                                "operating_cash_flow": 40000000000,
                                "capital_expenditure": -10000000000,
                            },
                            "derived": {"free_cash_flow": 30000000000},
                        }
                    ],
                    "annual": [],
                },
            },
        },
        "memory_context": [],
    }

    result = asyncio.run(report_agent.run_report_agent(state))

    assert "Profit and Loss Analysis Report" in result["report"]
    assert "## Profit and Loss Snapshot" in result["report"]
    assert "## Revenue Analysis" in result["report"]
    assert "## Expense Analysis" in result["report"]
    assert "## Profitability Analysis" in result["report"]
    assert "## Balance Sheet" in result["report"]
    assert "## Cash Flow" in result["report"]
    assert "INR 133.08B" in result["report"]
    assert "INR 1.00T" in result["report"]
    assert "INR 30.00B" in result["report"]
    assert "INR 13,308 crore" in result["report"]
    assert "Q4 FY25" in result["report"]
    assert "[F1/S1]" in result["report"]
    assert "[O1/S1] Revenue growth was 7.1% in constant currency." in result["report"]
    assert "Verified metrics: 2 of 7" in result["report"]


def test_macro_market_fallback_explains_transmission_channels(monkeypatch) -> None:
    async def fake_generate_report(*, fallback_report: str, state: dict) -> GeminiReportResult:
        return GeminiReportResult(
            report=fallback_report,
            used_fallback=True,
            model="test-model",
            error="test fallback",
        )

    monkeypatch.setattr(report_agent.gemini_report_service, "generate_report", fake_generate_report)
    state = {
        "query": "What affect does Iran Israel war have on Indian stock market?",
        "ticker": "^NSEI",
        "company": "Indian Stock Market",
        "intent": "macro_market_impact",
        "timeframe": "near term",
        "region": "India",
        "market_data": {
            "price": "INR 25,000.00",
            "change": "-1.20%",
            "source": "Yahoo Finance",
            "symbol": "^NSEI",
        },
        "sentiment": {"label": "negative", "score": -0.2, "confidence": 0.74},
        "articles": [
            {
                "title": "Conflict impact on Indian markets",
                "url": "https://example.com/market",
                "source": "Example",
                "published_at": "Latest",
            }
        ],
        "memory_context": [],
    }

    result = asyncio.run(report_agent.run_report_agent(state))

    assert "Indian Stock Market Macro Impact Report" in result["report"]
    assert "## Transmission Channels" in result["report"]
    assert "Crude oil" in result["report"]
    assert "## Sector Impact" in result["report"]
    assert "MARKET (MARKET)" not in result["report"]
