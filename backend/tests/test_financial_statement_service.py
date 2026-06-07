import asyncio
from unittest.mock import AsyncMock

from app.services.financial_statement_service import FinancialStatementService


YAHOO_PAYLOAD = {
    "timeseries": {
        "result": [
            {
                "meta": {"symbol": ["AAPL"], "type": ["quarterlyTotalRevenue"]},
                "quarterlyTotalRevenue": [
                    {
                        "asOfDate": "2025-06-30",
                        "periodType": "3M",
                        "currencyCode": "USD",
                        "reportedValue": {"raw": 100.0},
                    },
                    {
                        "asOfDate": "2025-09-30",
                        "periodType": "3M",
                        "currencyCode": "USD",
                        "reportedValue": {"raw": 120.0},
                    },
                ],
            },
            {
                "meta": {"symbol": ["AAPL"], "type": ["quarterlyGrossProfit"]},
                "quarterlyGrossProfit": [
                    {
                        "asOfDate": "2025-09-30",
                        "periodType": "3M",
                        "currencyCode": "USD",
                        "reportedValue": {"raw": 48.0},
                    }
                ],
            },
            {
                "meta": {"symbol": ["AAPL"], "type": ["quarterlyNetIncome"]},
                "quarterlyNetIncome": [
                    {
                        "asOfDate": "2025-09-30",
                        "periodType": "3M",
                        "currencyCode": "USD",
                        "reportedValue": {"raw": 24.0},
                    }
                ],
            },
            {
                "meta": {"symbol": ["AAPL"], "type": ["annualTotalAssets"]},
                "annualTotalAssets": [
                    {
                        "asOfDate": "2025-09-30",
                        "periodType": "12M",
                        "currencyCode": "USD",
                        "reportedValue": {"raw": 500.0},
                    }
                ],
            },
            {
                "meta": {"symbol": ["AAPL"], "type": ["annualOperatingCashFlow"]},
                "annualOperatingCashFlow": [
                    {
                        "asOfDate": "2025-09-30",
                        "periodType": "12M",
                        "currencyCode": "USD",
                        "reportedValue": {"raw": 80.0},
                    }
                ],
            },
            {
                "meta": {"symbol": ["AAPL"], "type": ["annualCapitalExpenditure"]},
                "annualCapitalExpenditure": [
                    {
                        "asOfDate": "2025-09-30",
                        "periodType": "12M",
                        "currencyCode": "USD",
                        "reportedValue": {"raw": -20.0},
                    }
                ],
            },
        ]
    }
}


def test_normalizes_yahoo_statements_and_derives_metrics() -> None:
    service = FinancialStatementService(alpha_vantage_api_key="")

    bundle = service._normalize_yahoo("AAPL", YAHOO_PAYLOAD)

    quarterly = bundle["statements"]["income_statement"]["quarterly"]
    annual_cash = bundle["statements"]["cash_flow"]["annual"]
    assert [period["period_end"] for period in quarterly] == [
        "2025-09-30",
        "2025-06-30",
    ]
    assert quarterly[0]["values"]["revenue"] == 120.0
    assert quarterly[0]["derived"]["gross_margin"] == 0.4
    assert quarterly[0]["derived"]["net_margin"] == 0.2
    assert quarterly[0]["derived"]["revenue_growth"] == 0.2
    assert annual_cash[0]["derived"]["free_cash_flow"] == 60.0
    assert bundle["source"] == "Yahoo Finance"
    assert bundle["currency"] == "USD"


def test_uses_alpha_vantage_when_yahoo_is_empty() -> None:
    service = FinancialStatementService(alpha_vantage_api_key="alpha-key")
    service._fetch_yahoo = AsyncMock(return_value={})
    service._fetch_alpha_vantage = AsyncMock(
        return_value={
            "income_statement": {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2025-03-31",
                        "reportedCurrency": "INR",
                        "totalRevenue": "1000",
                        "netIncome": "100",
                    }
                ],
                "quarterlyReports": [],
            },
            "balance_sheet": {"annualReports": [], "quarterlyReports": []},
            "cash_flow": {"annualReports": [], "quarterlyReports": []},
        }
    )

    bundle = asyncio.run(service.get_statements("RELIANCE.NS"))

    annual = bundle["statements"]["income_statement"]["annual"]
    assert bundle["source"] == "Alpha Vantage"
    assert annual[0]["values"]["revenue"] == 1000.0
    assert annual[0]["values"]["net_income"] == 100.0


def test_caches_successful_statement_bundle() -> None:
    now = [100.0]
    service = FinancialStatementService(
        alpha_vantage_api_key="",
        clock=lambda: now[0],
    )
    service._fetch_yahoo = AsyncMock(return_value=YAHOO_PAYLOAD)

    first = asyncio.run(service.get_statements("AAPL"))
    second = asyncio.run(service.get_statements("AAPL"))

    assert first == second
    service._fetch_yahoo.assert_awaited_once()


def test_keeps_zero_values_and_ignores_invalid_provider_values() -> None:
    service = FinancialStatementService(alpha_vantage_api_key="")
    payload = {
        "timeseries": {
            "result": [
                {
                    "meta": {"type": ["annualNetIncome"]},
                    "annualNetIncome": [
                        {
                            "asOfDate": "2025-03-31",
                            "periodType": "12M",
                            "currencyCode": "INR",
                            "reportedValue": {"raw": 0},
                        },
                        {
                            "asOfDate": "2024-03-31",
                            "periodType": "12M",
                            "currencyCode": "INR",
                            "reportedValue": {"raw": "not-a-number"},
                        },
                    ],
                }
            ]
        }
    }

    bundle = service._normalize_yahoo("TEST.NS", payload)

    periods = bundle["statements"]["income_statement"]["annual"]
    assert periods[0]["values"]["net_income"] == 0.0
    assert len(periods) == 1


def test_derives_debt_change_only_across_comparable_periods() -> None:
    service = FinancialStatementService(alpha_vantage_api_key="")
    payload = {
        "timeseries": {
            "result": [
                {
                    "meta": {"type": ["annualTotalDebt"]},
                    "annualTotalDebt": [
                        {
                            "asOfDate": "2024-03-31",
                            "periodType": "12M",
                            "currencyCode": "INR",
                            "reportedValue": {"raw": 100.0},
                        },
                        {
                            "asOfDate": "2025-03-31",
                            "periodType": "12M",
                            "currencyCode": "INR",
                            "reportedValue": {"raw": 80.0},
                        },
                    ],
                }
            ]
        }
    }

    bundle = service._normalize_yahoo("TEST.NS", payload)

    latest = bundle["statements"]["balance_sheet"]["annual"][0]
    assert latest["derived"]["total_debt_change"] == -0.2
