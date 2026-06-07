from collections.abc import AsyncIterator
from typing import Any

from app.agents.state import AgentState
from app.graphs.financial_research_graph import financial_research_graph
from app.memory.store import report_store
from app.schemas.events import StreamEvent
from app.core.config import settings
from app.services.trace_service import (
    privacy_safe_user_id,
    trace_service,
)


class FinancialResearchOrchestrator:
    def __init__(self, *, graph: Any = None, store: Any = None) -> None:
        self.graph = graph or financial_research_graph
        self.store = store or report_store

    async def stream_report(self, *, query: str, session_id: str) -> AsyncIterator[StreamEvent]:
        initial_state: AgentState = {
            "query": query,
            "session_id": session_id,
            "errors": [],
        }
        trace = trace_service.start(
            name="financial-research-query",
            user_id=privacy_safe_user_id(
                session_id,
                settings.session_secret or settings.app_name,
            ),
            input_data={"query_length": len(query)},
        )

        yield StreamEvent(
            type="status",
            agent="graph",
            message="Running financial research workflow",
        )
        try:
            state = await self.graph.ainvoke(
                initial_state,
                config={"configurable": {"trace": trace}},
            )
        except Exception:
            trace.end(output={"status": "error"})
            yield StreamEvent(
                type="error",
                message="Unable to complete the research workflow.",
            )
            return

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

        self.store.add(
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
