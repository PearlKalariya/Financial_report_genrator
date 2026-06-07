from pathlib import Path
import asyncio
from unittest.mock import AsyncMock

from app.memory.store import PersistentReportStore
from app.services.market_data_service import MarketDataService
from app.services.search_service import SearchService
from app.schemas.events import StreamEvent


def test_search_service_returns_fallback_sources_without_api_keys() -> None:
    service = SearchService(tavily_api_key="", serper_api_key="", max_results=3)

    articles = asyncio.run(
        service.search(company="Tata Consultancy Services", ticker="TCS.NS", query="TCS outlook")
    )

    assert articles
    assert articles[0]["url"].startswith("https://")
    assert "title" in articles[0]


def test_market_data_service_returns_fallback_metrics_without_api_key() -> None:
    service = MarketDataService(alpha_vantage_api_key="")

    metrics = asyncio.run(service.get_market_data("TCS.NS"))

    assert metrics["price"]
    assert metrics["source"]


def test_market_data_service_prefers_yahoo_for_nse_tickers() -> None:
    service = MarketDataService(alpha_vantage_api_key="alpha-key")
    service._fetch_yahoo_quote = AsyncMock(
        return_value={
            "price": "INR 3,550.25",
            "change": "+1.20%",
            "market_cap": "INR 4.8T",
            "pe_ratio": "31.2",
            "volume": "1,234,567",
            "fifty_two_week_range": "INR 2,900.00 - INR 3,900.00",
            "source": "Yahoo Finance",
            "currency": "INR",
            "exchange": "NSI",
        }
    )
    service._fetch_alpha_vantage = AsyncMock(return_value={"price": "999.00", "source": "Alpha Vantage"})

    metrics = asyncio.run(service.get_market_data("LT.NS"))

    assert metrics["price"] == "INR 3,550.25"
    assert metrics["source"] == "Yahoo Finance"
    service._fetch_yahoo_quote.assert_awaited_once_with("LT.NS")
    service._fetch_alpha_vantage.assert_not_awaited()


def test_market_data_service_tries_exchange_variants_for_bare_symbols() -> None:
    service = MarketDataService(alpha_vantage_api_key="")
    service._fetch_yahoo_quote = AsyncMock(
        side_effect=[
            {},
            {
                "price": "INR 812.40",
                "change": "+0.75%",
                "market_cap": "INR 7.2T",
                "pe_ratio": "10.5",
                "volume": "9,876,543",
                "fifty_two_week_range": "INR 650.00 - INR 860.00",
                "source": "Yahoo Finance",
                "currency": "INR",
                "exchange": "NSE",
                "symbol": "SBIN.NS",
            },
        ]
    )

    metrics = asyncio.run(service.get_market_data("SBIN"))

    assert metrics["price"] == "INR 812.40"
    assert metrics["symbol"] == "SBIN.NS"
    assert service._fetch_yahoo_quote.await_args_list[0].args == ("SBIN",)
    assert service._fetch_yahoo_quote.await_args_list[1].args == ("SBIN.NS",)


def test_persistent_report_store_writes_history_to_disk(tmp_path: Path) -> None:
    store = PersistentReportStore(storage_path=tmp_path)

    record = store.add(
        session_id="session-1",
        query="What is the outlook for TCS?",
        ticker="TCS.NS",
        company="Tata Consultancy Services",
        report="Report body",
        citations=[],
    )

    reloaded = PersistentReportStore(storage_path=tmp_path)

    assert record.report_id
    assert reloaded.list_by_session("session-1")[0].ticker == "TCS.NS"


def test_stream_event_supports_structured_financial_statements() -> None:
    event = StreamEvent(
        type="financial_statements",
        data={
            "ticker": "AAPL",
            "statements": {
                "income_statement": {
                    "quarterly": [{"period_end": "2025-09-30", "values": {"revenue": 100}}],
                    "annual": [],
                }
            },
        },
    )

    payload = event.model_dump(exclude_none=True)

    assert payload["type"] == "financial_statements"
    assert payload["data"]["ticker"] == "AAPL"
