import asyncio
import time
from datetime import UTC, datetime
from typing import Callable

import httpx

from app.core.config import settings


YAHOO_METRICS = {
    "income_statement": {
        "TotalRevenue": "revenue",
        "CostOfRevenue": "cost_of_revenue",
        "GrossProfit": "gross_profit",
        "OperatingIncome": "operating_income",
        "NormalizedEBITDA": "ebitda",
        "PretaxIncome": "pretax_income",
        "NetIncome": "net_income",
        "DilutedEPS": "diluted_eps",
    },
    "balance_sheet": {
        "CashCashEquivalentsAndShortTermInvestments": "cash",
        "CurrentAssets": "current_assets",
        "TotalAssets": "total_assets",
        "CurrentLiabilities": "current_liabilities",
        "TotalLiabilitiesNetMinorityInterest": "total_liabilities",
        "TotalDebt": "total_debt",
        "StockholdersEquity": "stockholders_equity",
    },
    "cash_flow": {
        "OperatingCashFlow": "operating_cash_flow",
        "CapitalExpenditure": "capital_expenditure",
        "FreeCashFlow": "free_cash_flow",
        "InvestingCashFlow": "investing_cash_flow",
        "FinancingCashFlow": "financing_cash_flow",
    },
}

ALPHA_METRICS = {
    "income_statement": {
        "totalRevenue": "revenue",
        "costOfRevenue": "cost_of_revenue",
        "grossProfit": "gross_profit",
        "operatingIncome": "operating_income",
        "ebitda": "ebitda",
        "incomeBeforeTax": "pretax_income",
        "netIncome": "net_income",
    },
    "balance_sheet": {
        "cashAndShortTermInvestments": "cash",
        "totalCurrentAssets": "current_assets",
        "totalAssets": "total_assets",
        "totalCurrentLiabilities": "current_liabilities",
        "totalLiabilities": "total_liabilities",
        "shortLongTermDebtTotal": "total_debt",
        "totalShareholderEquity": "stockholders_equity",
    },
    "cash_flow": {
        "operatingCashflow": "operating_cash_flow",
        "capitalExpenditures": "capital_expenditure",
        "cashflowFromInvestment": "investing_cash_flow",
        "cashflowFromFinancing": "financing_cash_flow",
    },
}


class FinancialStatementService:
    def __init__(
        self,
        *,
        alpha_vantage_api_key: str | None = None,
        cache_ttl_seconds: int = 900,
        empty_cache_ttl_seconds: int = 120,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.alpha_vantage_api_key = (
            alpha_vantage_api_key
            if alpha_vantage_api_key is not None
            else settings.alpha_vantage_api_key
        )
        self.cache_ttl_seconds = cache_ttl_seconds
        self.empty_cache_ttl_seconds = empty_cache_ttl_seconds
        self.clock = clock
        self._cache: dict[str, tuple[float, dict]] = {}

    async def get_statements(self, ticker: str) -> dict:
        normalized_ticker = ticker.strip().upper()
        cached = self._cache.get(normalized_ticker)
        now = self.clock()
        if cached and cached[0] > now:
            return cached[1]

        yahoo_payload = await self._fetch_yahoo(normalized_ticker)
        bundle = self._normalize_yahoo(normalized_ticker, yahoo_payload)
        if not self._has_data(bundle) and self.alpha_vantage_api_key:
            alpha_payload = await self._fetch_alpha_vantage(normalized_ticker)
            bundle = self._normalize_alpha(normalized_ticker, alpha_payload)

        ttl = (
            self.cache_ttl_seconds
            if self._has_data(bundle)
            else self.empty_cache_ttl_seconds
        )
        self._cache[normalized_ticker] = (now + ttl, bundle)
        return bundle

    async def _fetch_yahoo(self, ticker: str) -> dict:
        metric_types = []
        for metrics in YAHOO_METRICS.values():
            for provider_metric in metrics:
                metric_types.extend(
                    [f"quarterly{provider_metric}", f"annual{provider_metric}"]
                )
        try:
            async with httpx.AsyncClient(
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as client:
                response = await client.get(
                    "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/"
                    f"v1/finance/timeseries/{ticker}",
                    params={
                        "symbol": ticker,
                        "type": ",".join(metric_types),
                        "period1": 0,
                        "period2": int(time.time()) + 86400,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return {}
        return response.json()

    async def _fetch_alpha_vantage(self, ticker: str) -> dict:
        symbol = ticker.removesuffix(".NS").removesuffix(".BO")
        functions = {
            "income_statement": "INCOME_STATEMENT",
            "balance_sheet": "BALANCE_SHEET",
            "cash_flow": "CASH_FLOW",
        }

        async def fetch(function: str) -> dict:
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    response = await client.get(
                        "https://www.alphavantage.co/query",
                        params={
                            "function": function,
                            "symbol": symbol,
                            "apikey": self.alpha_vantage_api_key,
                        },
                    )
                    response.raise_for_status()
            except httpx.HTTPError:
                return {}
            return response.json()

        responses = await asyncio.gather(
            *(fetch(function) for function in functions.values())
        )
        return {
            statement: payload
            for statement, payload in zip(functions, responses, strict=True)
        }

    def _normalize_yahoo(self, ticker: str, payload: dict) -> dict:
        bundle = self._empty_bundle(ticker, "Yahoo Finance")
        results = payload.get("timeseries", {}).get("result", [])
        type_lookup = {
            provider_metric: (statement, canonical)
            for statement, metrics in YAHOO_METRICS.items()
            for provider_metric, canonical in metrics.items()
        }

        for result in results:
            meta_types = result.get("meta", {}).get("type", [])
            series_type = meta_types[0] if meta_types else ""
            cadence = (
                "quarterly"
                if series_type.startswith("quarterly")
                else "annual"
                if series_type.startswith("annual")
                else None
            )
            if not cadence:
                continue
            provider_metric = series_type.removeprefix(cadence)
            mapping = type_lookup.get(provider_metric)
            if not mapping:
                continue
            statement, canonical = mapping
            for item in result.get(series_type, []):
                value = self._parse_number(
                    item.get("reportedValue", {}).get("raw")
                )
                period_end = item.get("asOfDate")
                if value is None or not period_end:
                    continue
                self._add_value(
                    bundle,
                    statement=statement,
                    cadence=cadence,
                    period_end=period_end,
                    period_type=item.get("periodType", ""),
                    currency=item.get("currencyCode"),
                    metric=canonical,
                    value=value,
                )
        return self._finalize(bundle)

    def _normalize_alpha(self, ticker: str, payload: dict) -> dict:
        bundle = self._empty_bundle(ticker, "Alpha Vantage")
        for statement, metrics in ALPHA_METRICS.items():
            statement_payload = payload.get(statement, {})
            for cadence, provider_key in [
                ("quarterly", "quarterlyReports"),
                ("annual", "annualReports"),
            ]:
                for report in statement_payload.get(provider_key, []):
                    period_end = report.get("fiscalDateEnding")
                    if not period_end:
                        continue
                    for provider_metric, canonical in metrics.items():
                        value = self._parse_number(report.get(provider_metric))
                        if value is None:
                            continue
                        self._add_value(
                            bundle,
                            statement=statement,
                            cadence=cadence,
                            period_end=period_end,
                            period_type="3M" if cadence == "quarterly" else "12M",
                            currency=report.get("reportedCurrency"),
                            metric=canonical,
                            value=value,
                        )
        return self._finalize(bundle)

    def _empty_bundle(self, ticker: str, source: str) -> dict:
        return {
            "ticker": ticker,
            "source": source,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "currency": None,
            "statements": {
                statement: {"quarterly": [], "annual": []}
                for statement in YAHOO_METRICS
            },
        }

    def _add_value(
        self,
        bundle: dict,
        *,
        statement: str,
        cadence: str,
        period_end: str,
        period_type: str,
        currency: str | None,
        metric: str,
        value: float,
    ) -> None:
        periods = bundle["statements"][statement][cadence]
        period = next(
            (item for item in periods if item["period_end"] == period_end),
            None,
        )
        if period is None:
            period = {
                "period_end": period_end,
                "period_type": period_type,
                "currency": currency,
                "values": {},
                "derived": {},
            }
            periods.append(period)
        period["values"][metric] = value

    def _finalize(self, bundle: dict) -> dict:
        currencies = []
        for statement in bundle["statements"].values():
            for cadence in ["quarterly", "annual"]:
                periods = statement[cadence]
                periods.sort(key=lambda item: item["period_end"], reverse=True)
                currencies.extend(
                    period["currency"]
                    for period in periods
                    if period.get("currency")
                )
                self._derive_period_metrics(periods)
        bundle["currency"] = currencies[0] if currencies else None
        return bundle

    def _derive_period_metrics(self, periods: list[dict]) -> None:
        for index, period in enumerate(periods):
            values = period["values"]
            revenue = values.get("revenue")
            if revenue not in (None, 0):
                for metric, derived_name in [
                    ("gross_profit", "gross_margin"),
                    ("operating_income", "operating_margin"),
                    ("net_income", "net_margin"),
                ]:
                    if values.get(metric) is not None:
                        period["derived"][derived_name] = round(
                            values[metric] / revenue,
                            6,
                        )
            if (
                values.get("free_cash_flow") is None
                and values.get("operating_cash_flow") is not None
                and values.get("capital_expenditure") is not None
            ):
                period["derived"]["free_cash_flow"] = (
                    values["operating_cash_flow"]
                    + values["capital_expenditure"]
                )
            if index + 1 < len(periods):
                previous = periods[index + 1]
                if (
                    period.get("currency") == previous.get("currency")
                    and revenue is not None
                    and previous["values"].get("revenue") not in (None, 0)
                ):
                    period["derived"]["revenue_growth"] = round(
                        revenue / previous["values"]["revenue"] - 1,
                        6,
                    )
                total_debt = values.get("total_debt")
                previous_debt = previous["values"].get("total_debt")
                if (
                    period.get("currency") == previous.get("currency")
                    and total_debt is not None
                    and previous_debt not in (None, 0)
                ):
                    period["derived"]["total_debt_change"] = round(
                        total_debt / previous_debt - 1,
                        6,
                    )

    def _parse_number(self, value) -> float | None:
        if value in {None, "", "None", "-"}:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _has_data(self, bundle: dict) -> bool:
        return any(
            periods
            for statement in bundle.get("statements", {}).values()
            for periods in statement.values()
        )


financial_statement_service = FinancialStatementService()
