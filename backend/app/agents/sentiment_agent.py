from app.agents.state import AgentState


POSITIVE_TERMS = {"growth", "strong", "profit", "beat", "deal", "upgrade", "resilient"}
NEGATIVE_TERMS = {"risk", "weak", "miss", "downgrade", "fall", "pressure", "lawsuit"}


def run_sentiment_agent(state: AgentState) -> AgentState:
    if state.get("intent") == "comparison" and len(state.get("comparison_data", [])) > 1:
        comparison_data = []
        for company_data in state["comparison_data"]:
            sentiment = _score_articles(company_data.get("articles", []))
            comparison_data.append({**company_data, "sentiment": sentiment})

        positive_count = sum(
            1 for company_data in comparison_data if company_data["sentiment"]["label"] == "positive"
        )
        aggregate = {
            "label": "positive" if positive_count else "neutral",
            "score": round(
                sum(company_data["sentiment"]["score"] for company_data in comparison_data)
                / len(comparison_data),
                2,
            ),
            "confidence": 0.7,
            "drivers": ["per-company source tone", "relative market context", "headline language"],
        }
        return {**state, "comparison_data": comparison_data, "sentiment": aggregate}

    sentiment = _score_articles(state.get("articles", []))
    return {**state, "sentiment": sentiment}


def _score_articles(articles: list[dict]) -> dict:
    text = " ".join(
        f"{article.get('title', '')} {article.get('snippet', '')}"
        for article in articles
    ).lower()

    positive_hits = sum(1 for term in POSITIVE_TERMS if term in text)
    negative_hits = sum(1 for term in NEGATIVE_TERMS if term in text)
    raw_score = positive_hits - negative_hits

    if raw_score > 0:
        label = "positive"
    elif raw_score < 0:
        label = "negative"
    else:
        label = "neutral"

    score = max(-1.0, min(1.0, raw_score / 5))
    sentiment = {
        "label": label,
        "score": round(score, 2),
        "confidence": 0.62 if label == "neutral" else 0.74,
        "drivers": ["recent source tone", "market data context", "headline language"],
    }
    return sentiment
