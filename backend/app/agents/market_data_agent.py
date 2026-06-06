from app.agents.state import AgentState
from app.services.evidence_service import financial_evidence_service
from app.services.market_data_service import market_data_service


async def run_market_data_agent(state: AgentState) -> AgentState:
    if state.get("intent") == "comparison" and len(state.get("comparison_data", [])) > 1:
        comparison_data = []
        for company_data in state["comparison_data"]:
            market_data = await market_data_service.get_market_data(company_data["ticker"])
            evidence = financial_evidence_service.build_evidence(
                company=company_data["company"],
                ticker=company_data["ticker"],
                articles=company_data.get("articles", []),
                market_data=market_data,
            )
            comparison_data.append(
                {
                    **company_data,
                    "market_data": market_data,
                    "financial_evidence": evidence,
                }
            )

        return {
            **state,
            "comparison_data": comparison_data,
            "market_data": comparison_data[0]["market_data"],
            "financial_evidence": comparison_data[0]["financial_evidence"],
        }

    ticker = state.get("ticker", "UNKNOWN")
    market_data = await market_data_service.get_market_data(ticker)
    evidence = financial_evidence_service.build_evidence(
        company=state.get("company", ticker),
        ticker=ticker,
        articles=state.get("articles", []),
        market_data=market_data,
    )
    return {**state, "market_data": market_data, "financial_evidence": evidence}
