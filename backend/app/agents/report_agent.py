from app.agents.state import AgentState
from app.services.llm_service import gemini_report_service
from app.services.security_service import sanitize_citations


DISCLAIMER = (
    "This report is for informational and educational purposes only. "
    "It is not financial advice, investment advice, or a recommendation to buy, sell, or hold any security."
)


async def run_report_agent(state: AgentState) -> AgentState:
    if state.get("intent") == "comparison" and len(state.get("comparison_data", [])) > 1:
        return await _run_comparison_report_agent(state)

    if state.get("intent") == "financial_statement_analysis":
        return await _run_financial_statement_report_agent(state)

    if state.get("intent") == "macro_market_impact":
        return await _run_macro_market_report_agent(state)

    company = state.get("company", "Unknown company")
    ticker = state.get("ticker", "UNKNOWN")
    timeframe = state.get("timeframe", "near term")
    market = state.get("market_data", {})
    sentiment = state.get("sentiment", {})
    articles = state.get("articles", [])
    memory_context = state.get("memory_context", [])

    citations = sanitize_citations([
        {
            "title": article["title"],
            "url": article["url"],
            "source": article.get("source"),
            "published_at": article.get("published_at"),
        }
        for article in articles
    ])

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


async def _run_macro_market_report_agent(state: AgentState) -> AgentState:
    company = state.get("company", "Target Market")
    ticker = state.get("ticker", "UNKNOWN")
    timeframe = state.get("timeframe", "near term")
    market = state.get("market_data", {})
    sentiment = state.get("sentiment", {})
    articles = state.get("articles", [])
    citations = sanitize_citations(
        [
            {
                "title": article["title"],
                "url": article["url"],
                "source": article.get("source"),
                "published_at": article.get("published_at"),
            }
            for article in articles
        ]
    )
    source_lines = "\n".join(
        f"- [{index + 1}] {article['title']} ({article.get('source', 'Source')})"
        for index, article in enumerate(articles)
        if any(citation["url"] == article.get("url") for citation in citations)
    ) or "- No valid sources were retrieved."

    fallback_report = f"""# {company} Macro Impact Report

## Executive Summary
The query examines how a geopolitical event could affect the **{company}** over the **{timeframe}**. The main transmission channels are crude-oil prices, inflation, the rupee, foreign institutional flows, global risk appetite, and supply-chain disruption. The effect is usually uneven across sectors rather than uniformly negative for every listed company.

## Current Market Context
- Benchmark: {market.get("symbol", ticker)}
- Current level: {market.get("price", "Unavailable")}
- Change: {market.get("change", "N/A")}
- Data source: {market.get("source", "N/A")}
- Source sentiment: {sentiment.get("label", "neutral")} ({sentiment.get("score", 0)})

## Transmission Channels
- **Crude oil:** India imports most of its crude requirements. A sustained oil-price increase can widen the import bill, pressure the rupee, raise inflation, and reduce room for interest-rate cuts.
- **Foreign flows:** A global move toward safer assets can trigger foreign institutional investor selling and increase equity-market volatility.
- **Currency and rates:** Rupee weakness raises imported costs. Persistent inflation can keep interest rates higher for longer.
- **Trade and logistics:** Disruption around major shipping routes can increase freight, insurance, fertilizer, energy, and input costs.
- **Risk appetite:** Escalation usually pressures valuation-sensitive and cyclical stocks; credible de-escalation can reverse part of that move quickly.

## Sector Impact
- **Potential pressure:** Airlines, paints, chemicals, tyres, logistics, and other businesses with fuel or imported-input exposure.
- **Mixed impact:** Oil marketing companies depend on crude prices, retail-price policy, and refining margins.
- **Potential relative resilience:** Domestic defensives such as selected FMCG, healthcare, and utilities may hold up better during risk-off periods.
- **Possible beneficiaries:** Upstream oil producers and defence-related companies may gain if energy prices or security spending rise, though company fundamentals still matter.

## News and Evidence
{source_lines}

## Key Risks
- The market impact depends on whether the conflict remains contained or disrupts energy and shipping infrastructure.
- Headlines can cause sharp short-term moves that reverse when escalation expectations change.
- Source sentiment is not a substitute for verified index, oil-price, currency, and foreign-flow data.

## Outlook
The near-term bias is likely to remain volatile while investors track crude oil, the USD/INR exchange rate, foreign flows, and signs of escalation or de-escalation. A contained conflict may produce a temporary risk-off move; sustained disruption to oil supply or shipping would create a more material earnings and inflation shock for India.

## Sources
{source_lines}

## Disclaimer
{DISCLAIMER}
"""

    result = await gemini_report_service.generate_report(
        fallback_report=fallback_report,
        state=dict(state),
    )
    return {
        **state,
        "report": result.report,
        "citations": citations,
        "report_model": result.model,
        "report_used_fallback": result.used_fallback,
        "report_error": result.error,
    }


async def _run_financial_statement_report_agent(state: AgentState) -> AgentState:
    company = state.get("company", "Unknown company")
    ticker = state.get("ticker", "UNKNOWN")
    timeframe = state.get("timeframe", "near term")
    market = state.get("market_data", {})
    articles = state.get("articles", [])
    evidence = state.get("financial_evidence", {})

    citations = sanitize_citations([
        {
            "title": article["title"],
            "url": article["url"],
            "source": article.get("source"),
            "published_at": article.get("published_at"),
        }
        for article in articles
    ])
    source_lines = "\n".join(
        f"- [{index + 1}] {article['title']} ({article.get('source', 'Source')})"
        for index, article in enumerate(articles)
    )
    fact_rows = _financial_fact_rows(evidence)
    evidence_lines = _financial_evidence_lines(evidence)
    observation_lines = _source_observation_lines(evidence)
    confidence = evidence.get("confidence", {})
    freshness = evidence.get("freshness", {})

    fallback_report = f"""# {company} ({ticker}) Profit and Loss Analysis Report

## Executive Summary
This report focuses on profit and loss performance for {company} over the **{timeframe}** timeframe. Only explicitly extracted financial facts are shown as verified. Missing metrics are marked unavailable rather than estimated.

## Profit and Loss Snapshot
| Metric | Value | Period | Evidence |
|---|---:|---|---|
{fact_rows}

## Revenue Analysis
Review reported revenue, sales volume, segment growth, and management commentary from the cited results sources.

## Expense Analysis
Review operating expenses, fuel/input costs, finance costs, depreciation, and other cost drivers only when they appear in cited sources.

## Profitability Analysis
Review EBITDA, PAT/net profit, margin movement, and EPS trends. Do not infer profitability numbers from price action.

## Market Context
- Current price: {market.get("price", "N/A")}
- Change: {market.get("change", "N/A")}
- Data source: {market.get("source", "N/A")}
- Exchange: {market.get("exchange", "N/A")}
- Resolved symbol: {market.get("symbol", ticker)}

## Recent Earnings and Source Evidence
{evidence_lines}

## Source-Reported Figures
The following figures are reproduced from retrieved source text. They are not reclassified, calculated, or treated as verified P&L metrics unless also listed in the snapshot above.

{observation_lines}

## Data Quality
- Confidence: {confidence.get("level", "low")} ({confidence.get("score", 0)})
- Verified metrics: {confidence.get("verified_metrics", 0)} of {confidence.get("required_metrics", 0)}
- Official sources: {confidence.get("official_sources", 0)}
- Latest source date: {freshness.get("latest_source_date", "Unavailable")}
- Market data as of: {freshness.get("market_data_as_of", "Unavailable")}
- Freshness warning: {freshness.get("warning") or "None"}

## Key Risks
- Revenue volatility and demand cyclicality
- Margin pressure from input costs, finance costs, or regulatory changes
- Execution risk in expansion or capex plans
- Missing or stale financial-statement data if official filings are not retrieved

## Outlook
The P&L outlook should be based on cited revenue, expense, and profitability evidence. If exact current-period P&L figures are unavailable, consult the latest quarterly results, annual report, or exchange filing before drawing conclusions.

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

    citations = sanitize_citations([
        {
            "title": article["title"],
            "url": article["url"],
            "source": article.get("source"),
            "published_at": article.get("published_at"),
        }
        for company_data in comparison_data
        for article in company_data.get("articles", [])
    ])

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


def _financial_fact_rows(evidence: dict) -> str:
    facts = evidence.get("facts", [])
    metric_labels = {
        "revenue": "Revenue",
        "ebitda": "EBITDA",
        "net_profit": "Net Profit / PAT",
        "expenses": "Expenses",
        "eps": "EPS",
        "operating_margin": "Operating Margin",
        "ebitda_margin": "EBITDA Margin",
    }
    facts_by_metric = {}
    for fact in facts:
        facts_by_metric.setdefault(fact["metric"], fact)

    rows = []
    for metric, label in metric_labels.items():
        fact = facts_by_metric.get(metric)
        if not fact:
            rows.append(f"| {label} | Unavailable | - | - |")
            continue
        value = _format_fact_value(fact)
        rows.append(
            f"| {label} | {value} | {fact.get('period', 'Unspecified')} | "
            f"[{fact.get('fact_id')}/{fact.get('source_id')}] |"
        )
    return "\n".join(rows)


def _financial_evidence_lines(evidence: dict) -> str:
    facts = evidence.get("facts", [])
    if not facts:
        return "No explicit P&L metrics were found in the retrieved source snippets."

    return "\n".join(
        f"- [{fact.get('fact_id')}/{fact.get('source_id')}] "
        f"{fact.get('metric').replace('_', ' ').title()}: {_format_fact_value(fact)} "
        f"for {fact.get('period', 'Unspecified')} "
        f"(confidence: {fact.get('confidence', 'low')})"
        for fact in facts
    )


def _source_observation_lines(evidence: dict) -> str:
    observations = evidence.get("source_observations", [])
    if not observations:
        return "No additional source-reported numeric statements were found."

    return "\n".join(
        f"- [{observation.get('observation_id')}/{observation.get('source_id')}] "
        f"{observation.get('text')}"
        for observation in observations
    )


def _format_fact_value(fact: dict) -> str:
    currency = f"{fact.get('currency')} " if fact.get("currency") else ""
    unit = f" {fact.get('unit')}" if fact.get("unit") else ""
    return f"{currency}{fact.get('value', 'Unavailable')}{unit}"
