import asyncio
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Awaitable, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents.memory_agent import run_memory_agent
from app.agents.query_agent import run_query_agent
from app.agents.report_agent import run_report_agent
from app.agents.research_agent import run_research_agent
from app.agents.sentiment_agent import run_sentiment_agent
from app.agents.state import AgentState
from app.services.evidence_service import financial_evidence_service
from app.services.financial_statement_service import financial_statement_service
from app.services.market_data_service import market_data_service
from app.services.trace_service import summarize_state


SyncNode = Callable[[AgentState], dict]
AsyncNode = Callable[[AgentState], Awaitable[dict]]


@dataclass(frozen=True)
class GraphNodeFunctions:
    query: SyncNode
    research: AsyncNode
    market_provider: AsyncNode
    sentiment: SyncNode
    join_analysis: SyncNode
    memory: SyncNode
    report: AsyncNode


def merge_comparison_data(*groups: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for group in groups:
        for item in group or []:
            ticker = item.get("ticker")
            if not ticker:
                continue
            if ticker not in merged:
                merged[ticker] = {}
                order.append(ticker)
            merged[ticker].update(item)
    return [merged[ticker] for ticker in order]


def build_financial_research_graph(node_functions: GraphNodeFunctions):
    graph = StateGraph(AgentState)
    graph.add_node("query", node_functions.query)
    graph.add_node("research", node_functions.research)
    graph.add_node("market_provider", node_functions.market_provider)
    graph.add_node("sentiment", node_functions.sentiment)
    graph.add_node("join_analysis", node_functions.join_analysis)
    graph.add_node("memory", node_functions.memory)
    graph.add_node("report", node_functions.report)

    graph.add_edge(START, "query")
    graph.add_conditional_edges("query", _route_after_query)
    graph.add_edge("research", "sentiment")
    graph.add_edge(["sentiment", "market_provider"], "join_analysis")
    graph.add_edge("join_analysis", "memory")
    graph.add_edge("memory", "report")
    graph.add_edge("report", END)
    return graph.compile()


def _route_after_query(state: AgentState):
    if state.get("needs_clarification"):
        return END
    return ["research", "market_provider"]


def _trace_span(
    config: RunnableConfig | None,
    name: str,
    state: AgentState,
):
    trace = (config or {}).get("configurable", {}).get("trace")
    if trace:
        return trace.span(name=name, input_data=summarize_state(state))
    return nullcontext()


def _query_node(
    state: AgentState,
    config: RunnableConfig | None = None,
) -> dict:
    with _trace_span(config, "query_agent", state):
        result = run_query_agent(state)
    return {
        key: result[key]
        for key in [
            "ticker",
            "company",
            "intent",
            "timeframe",
            "region",
            "entities",
            "needs_clarification",
            "clarification_question",
            "clarification_options",
        ]
        if key in result
    }


async def _research_node(
    state: AgentState,
    config: RunnableConfig | None = None,
) -> dict:
    with _trace_span(config, "research_agent", state):
        result = await run_research_agent(state)
    update = {"articles": result.get("articles", [])}
    if result.get("comparison_data"):
        update["research_comparison_data"] = result["comparison_data"]
    return update


async def _fetch_entity_market_data(entity: dict) -> dict:
    market_data, statements = await asyncio.gather(
        market_data_service.get_market_data(entity["ticker"]),
        financial_statement_service.get_statements(entity["ticker"]),
    )
    return {
        **entity,
        "market_data": market_data,
        "financial_statements": statements,
    }


async def _market_provider_node(
    state: AgentState,
    config: RunnableConfig | None = None,
) -> dict:
    with _trace_span(config, "market_data_agent", state):
        entities = state.get("entities", [])
        if state.get("intent") == "comparison" and len(entities) > 1:
            company_data = await asyncio.gather(
                *(_fetch_entity_market_data(entity) for entity in entities)
            )
            return {"market_comparison_data": list(company_data)}

        ticker = state.get("ticker", "UNKNOWN")
        market_data = await market_data_service.get_market_data(ticker)
        statements = (
            await financial_statement_service.get_statements(ticker)
            if state.get("intent") == "financial_statement_analysis"
            else {}
        )
    return {
        "market_data": market_data,
        "financial_statements": statements,
    }


def _sentiment_node(
    state: AgentState,
    config: RunnableConfig | None = None,
) -> dict:
    sentiment_state = dict(state)
    if state.get("research_comparison_data"):
        sentiment_state["comparison_data"] = state["research_comparison_data"]
    with _trace_span(config, "sentiment_agent", state):
        result = run_sentiment_agent(sentiment_state)
    update = {"sentiment": result.get("sentiment", {})}
    if result.get("comparison_data"):
        update["sentiment_comparison_data"] = result["comparison_data"]
    return update


def _join_analysis_node(
    state: AgentState,
    config: RunnableConfig | None = None,
) -> dict:
    with _trace_span(config, "join_analysis", state):
        if state.get("intent") == "comparison":
            comparison_data = merge_comparison_data(
                state.get("research_comparison_data", []),
                state.get("market_comparison_data", []),
                state.get("sentiment_comparison_data", []),
            )
            enriched = []
            for company_data in comparison_data:
                evidence = financial_evidence_service.build_evidence(
                    company=company_data["company"],
                    ticker=company_data["ticker"],
                    articles=company_data.get("articles", []),
                    market_data=company_data.get("market_data", {}),
                )
                enriched.append(
                    {**company_data, "financial_evidence": evidence}
                )
            first = enriched[0] if enriched else {}
            return {
                "comparison_data": enriched,
                "market_data": first.get("market_data", {}),
                "financial_evidence": first.get("financial_evidence", {}),
                "financial_statements": first.get("financial_statements", {}),
            }

        evidence = financial_evidence_service.build_evidence(
            company=state.get("company", state.get("ticker", "UNKNOWN")),
            ticker=state.get("ticker", "UNKNOWN"),
            articles=state.get("articles", []),
            market_data=state.get("market_data", {}),
        )
        return {"financial_evidence": evidence}


def _memory_node(
    state: AgentState,
    config: RunnableConfig | None = None,
) -> dict:
    with _trace_span(config, "memory_agent", state):
        result = run_memory_agent(state)
    return {"memory_context": result.get("memory_context", [])}


async def _report_node(
    state: AgentState,
    config: RunnableConfig | None = None,
) -> dict:
    with _trace_span(config, "report_agent", state):
        result = await run_report_agent(state)
    return {
        key: result[key]
        for key in [
            "report",
            "citations",
            "report_model",
            "report_used_fallback",
            "report_error",
        ]
        if key in result
    }


default_node_functions = GraphNodeFunctions(
    query=_query_node,
    research=_research_node,
    market_provider=_market_provider_node,
    sentiment=_sentiment_node,
    join_analysis=_join_analysis_node,
    memory=_memory_node,
    report=_report_node,
)

financial_research_graph = build_financial_research_graph(default_node_functions)
