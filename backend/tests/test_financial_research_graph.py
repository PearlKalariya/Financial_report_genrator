import asyncio

from app.graphs.financial_research_graph import (
    GraphNodeFunctions,
    build_financial_research_graph,
    merge_comparison_data,
)


def test_merge_comparison_data_preserves_branch_fields_by_ticker() -> None:
    merged = merge_comparison_data(
        [
            {
                "ticker": "AAPL",
                "company": "Apple",
                "articles": [{"title": "Apple source"}],
            }
        ],
        [
            {
                "ticker": "AAPL",
                "market_data": {"price": "USD 100.00"},
                "financial_statements": {"source": "Yahoo Finance"},
            },
            {
                "ticker": "META",
                "company": "Meta Platforms",
                "sentiment": {"label": "positive"},
            },
        ],
    )

    assert [item["ticker"] for item in merged] == ["AAPL", "META"]
    assert merged[0]["articles"][0]["title"] == "Apple source"
    assert merged[0]["market_data"]["price"] == "USD 100.00"
    assert merged[0]["financial_statements"]["source"] == "Yahoo Finance"
    assert merged[1]["sentiment"]["label"] == "positive"


def test_graph_runs_research_and_market_provider_concurrently() -> None:
    async def scenario() -> None:
        research_started = asyncio.Event()
        market_started = asyncio.Event()

        def query_node(state: dict) -> dict:
            return {
                "ticker": "AAPL",
                "company": "Apple",
                "entities": [
                    {
                        "ticker": "AAPL",
                        "company": "Apple",
                        "region": "United States",
                    }
                ],
                "needs_clarification": False,
            }

        async def research_node(state: dict) -> dict:
            research_started.set()
            await asyncio.wait_for(market_started.wait(), timeout=1)
            return {"articles": [{"title": "Source"}]}

        async def market_node(state: dict) -> dict:
            market_started.set()
            await asyncio.wait_for(research_started.wait(), timeout=1)
            return {"market_data": {"price": "USD 100.00"}}

        def sentiment_node(state: dict) -> dict:
            assert state["articles"]
            return {"sentiment": {"label": "positive"}}

        def join_node(state: dict) -> dict:
            assert state["market_data"]["price"] == "USD 100.00"
            assert state["sentiment"]["label"] == "positive"
            return {"financial_evidence": {"facts": []}}

        def memory_node(state: dict) -> dict:
            assert "financial_evidence" in state
            return {"memory_context": []}

        async def report_node(state: dict) -> dict:
            assert "memory_context" in state
            return {"report": "Complete report", "citations": []}

        graph = build_financial_research_graph(
            GraphNodeFunctions(
                query=query_node,
                research=research_node,
                market_provider=market_node,
                sentiment=sentiment_node,
                join_analysis=join_node,
                memory=memory_node,
                report=report_node,
            )
        )

        result = await graph.ainvoke(
            {"query": "Analyze Apple", "session_id": "session", "errors": []}
        )

        assert result["report"] == "Complete report"
        assert research_started.is_set()
        assert market_started.is_set()

    asyncio.run(scenario())


def test_graph_clarification_bypasses_downstream_nodes() -> None:
    downstream_calls = []

    def query_node(state: dict) -> dict:
        return {
            "ticker": "UNKNOWN",
            "company": "Tata",
            "needs_clarification": True,
            "clarification_question": "Which Tata company do you mean?",
        }

    async def unexpected_async(state: dict) -> dict:
        downstream_calls.append("async")
        return {}

    def unexpected_sync(state: dict) -> dict:
        downstream_calls.append("sync")
        return {}

    graph = build_financial_research_graph(
        GraphNodeFunctions(
            query=query_node,
            research=unexpected_async,
            market_provider=unexpected_async,
            sentiment=unexpected_sync,
            join_analysis=unexpected_sync,
            memory=unexpected_sync,
            report=unexpected_async,
        )
    )

    result = asyncio.run(
        graph.ainvoke(
            {"query": "Analyze Tata", "session_id": "session", "errors": []}
        )
    )

    assert result["needs_clarification"] is True
    assert downstream_calls == []

