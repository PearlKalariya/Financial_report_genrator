from app.agents.state import AgentState
from app.services.llm_service import gemini_report_service


DISCLAIMER = (
    "This report is for informational and educational purposes only. "
    "It is not financial advice, investment advice, or a recommendation to buy, sell, or hold any security."
)


async def run_report_agent(state: AgentState) -> AgentState:
    if state.get("intent") == "comparison" and len(state.get("comparison_data", [])) > 1:
        return await _run_comparison_report_agent(state)

    company = state.get("company", "Unknown company")
    ticker = state.get("ticker", "UNKNOWN")
    timeframe = state.get("timeframe", "near term")
    market = state.get("market_data", {})
    sentiment = state.get("sentiment", {})
    articles = state.get("articles", [])
    memory_context = state.get("memory_context", [])

    citations = [
        {
            "title": article["title"],
            "url": article["url"],
            "source": article.get("source"),
            "published_at": article.get("published_at"),
        }
        for article in articles
    ]

    source_lines = "\n".join(
        f"- [{index + 1}] {article['title']} ({article.get('source', 'Source')})"
        for index, article in enumerate(articles)
    )
    memory_note = (
        f"{len(memory_context)} related prior report(s) were found for this session."
        if memory_context
        else "No prior session context was found for this ticker."
    )

    fallback_report = f"""# {company} ({ticker}) Market Insight Report

## Executive Summary
{company} is being analyzed for a **{state.get("intent", "market")}** query over the **{timeframe}** timeframe. The current demo workflow combines source discovery, market metrics, lightweight sentiment scoring, and session memory into one structured report.

## Price Action
- Current price: {market.get("price", "N/A")}
- Change: {market.get("change", "N/A")}
- Volume: {market.get("volume", "N/A")}
- 52-week range: {market.get("fifty_two_week_range", "N/A")}
- Data source: {market.get("source", "N/A")}
- Exchange: {market.get("exchange", "N/A")}
- Resolved symbol: {market.get("symbol", ticker)}

## Key Market Metrics
- Market cap: {market.get("market_cap", "N/A")}
- PE ratio: {market.get("pe_ratio", "N/A")}

## News Analysis
The research agent found {len(articles)} source(s) for this query. These sources should be used to validate the latest price context, company announcements, earnings material, and broader market narrative.

{source_lines}

## Sentiment
- Label: {sentiment.get("label", "neutral")}
- Score: {sentiment.get("score", 0)}
- Confidence: {sentiment.get("confidence", 0)}
- Main drivers: {", ".join(sentiment.get("drivers", []))}

## Memory Context
{memory_note}

## Key Risks
- Market data in this MVP uses deterministic fallback values unless real API providers are connected.
- Search results should be upgraded to Tavily or Serper for production-grade source retrieval.
- Financial conclusions must remain citation-backed and should not rely on LLM-generated numbers.

## Outlook
The near-term outlook should be treated as a structured research starting point rather than a final recommendation. A stronger production version should add live news ranking, filings retrieval, real market data, and deeper sector comparison before producing high-confidence conclusions.

## Sources
{source_lines}

## Disclaimer
{DISCLAIMER}
"""

    result = await gemini_report_service.generate_report(fallback_report=fallback_report, state=dict(state))

    return {
        **state,
        "report": result.report,
        "citations": citations,
        "report_model": result.model,
        "report_used_fallback": result.used_fallback,
        "report_error": result.error,
    }


async def _run_comparison_report_agent(state: AgentState) -> AgentState:
    comparison_data = state.get("comparison_data", [])
    timeframe = state.get("timeframe", "near term")
    title = " vs ".join(company_data["company"] for company_data in comparison_data)

    citations = [
        {
            "title": article["title"],
            "url": article["url"],
            "source": article.get("source"),
            "published_at": article.get("published_at"),
        }
        for company_data in comparison_data
        for article in company_data.get("articles", [])
    ]

    rows = "\n".join(
        _comparison_table_row(company_data)
        for company_data in comparison_data
    )
    company_sections = "\n\n".join(
        _comparison_company_section(index, company_data)
        for index, company_data in enumerate(comparison_data, start=1)
    )
    source_lines = "\n".join(
        f"- [{index + 1}] {citation['title']} ({citation.get('source', 'Source')})"
        for index, citation in enumerate(citations)
    )

    fallback_report = f"""# {title} Comparison Report

## Executive Summary
This report compares {title} over the **{timeframe}** timeframe. It uses separate market data, source retrieval, and sentiment scoring for each company instead of analyzing only the first ticker.

## Comparison Snapshot
| Company | Ticker | Price | Change | Sentiment | Source | Exchange |
|---|---:|---:|---:|---:|---|---|
{rows}

{company_sections}

## Relative Takeaways
- Compare the companies by business exposure, price action, source sentiment, and risk profile.
- Use the per-company sections above to avoid over-weighting only the first company in the query.
- Treat unavailable metrics as missing data, not as negative signals.

## Sources
{source_lines}

## Disclaimer
{DISCLAIMER}
"""

    result = await gemini_report_service.generate_report(fallback_report=fallback_report, state=dict(state))

    return {
        **state,
        "report": result.report,
        "citations": citations,
        "report_model": result.model,
        "report_used_fallback": result.used_fallback,
        "report_error": result.error,
    }


def _comparison_table_row(company_data: dict) -> str:
    market = company_data.get("market_data", {})
    sentiment = company_data.get("sentiment", {})
    return (
        f"| {company_data.get('company', 'N/A')} | {company_data.get('ticker', 'N/A')} | "
        f"{market.get('price', 'N/A')} | {market.get('change', 'N/A')} | "
        f"{sentiment.get('label', 'neutral')} ({sentiment.get('score', 0)}) | "
        f"{market.get('source', 'N/A')} | {market.get('exchange', 'N/A')} |"
    )


def _comparison_company_section(index: int, company_data: dict) -> str:
    market = company_data.get("market_data", {})
    sentiment = company_data.get("sentiment", {})
    articles = company_data.get("articles", [])
    source_lines = "\n".join(
        f"- {article.get('title', 'Untitled source')} ({article.get('source', 'Source')})"
        for article in articles[:4]
    )

    return f"""## {index}. {company_data.get('company')} ({company_data.get('ticker')})
- Current price: {market.get('price', 'N/A')}
- Change: {market.get('change', 'N/A')}
- Volume: {market.get('volume', 'N/A')}
- 52-week range: {market.get('fifty_two_week_range', 'N/A')}
- Data source: {market.get('source', 'N/A')}
- Exchange: {market.get('exchange', 'N/A')}
- Sentiment: {sentiment.get('label', 'neutral')} ({sentiment.get('score', 0)})

Recent sources:
{source_lines}
"""
