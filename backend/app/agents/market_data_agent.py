from app.agents.state import AgentState
from app.services.market_data_service import market_data_service


async def run_market_data_agent(state: AgentState) -> AgentState:
    if state.get("intent") == "comparison" and len(state.get("comparison_data", [])) > 1:
        comparison_data = []
        for company_data in state["comparison_data"]:
            market_data = await market_data_service.get_market_data(company_data["ticker"])
            comparison_data.append({**company_data, "market_data": market_data})

        return {**state, "comparison_data": comparison_data, "market_data": comparison_data[0]["market_data"]}

    ticker = state.get("ticker", "UNKNOWN")
    market_data = await market_data_service.get_market_data(ticker)
    return {**state, "market_data": market_data}
