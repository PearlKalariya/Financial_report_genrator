from app.agents.state import AgentState
from app.memory.store import report_store


def run_memory_agent(state: AgentState) -> AgentState:
    ticker = state.get("ticker")
    session_id = state.get("session_id", "demo-session")
    memory_context = report_store.find_related(session_id=session_id, ticker=ticker, limit=3)
    return {**state, "memory_context": memory_context}

