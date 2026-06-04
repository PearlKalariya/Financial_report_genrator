from app.agents.state import AgentState
from app.services.search_service import search_service


async def run_research_agent(state: AgentState) -> AgentState:
    if state.get("intent") == "comparison" and len(state.get("entities", [])) > 1:
        comparison_data = []
        for entity in state["entities"]:
            articles = await search_service.search(
                company=entity["company"],
                ticker=entity["ticker"],
                query=f"{state['query']} {entity['company']} {entity['ticker']}",
            )
            comparison_data.append({**entity, "articles": articles})

        all_articles = [
            article
            for company_data in comparison_data
            for article in company_data.get("articles", [])
        ]
        return {**state, "comparison_data": comparison_data, "articles": all_articles}

    company = state.get("company", "the company")
    ticker = state.get("ticker", "UNKNOWN")
    articles = await search_service.search(company=company, ticker=ticker, query=state["query"])

    return {**state, "articles": articles}
