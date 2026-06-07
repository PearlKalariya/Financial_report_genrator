import re
from difflib import get_close_matches

from app.agents.state import AgentState


KNOWN_TICKERS = {
    "lt": ("LT.NS", "Larsen & Toubro", "India"),
    "l&t": ("LT.NS", "Larsen & Toubro", "India"),
    "larsen": ("LT.NS", "Larsen & Toubro", "India"),
    "larsen and toubro": ("LT.NS", "Larsen & Toubro", "India"),
    "larsen & toubro": ("LT.NS", "Larsen & Toubro", "India"),
    "tcs": ("TCS.NS", "Tata Consultancy Services", "India"),
    "tata consultancy services": ("TCS.NS", "Tata Consultancy Services", "India"),
    "reliance": ("RELIANCE.NS", "Reliance Industries", "India"),
    "reliance industries": ("RELIANCE.NS", "Reliance Industries", "India"),
    "infosys": ("INFY.NS", "Infosys", "India"),
    "infosis": ("INFY.NS", "Infosys", "India"),
    "hdfc bank": ("HDFCBANK.NS", "HDFC Bank", "India"),
    "icici": ("ICICI.NS", "ICICI Bank", "India"),
    "icici bank": ("ICICI.NS", "ICICI Bank", "India"),
    "apple": ("AAPL", "Apple", "United States"),
    "meta": ("META", "Meta Platforms", "United States"),
    "facebook": ("META", "Meta Platforms", "United States"),
    "meta platforms": ("META", "Meta Platforms", "United States"),
    "google": ("GOOGL", "Alphabet", "United States"),
    "alphabet": ("GOOGL", "Alphabet", "United States"),
    "amazon": ("AMZN", "Amazon", "United States"),
    "microsoft": ("MSFT", "Microsoft", "United States"),
    "tesla": ("TSLA", "Tesla", "United States"),
    "nvidia": ("NVDA", "NVIDIA", "United States"),
    "adani enterprises": ("ADANIENT.NS", "Adani Enterprises", "India"),
    "adani ports": ("ADANIPORTS.NS", "Adani Ports and Special Economic Zone", "India"),
    "adani port": ("ADANIPORTS.NS", "Adani Ports and Special Economic Zone", "India"),
    "adani green": ("ADANIGREEN.NS", "Adani Green Energy", "India"),
    "adani green energy": ("ADANIGREEN.NS", "Adani Green Energy", "India"),
    "adani power": ("ADANIPOWER.NS", "Adani Power", "India"),
    "adani energy": ("ADANIENSOL.NS", "Adani Energy Solutions", "India"),
    "adani energy solutions": ("ADANIENSOL.NS", "Adani Energy Solutions", "India"),
    "adani total gas": ("ATGL.NS", "Adani Total Gas", "India"),
    "tata motors": ("TATAMOTORS.NS", "Tata Motors", "India"),
    "tata power": ("TATAPOWER.NS", "Tata Power", "India"),
    "tata steel": ("TATASTEEL.NS", "Tata Steel", "India"),
}

AMBIGUOUS_ALIASES = {
    "tata": [
        "Tata Consultancy Services",
        "Tata Motors",
        "Tata Power",
        "Tata Steel",
    ],
    "adani": [
        "Adani Enterprises",
        "Adani Ports and Special Economic Zone",
        "Adani Green Energy",
        "Adani Power",
        "Adani Energy Solutions",
        "Adani Total Gas",
    ],
}

STOP_WORDS = {
    "about",
    "analysis",
    "and",
    "do",
    "for",
    "how",
    "is",
    "its",
    "me",
    "news",
    "outlook",
    "risk",
    "risks",
    "sentiment",
    "summarize",
    "the",
    "think",
    "what",
    "you",
    "analyze",
    "analze",
    "compare",
    "financial",
    "generate",
    "loss",
    "p",
    "profit",
    "report",
}

MACRO_MARKETS = {
    "indian stock market": ("^NSEI", "Indian Stock Market", "India"),
    "india stock market": ("^NSEI", "Indian Stock Market", "India"),
    "indian market": ("^NSEI", "Indian Stock Market", "India"),
    "nifty": ("^NSEI", "Nifty 50", "India"),
    "sensex": ("^BSESN", "BSE Sensex", "India"),
    "us stock market": ("^GSPC", "United States Stock Market", "United States"),
    "american stock market": ("^GSPC", "United States Stock Market", "United States"),
}

MACRO_IMPACT_TERMS = {
    "affect",
    "effect",
    "impact",
    "war",
    "conflict",
    "tension",
    "sanction",
    "oil",
    "inflation",
    "geopolitical",
}


def run_query_agent(state: AgentState) -> AgentState:
    query = state["query"].strip()
    lowered = query.lower()
    normalized = _normalize_query(lowered)

    macro_entity = _extract_macro_market(normalized)
    entities = [macro_entity] if macro_entity else _extract_entities(normalized)
    clarification = _find_ambiguous_alias(normalized)
    if clarification and not entities:
        return {
            **state,
            "ticker": "UNKNOWN",
            "company": clarification.title(),
            "intent": _detect_intent(lowered),
            "timeframe": _detect_timeframe(lowered),
            "region": "Unknown",
            "entities": [],
            "needs_clarification": True,
            "clarification_question": f"Which {clarification.title()} company do you mean?",
            "clarification_options": AMBIGUOUS_ALIASES[clarification],
        }

    ticker = None
    company = None
    region = None
    if entities:
        first_entity = entities[0]
        ticker = first_entity["ticker"]
        company = first_entity["company"]
        region = first_entity["region"]

    if ticker is None:
        words = [word.strip(".,?!").upper() for word in normalized.split()]
        candidates = [word for word in words if word.lower() not in STOP_WORDS]
        ticker = candidates[-1] if candidates else "UNKNOWN"
        company = ticker
        region = "Unknown"

    return {
        **state,
        "ticker": ticker,
        "company": company,
        "intent": _detect_intent(lowered),
        "timeframe": _detect_timeframe(lowered),
        "region": region,
        "entities": entities,
        "needs_clarification": False,
        "clarification_options": [],
    }


def _contains_alias(query: str, alias: str) -> bool:
    escaped = re.escape(alias.lower())
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", query))


def _normalize_query(query: str) -> str:
    normalized = query.lower()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9.\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _find_ambiguous_alias(query: str) -> str | None:
    for alias in AMBIGUOUS_ALIASES:
        if _contains_alias(query, alias):
            return alias
    return None


def _extract_entities(query: str) -> list[dict[str, str]]:
    matches: list[tuple[int, str, tuple[str, str, str]]] = []
    for alias, value in KNOWN_TICKERS.items():
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])")
        match = pattern.search(query)
        if match:
            matches.append((match.start(), alias, value))

    if not matches:
        fuzzy = _fuzzy_match_entity(query)
        if fuzzy:
            matches.append((0, fuzzy[0], fuzzy[1]))

    matches.sort(key=lambda item: (item[0], -len(item[1])))

    entities: list[dict[str, str]] = []
    seen_tickers: set[str] = set()
    consumed_spans: list[tuple[int, int]] = []
    for _, alias, value in matches:
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])")
        match = pattern.search(query)
        if match and any(_overlaps(match.span(), span) for span in consumed_spans):
            continue

        ticker, company, region = value
        if ticker in seen_tickers:
            continue

        seen_tickers.add(ticker)
        if match:
            consumed_spans.append(match.span())
        entities.append({"ticker": ticker, "company": company, "region": region})

    return entities


def _extract_macro_market(query: str) -> dict[str, str] | None:
    if not any(term in query.split() for term in MACRO_IMPACT_TERMS):
        return None
    for alias, (ticker, company, region) in MACRO_MARKETS.items():
        if _contains_alias(query, alias):
            return {"ticker": ticker, "company": company, "region": region}
    return None


def _fuzzy_match_entity(query: str) -> tuple[str, tuple[str, str, str]] | None:
    tokens = [
        token
        for token in query.split()
        if token not in STOP_WORDS and len(token) >= 4 and not token.isdigit()
    ]
    aliases = list(KNOWN_TICKERS.keys())
    ambiguous_tokens = set(AMBIGUOUS_ALIASES.keys())
    for token in tokens:
        if token in ambiguous_tokens:
            continue
        close = get_close_matches(token, aliases, n=1, cutoff=0.78)
        if close:
            alias = close[0]
            return alias, KNOWN_TICKERS[alias]
    return None


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _detect_intent(query: str) -> str:
    normalized = _normalize_query(query)
    if _extract_macro_market(normalized):
        return "macro_market_impact"
    if "compare" in query:
        return "comparison"
    if (
        "profit and loss" in query
        or "p&l" in query
        or "pnl" in query
        or "financial report" in query
        or "financial statement" in query
        or "earnings" in query
        or "quarterly results" in query
    ):
        return "financial_statement_analysis"
    if "sentiment" in query or "mood" in query:
        return "sentiment_analysis"
    if "risk" in query or "risks" in query:
        return "risk_analysis"
    if "news" in query or "summarize" in query:
        return "news_summary"
    return "outlook"


def _detect_timeframe(query: str) -> str:
    for marker in ["q1", "q2", "q3", "q4", "2026", "2025", "this week", "today"]:
        if marker in query:
            return marker.upper() if marker.startswith("q") else marker
    return "near term"
