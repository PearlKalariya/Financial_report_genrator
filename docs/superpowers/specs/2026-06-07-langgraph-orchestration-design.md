# LangGraph Orchestration Design

## Goal

Replace the hand-written sequential workflow with a real LangGraph graph while
preserving the existing FastAPI endpoint, SSE event contract, agent functions,
clarification behavior, report storage, tracing, and frontend compatibility.

## Scope

This phase implements only the orchestration foundation:

- Add the LangGraph runtime dependency.
- Build a compiled financial-research graph.
- Run independent research and market-data work in parallel.
- Run sentiment after research data is available.
- Join branch results before memory retrieval and report generation.
- Preserve comparison, macro-market, financial-statement, and clarification
  queries.
- Preserve existing SSE event types and report persistence.
- Add graph-focused unit and integration tests.

ChromaDB, frontend history and charts, expanded Langfuse generations, prompt
files, deployment configuration, and README repair remain separate phases.

## Compatibility Contract

The public behavior must remain stable:

- `POST /api/query` continues returning `text/event-stream`.
- Existing `status`, `section`, `delta`, `citation`,
  `financial_statements`, and `done` events remain valid.
- Signed cookie sessions and in-memory rate limiting remain unchanged.
- Clarification queries return a clarification report without invoking research
  or report-generation nodes.
- Completed reports continue to be stored once per successful workflow.
- The frontend requires no changes for this phase.

## Graph Architecture

The graph uses `AgentState` as its shared state and contains these nodes:

1. `query`
2. `research`
3. `market_data`
4. `sentiment`
5. `join_analysis`
6. `memory`
7. `report`

Flow:

```text
START
  |
  v
query
  |
  +-- clarification required --> END
  |
  +--> research ----> sentiment --+
  |                               |
  +--> market_data ---------------+--> join_analysis
                                        |
                                        v
                                      memory
                                        |
                                        v
                                      report
                                        |
                                        v
                                       END
```

`research` and `market_data` are parallel branches. `sentiment` depends on the
research result. `join_analysis` is an explicit synchronization node and does
not perform business logic.

## State Merge Strategy

Parallel branches must not return a full copied state because concurrent full
state updates can overwrite each other. Graph node adapters return only fields
owned by their node:

- Query: entity, intent, timeframe, region, and clarification fields.
- Research: `articles` and research-side `comparison_data`.
- Market data: `market_data`, `financial_evidence`,
  `financial_statements`, and market-side comparison results.
- Sentiment: `sentiment` and sentiment-side comparison results.
- Memory: `memory_context`.
- Report: `report`, `citations`, model, fallback, and error metadata.

Comparison mode needs deterministic merging because research, market data, and
sentiment enrich the same companies. A comparison merge helper combines entries
by ticker and preserves fields supplied by each branch.

State keys that receive parallel updates use explicit reducers where needed.
Reducers must be deterministic and must not silently discard populated values.

## Agent Adapters

Existing agent functions remain the source of business logic. Thin graph-node
adapters call each agent and extract only the node-owned update. This avoids a
large agent rewrite and keeps existing tests meaningful.

Synchronous agents are wrapped as synchronous graph nodes. Asynchronous agents
remain asynchronous graph nodes, and the compiled graph is invoked with
`ainvoke`.

## Streaming Behavior

LangGraph executes the internal workflow. The existing orchestrator remains the
SSE presentation layer.

The orchestrator:

1. Emits query status.
2. Runs the query node directly or through a query-only graph step.
3. Returns clarification SSE events immediately when required.
4. Emits analysis status before invoking the remaining compiled graph.
5. Receives the completed graph state.
6. Stores the report.
7. Emits structured statements, report sections, deltas, citations, and done.

This phase does not promise per-node live status timing from LangGraph. Status
messages describe graph stages without exposing unstable internal stream
formats. A later observability phase may use LangGraph event streaming for
fine-grained UI progress.

## Tracing

The request keeps one Langfuse trace. Each graph node is wrapped in a named span
using the existing privacy-safe state summary. Raw queries, source snippets,
reports, evidence, and session identifiers remain excluded from trace payloads.

Graph execution errors end the active span with sanitized error metadata and
propagate to the API streaming layer. Existing rate-limit releases remain in
the route's `finally` block.

## Error Handling

- Provider errors continue to be handled by individual services and fallbacks.
- An unexpected graph-node exception terminates graph execution.
- The SSE layer emits an `error` event with a generic message before closing
  the stream.
- A failed workflow is not persisted as a completed report.
- Clarification is a normal graph outcome, not an error.

## File Changes

Create:

- `backend/app/graphs/__init__.py`
- `backend/app/graphs/financial_research_graph.py`
- `backend/tests/test_financial_research_graph.py`

Modify:

- `backend/requirements.txt`
- `backend/app/agents/state.py`
- `backend/app/services/orchestrator.py`
- `backend/tests/test_services.py`

The current agent modules, routes, schemas, memory store, frontend, and security
services remain compatible.

## Testing

### Unit Tests

- The graph compiles.
- Query output enters both research and market-data branches.
- Research and market-data nodes overlap in execution, proving parallelism.
- Sentiment starts only after research completes.
- Memory and report run only after both analysis branches join.
- Clarification bypasses all downstream agents.
- Parallel comparison updates merge by ticker without losing articles, market
  data, statements, or sentiment.

### Integration Tests

- A mocked full graph returns a complete report state.
- The orchestrator preserves the existing SSE event sequence and payload types.
- A financial-statement workflow still emits a
  `financial_statements` event.
- A graph exception emits an error event and does not store a report.

### Regression Verification

- Run the complete backend test suite.
- Compile all backend modules.
- Run one live local SSE query.
- Confirm frontend production build remains successful even though no frontend
  code changes are expected.

## Acceptance Criteria

Phase 1 is complete when:

- `langgraph` is installed and imported by the application.
- A compiled `StateGraph` executes the financial research workflow.
- Research and market-data branches demonstrably execute concurrently.
- Sentiment waits for research.
- Memory and report wait for both analysis branches.
- Clarification behavior is unchanged.
- Existing SSE clients work without modification.
- Reports are persisted exactly once after successful completion.
- All backend tests and the frontend production build pass.

