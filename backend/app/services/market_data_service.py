import httpx

from app.core.config import settings


DEMO_MARKET_DATA = {
    "TCS.NS": {
        "price": "INR 3,920.50",
        "change": "+0.8%",
        "market_cap": "INR 14.2T",
        "pe_ratio": "29.4",
        "volume": "2.1M",
        "fifty_two_week_range": "INR 3,250 - INR 4,320",
        "source": "demo fallback",
    },
    "RELIANCE.NS": {
        "price": "INR 2,875.20",
        "change": "+0.4%",
        "market_cap": "INR 19.4T",
        "pe_ratio": "27.8",
        "volume": "4.8M",
        "fifty_two_week_range": "INR 2,220 - INR 3,025",
        "source": "demo fallback",
    },
    "INFY.NS": {
        "price": "INR 1,525.70",
        "change": "-0.3%",
        "market_cap": "INR 6.3T",
        "pe_ratio": "24.1",
        "volume": "3.5M",
        "fifty_two_week_range": "INR 1,240 - INR 1,730",
        "source": "demo fallback",
    },
}


class MarketDataService:
    def __init__(self, *, alpha_vantage_api_key: str | None = None) -> None:
        self.alpha_vantage_api_key = (
            alpha_vantage_api_key if alpha_vantage_api_key is not None else settings.alpha_vantage_api_key
        )

    async def get_market_data(self, ticker: str) -> dict:
        for candidate in self._ticker_candidates(ticker):
            yahoo_data = await self._fetch_yahoo_quote(candidate)
            if yahoo_data:
                return yahoo_data

        if self.alpha_vantage_api_key:
            data = await self._fetch_alpha_vantage(ticker)
            if data:
                return data

        return DEMO_MARKET_DATA.get(
            ticker,
            {
                "price": "Unavailable",
                "change": "N/A",
                "market_cap": "N/A",
                "pe_ratio": "N/A",
                "volume": "N/A",
                "fifty_two_week_range": "N/A",
                "source": "fallback",
            },
        )

    async def _fetch_yahoo_quote(self, ticker: str) -> dict:
        chart_data = await self._fetch_yahoo_chart(ticker)
        if chart_data:
            return chart_data

        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    "https://query1.finance.yahoo.com/v7/finance/quote",
                    params={"symbols": ticker},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return {}

        results = response.json().get("quoteResponse", {}).get("result", [])
        if not results:
            return {}

        quote = results[0]
        price = quote.get("regularMarketPrice")
        if price is None:
            return {}

        currency = quote.get("currency") or ""
        return {
            "price": self._format_money(price, currency),
            "change": self._format_percent(quote.get("regularMarketChangePercent")),
            "market_cap": self._format_large_number(quote.get("marketCap"), currency),
            "pe_ratio": self._format_decimal(quote.get("trailingPE")),
            "volume": self._format_int(quote.get("regularMarketVolume")),
            "fifty_two_week_range": self._format_price_range(
                quote.get("fiftyTwoWeekLow"),
                quote.get("fiftyTwoWeekHigh"),
                currency,
            ),
            "source": "Yahoo Finance",
            "symbol": quote.get("symbol") or ticker,
            "currency": currency or "N/A",
            "exchange": quote.get("fullExchangeName") or quote.get("exchange") or "N/A",
            "market_time": quote.get("regularMarketTime") or "N/A",
        }

    async def _fetch_yahoo_chart(self, ticker: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                    params={"range": "1d", "interval": "1m"},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return {}

        results = response.json().get("chart", {}).get("result", [])
        if not results:
            return {}

        meta = results[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is None:
            return {}

        currency = meta.get("currency") or ""
        previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")
        change_percent = self._calculate_change_percent(price, previous_close)

        return {
            "price": self._format_money(price, currency),
            "change": change_percent,
            "market_cap": "N/A",
            "pe_ratio": "N/A",
            "volume": self._format_int(meta.get("regularMarketVolume")),
            "fifty_two_week_range": self._format_price_range(
                meta.get("fiftyTwoWeekLow"),
                meta.get("fiftyTwoWeekHigh"),
                currency,
            ),
            "source": "Yahoo Finance",
            "symbol": meta.get("symbol") or ticker,
            "currency": currency or "N/A",
            "exchange": meta.get("fullExchangeName") or meta.get("exchangeName") or "N/A",
            "market_time": meta.get("regularMarketTime") or "N/A",
        }

    async def _fetch_alpha_vantage(self, ticker: str) -> dict:
        symbol = ticker.removesuffix(".NS") if ticker.endswith(".NS") else ticker
        quote, overview = await self._fetch_quote(symbol), await self._fetch_overview(symbol)

        if not quote:
            return {}

        price = quote.get("05. price") or "N/A"
        change_percent = quote.get("10. change percent") or "N/A"
        volume = quote.get("06. volume") or "N/A"

        return {
            "price": price,
            "change": change_percent,
            "market_cap": overview.get("MarketCapitalization") or "N/A",
            "pe_ratio": overview.get("PERatio") or "N/A",
            "volume": volume,
            "fifty_two_week_range": self._format_range(overview),
            "source": "Alpha Vantage",
            "symbol": symbol,
        }

    async def _fetch_quote(self, symbol: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": "GLOBAL_QUOTE",
                        "symbol": symbol,
                        "apikey": self.alpha_vantage_api_key,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return {}

        return response.json().get("Global Quote", {})

    async def _fetch_overview(self, symbol: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": "OVERVIEW",
                        "symbol": symbol,
                        "apikey": self.alpha_vantage_api_key,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return {}

        data = response.json()
        if "Symbol" not in data:
            return {}
        return data

    def _format_range(self, overview: dict) -> str:
        low = overview.get("52WeekLow")
        high = overview.get("52WeekHigh")
        if low and high:
            return f"{low} - {high}"
        return "N/A"

    def _format_money(self, value: float | int | None, currency: str) -> str:
        if value is None:
            return "N/A"
        prefix = f"{currency} " if currency else ""
        return f"{prefix}{float(value):,.2f}"

    def _format_percent(self, value: float | int | None) -> str:
        if value is None:
            return "N/A"
        return f"{float(value):+.2f}%"

    def _format_decimal(self, value: float | int | None) -> str:
        if value is None:
            return "N/A"
        return f"{float(value):.2f}"

    def _format_int(self, value: int | None) -> str:
        if value is None:
            return "N/A"
        return f"{int(value):,}"

    def _format_large_number(self, value: int | float | None, currency: str) -> str:
        if value is None:
            return "N/A"

        amount = float(value)
        units = [("T", 1_000_000_000_000), ("B", 1_000_000_000), ("M", 1_000_000)]
        prefix = f"{currency} " if currency else ""
        for suffix, divisor in units:
            if abs(amount) >= divisor:
                return f"{prefix}{amount / divisor:.2f}{suffix}"
        return f"{prefix}{amount:,.0f}"

    def _format_price_range(
        self,
        low: float | int | None,
        high: float | int | None,
        currency: str,
    ) -> str:
        if low is None or high is None:
            return "N/A"
        return f"{self._format_money(low, currency)} - {self._format_money(high, currency)}"

    def _calculate_change_percent(
        self,
        price: float | int | None,
        previous_close: float | int | None,
    ) -> str:
        if price is None or previous_close in (None, 0):
            return "N/A"

        change = ((float(price) - float(previous_close)) / float(previous_close)) * 100
        return self._format_percent(change)

    def _ticker_candidates(self, ticker: str) -> list[str]:
        clean_ticker = ticker.strip().upper()
        candidates = [clean_ticker]

        if "." not in clean_ticker and clean_ticker.isalpha() and 2 <= len(clean_ticker) <= 10:
            candidates.extend([f"{clean_ticker}.NS", f"{clean_ticker}.BO"])

        deduped: list[str] = []
        for candidate in candidates:
            if candidate not in deduped:
                deduped.append(candidate)
        return deduped


market_data_service = MarketDataService()
