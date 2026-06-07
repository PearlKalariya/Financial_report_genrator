from collections.abc import AsyncIterator

from app.agents.market_data_agent import run_market_data_agent
from app.agents.memory_agent import run_memory_agent
from app.agents.query_agent import run_query_agent
from app.agents.report_agent import run_report_agent
from app.agents.research_agent import run_research_agent
from app.agents.sentiment_agent import run_sentiment_agent
from app.agents.state import AgentState
from app.memory.store import report_store
from app.schemas.events import StreamEvent
from app.core.config import settings
from app.services.trace_service import (
    privacy_safe_user_id,
    summarize_state,
    trace_service,
)


class FinancialResearchOrchestrator:
    async def stream_report(self, *, query: str, session_id: str) -> AsyncIterator[StreamEvent]:
        state: AgentState = {"query": query, "session_id": session_id, "errors": []}
        trace = trace_service.start(
            name="financial-research-query",
            user_id=privacy_safe_user_id(
                session_id,
                settings.session_secret or settings.app_name,
            ),
            input_data={"query_length": len(query)},
        )

        yield StreamEvent(type="status", agent="query", message="Understanding query")
        with trace.span(name="query_agent", input_data=summarize_state(state)):
            state = run_query_agent(state)

        if state.get("needs_clarification"):
            question = state.get("clarification_question", "Please clarify your query.")
            options = state.get("clarification_options", [])
            content = f"## Clarification Needed\n{question}\n\n"
            if options:
                content += "\n".join(f"- {option}" for option in options)
            yield StreamEvent(type="section", title="Clarification Needed")
            yield StreamEvent(type="delta", content=content + "\n\n")
            trace.end(output={"needs_clarification": True, "options": options})
            yield StreamEvent(type="done", message="Clarification needed")
            return

        yield StreamEvent(type="status", agent="research", message="Collecting source candidates")
        with trace.span(name="research_agent", input_data=summarize_state(state)):
            state = await run_research_agent(state)

        yield StreamEvent(type="status", agent="market_data", message="Fetching market metrics")
        with trace.span(name="market_data_agent", input_data=summarize_state(state)):
            state = await run_market_data_agent(state)

        yield StreamEvent(type="status", agent="sentiment", message="Scoring source sentiment")
        with trace.span(name="sentiment_agent", input_data=summarize_state(state)):
            state = run_sentiment_agent(state)

        yield StreamEvent(type="status", agent="memory", message="Retrieving session context")
        with trace.span(name="memory_agent", input_data=summarize_state(state)):
            state = run_memory_agent(state)

        yield StreamEvent(type="status", agent="report", message="Writing structured report")
        with trace.span(name="report_agent", input_data=summarize_state(state)):
            state = await run_report_agent(state)

        report_store.add(
            session_id=session_id,
            query=query,
            ticker=state.get("ticker"),
            company=state.get("company"),
            report=state["report"],
            citations=state.get("citations", []),
        )

        if state.get("financial_statements", {}).get("statements"):
            yield StreamEvent(
                type="financial_statements",
                data=state["financial_statements"],
            )

        for section in state["report"].split("\n\n"):
            if section.startswith("## "):
                yield StreamEvent(type="section", title=section.removeprefix("## ").split("\n")[0])
            yield StreamEvent(type="delta", content=section + "\n\n")

        for citation in state.get("citations", []):
            yield StreamEvent(type="citation", title=citation["title"], url=citation["url"])

        trace.end(output={"ticker": state.get("ticker"), "company": state.get("company")})
        yield StreamEvent(type="done", message="Report complete")


orchestrator = FinancialResearchOrchestrator()
