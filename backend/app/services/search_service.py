import httpx

from app.core.config import settings


class SearchService:
    def __init__(
        self,
        *,
        tavily_api_key: str | None = None,
        serper_api_key: str | None = None,
        max_results: int | None = None,
    ) -> None:
        self.tavily_api_key = tavily_api_key if tavily_api_key is not None else settings.tavily_api_key
        self.serper_api_key = serper_api_key if serper_api_key is not None else settings.serper_api_key
        self.max_results = max_results or settings.max_articles

    async def search(self, *, company: str, ticker: str, query: str) -> list[dict]:
        search_query = self._build_search_query(company=company, ticker=ticker, query=query)

        if self.tavily_api_key:
            articles = await self._search_tavily(search_query)
            if articles:
                return articles

        if self.serper_api_key:
            articles = await self._search_serper(search_query)
            if articles:
                return articles

        return self._fallback_sources(company=company, ticker=ticker, query=query)

    async def _search_tavily(self, query: str) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    headers={"Authorization": f"Bearer {self.tavily_api_key}"},
                    json={
                        "query": query,
                        "topic": "finance",
                        "search_depth": "basic",
                        "max_results": self.max_results,
                        "include_answer": False,
                        "include_raw_content": False,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        results = response.json().get("results", [])
        return [
            {
                "title": result.get("title") or "Untitled source",
                "url": result.get("url") or "",
                "source": "Tavily",
                "published_at": result.get("published_date") or "Latest",
                "snippet": result.get("content") or "",
            }
            for result in results
            if result.get("url")
        ]

    async def _search_serper(self, query: str) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": self.serper_api_key, "Content-Type": "application/json"},
                    json={"q": query, "num": self.max_results},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        results = response.json().get("organic", [])
        return [
            {
                "title": result.get("title") or "Untitled source",
                "url": result.get("link") or "",
                "source": "Serper",
                "published_at": result.get("date") or "Latest",
                "snippet": result.get("snippet") or "",
            }
            for result in results
            if result.get("link")
        ]

    def _fallback_sources(self, *, company: str, ticker: str, query: str) -> list[dict]:
        return [
            {
                "title": f"{company} latest market update",
                "url": f"https://finance.yahoo.com/quote/{ticker}",
                "source": "Yahoo Finance",
                "published_at": "Latest",
                "snippet": f"Market page for {company} with quote, chart, and related financial news.",
            },
            {
                "title": f"{company} financial overview",
                "url": f"https://www.google.com/finance/quote/{ticker}",
                "source": "Google Finance",
                "published_at": "Latest",
                "snippet": f"Company profile, recent market movement, and key metrics for {company}.",
            },
            {
                "title": f"{company} investor relations",
                "url": f"https://www.google.com/search?q={company.replace(' ', '+')}+investor+relations",
                "source": "Investor Relations Search",
                "published_at": "Latest",
                "snippet": f"Investor materials can validate earnings, filings, and management commentary for: {query}",
            },
        ][: self.max_results]

    def _build_search_query(self, *, company: str, ticker: str, query: str) -> str:
        base_query = f"{company} {ticker} {query}".strip()
        if any(
            phrase in query.lower()
            for phrase in [
                "profit",
                "loss",
                "p&l",
                "pnl",
                "financial statement",
                "quarterly results",
                "earnings",
                "annual report",
            ]
        ):
            return (
                f"{base_query} revenue EBITDA PAT net profit expenses margins EPS "
                "quarterly results investor presentation annual report"
            )

        return f"{base_query} financial news outlook earnings"


search_service = SearchService()
