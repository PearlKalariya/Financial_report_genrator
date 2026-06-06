from app.services.evidence_service import FinancialEvidenceService


def test_source_ranking_prefers_company_and_exchange_sources() -> None:
    service = FinancialEvidenceService()
    articles = [
        {
            "title": "Company results discussion",
            "url": "https://finance.yahoo.com/quote/TEST/news",
            "source": "Yahoo Finance",
            "published_at": "2026-05-01",
            "snippet": "General market commentary.",
        },
        {
            "title": "Q4 and FY26 Results",
            "url": "https://www.examplecompany.com/investors/q4-fy26-results",
            "source": "Example Company",
            "published_at": "2026-05-03",
            "snippet": "Official quarterly results.",
        },
        {
            "title": "Exchange filing",
            "url": "https://www.nseindia.com/corporates/filing",
            "source": "NSE",
            "published_at": "2026-05-02",
            "snippet": "Filed financial results.",
        },
    ]

    ranked = service.rank_sources(articles, company="Example Company")

    assert ranked[0]["source_tier"] == "exchange_filing"
    assert ranked[1]["source_tier"] == "company_official"
    assert ranked[-1]["source_tier"] == "financial_aggregator"


def test_source_title_alone_does_not_make_aggregator_official() -> None:
    service = FinancialEvidenceService()

    ranked = service.rank_sources(
        [
            {
                "title": "Company Quarterly Results and Financial Statement",
                "url": "https://trendlyne.com/fundamentals/financials/123/example",
                "source": "Trendlyne",
                "published_at": "2026-05-01",
                "snippet": "Revenue and profit information.",
            }
        ],
        company="Example Company",
    )

    assert ranked[0]["source_tier"] == "financial_aggregator"


def test_extracts_financial_facts_with_period_currency_and_source() -> None:
    service = FinancialEvidenceService()
    articles = [
        {
            "title": "Adani Power announces Q4 FY25 results",
            "url": "https://www.adanipower.com/investors/q4-fy25",
            "source": "Adani Power",
            "published_at": "2025-05-01",
            "snippet": (
                "For Q4 FY25, revenue was INR 13,308 crore, EBITDA was INR 5,098 crore "
                "and PAT was INR 2,599 crore. EBITDA margin was 38.3%."
            ),
            "source_tier": "company_official",
            "source_score": 90,
        }
    ]

    bundle = service.build_evidence(
        company="Adani Power",
        ticker="ADANIPOWER.NS",
        articles=articles,
        market_data={"price": "INR 232.30", "market_time": 1746070200},
    )

    metrics = {fact["metric"]: fact for fact in bundle["facts"]}
    assert metrics["revenue"]["value"] == "13,308"
    assert metrics["revenue"]["currency"] == "INR"
    assert metrics["revenue"]["unit"] == "crore"
    assert metrics["revenue"]["period"] == "Q4 FY25"
    assert metrics["net_profit"]["value"] == "2,599"
    assert metrics["ebitda_margin"]["value"] == "38.3"
    assert metrics["revenue"]["source_id"] == "S1"


def test_evidence_marks_missing_metrics_unavailable() -> None:
    service = FinancialEvidenceService()

    bundle = service.build_evidence(
        company="Example",
        ticker="EXAMPLE",
        articles=[],
        market_data={},
    )

    assert bundle["metric_status"]["revenue"] == "unavailable"
    assert bundle["metric_status"]["ebitda"] == "unavailable"
    assert bundle["confidence"]["level"] == "low"


def test_preserves_source_reported_numeric_statements_without_assuming_metric() -> None:
    service = FinancialEvidenceService()
    articles = [
        {
            "title": "Birlasoft quarterly update",
            "url": "https://example.com/results",
            "source": "Example",
            "published_at": "2026-05-01",
            "snippet": (
                "Revenue growth was 7.1% in constant currency. "
                "Management also reported deal wins of USD 240 million."
            ),
        }
    ]

    bundle = service.build_evidence(
        company="Birlasoft",
        ticker="BSOFT.NS",
        articles=articles,
        market_data={},
    )

    observations = bundle["source_observations"]
    assert observations[0]["source_id"] == "S1"
    assert observations[0]["text"] == "Revenue growth was 7.1% in constant currency."
    assert observations[0]["classification"] == "unclassified_numeric_evidence"
