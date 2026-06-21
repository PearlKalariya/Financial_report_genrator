# LangGraph Orchestration Design

## Goal

Replace the hand-written sequential workflow with a real LangGraph graph while
preserving the existing FastAPI endpoint, SSE event contract, agent functions,
clarification behavior, report storage, tracing, and frontend compatibility.

## Scope

This phase implements only the orchestration foundation:

 - Add the LangGraph runtime dependency (LangGraph 1.1.10). Pin this exact
   version for reproducible builds, matching `backend/requirements.txt`. To
   update, change the pinned version in `backend/requirements.txt` and update
   this spec to document the new version and justification.
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
research result. `join_analysis` synchronizes the branches, merges comparison
records by ticker, and builds financial evidence after both articles and market
data are available.

## State Merge Strategy

Parallel branches must not return a full copied state because concurrent full
state updates can overwrite each other. Graph node adapters return only fields
owned by their node:

- Query: entity, intent, timeframe, region, and clarification fields.
- Research: `articles` and research-side `comparison_data`.
- Market data: `market_data`, `financial_statements`, and market-side comparison
  results.
- Sentiment: `sentiment` and sentiment-side comparison results.
- Join analysis: merged `comparison_data` and `financial_evidence`.
- Memory: `memory_context`.
- Report: `report`, `citations`, model, fallback, and error metadata.

Comparison mode needs deterministic merging because research, market data, and
sentiment enrich the same companies. The comparison merge helper MUST:

- Group incoming entries by `ticker` (exact string match after canonical
  normalization).
- For each ticker, merge fields deterministically using a fixed precedence
  rule. Default precedence: `research > market_data > sentiment` (higher
  precedence wins on conflicting scalar fields). Implementers may choose a
  different precedence, but it must be documented and constant across runs.
- When conflicting values are resolved in favor of a higher-precedence branch,
  annotate the merged field with provenance metadata: e.g. `_provenance.fieldX`
  = {"source": "research", "timestamp": "2026-03-15T12:34:56Z"}.
- For array-valued fields, apply a canonical de-dup + append strategy
  (preserve arrival order per-branch, then de-duplicate by item id).
- For numeric/time fields where aggregation makes sense (e.g. price, marketcap),
  specify the rule explicitly (default: latest-by-timestamp for time-series,
  max() for high-water-mark metrics) in the helper's configuration.

The comparison merge helper must always produce the same output for the same
set of inputs (deterministic), and must never silently drop non-empty values
without explicit de-duplication or aggregation rules.

State keys that receive parallel updates use explicit reducers. Reducers must be
deterministic, idempotent, and must not silently discard populated values.
Each reducer is a named function and must be registered in a `reducers` map
keyed by the state key so the orchestrator calls the correct reducer for each
concurrent update.

Recommended reducers (name, deterministic rule, example):

- `reduce_articles`: append-then-dedupe by `article.id`, preserving original
  arrival order across branches. Example:

  - Input A: [{id: "a1", title: "x"}]
  - Input B: [{id: "a2", title: "y"}, {id: "a1", title: "x-mod"}]
  - Output: [{id: "a1", title: "x"}, {id: "a2", title: "y"}]
    (first-seen wins for identical `id`, no silent drops)

- `reduce_citations`: set-union by `citation.key` with canonical normalization
  of keys (lowercase, trim). Preserve the earliest `source` for provenance.

- `reduce_researchResults`: merge arrays by `item.id` with field-level merge
  where non-null scalar fields are taken from the highest-priority branch
  (per comparison precedence) and arrays are de-duped/concatenated.

- `reduce_metadata`: shallow-merge with last-write-wins for scalar fields
  (the reducer applies a deterministic ordering based on `sourcePriority`
  ordering), and deep-merge for lists using union semantics.

- `reduce_stateFlags` (status / boolean flags): priority-based resolution —
  treat `true` as high priority; final result is `true` if any writer sets
  `true`. When conflicting semantics exist, use the `sourcePriority` map to
  deterministically break ties.

- `reduce_timestamps`: use `max(timestamp)` for `last_modified` style fields.

Each reducer must document its input and output invariants (types, required
keys) and include unit tests demonstrating the expected merged result for
concurrent inputs.

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
2. Runs the query node either inline in the main compiled graph (default) or
   as a separate pre-step (`QueryOnlyGraphStep`) when conditions require
   immediate clarification output. Execution policy:

   - Default: execute `query` inline as part of the main `StateGraph` to
     reduce latency (`runQueryPrestep = false`). SSE output from the query is
     buffered and emitted in order with the rest of the graph's sections.
   - If `request.isClarification == true` OR the orchestrator is invoked with
     `runQueryPrestep = true` then run `query` as a separate pre-step
     (`QueryOnlyGraphStep`) before invoking the compiled graph. In this case
     clarification SSE events are emitted immediately as they are produced
     by the pre-step (unbuffered), enabling the UI to show clarifying
     questions without waiting for the rest of the graph.

   Implementers: call `QueryOnlyGraphStep` when the pre-step condition is
   satisfied; otherwise include `QueryNode` inside the compiled `StateGraph`.

3. Returns clarification SSE events immediately when required (pre-step
   behavior) or emits them as part of the main stream when the `query` runs
   inline (buffered behavior).
4. Emits analysis status before invoking the remaining compiled graph.
5. Receives the completed graph state.
6. Attempts to store the report.
   - On success: continue to step 7.
   - On storage failure (DB / I/O): emit a non-terminal `error` SSE event with
     storage failure details (`error.type = "storage_failure"`, include an
     opaque `error.ref` for troubleshooting), keep the stream open, and
     continue emitting report sections to the client.
   - The orchestrator MUST trigger configurable retries for the storage
     operation using exponential backoff (default: 5 attempts, backoff base 2,
     randomized jitter). If retries eventually succeed, emit a follow-up
     `status` SSE event indicating storage succeeded.
   - If retries exhaust, emit a terminal `error` SSE event, record durable
     report metadata `storage_failed` (distinct from an unpersisted failed
     workflow), and close the stream so background workers can pick up the
     failed storage artifact for later retry or manual recovery.
   - The report metadata key `storage_failed` should include retry counts,
     last error, and a durable `report_ref` to identify the persisted object
     (if any partial artifact exists).
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
- Graph execution errors terminate the active run: the SSE layer emits a
  terminal `error` event with a sanitized message and then closes the stream.
- Post-graph storage failures are handled differently: the SSE layer emits a
  non-terminal `error` event with storage failure details while keeping the
  stream open and continuing to send report sections (see storage retry rule
  above). If storage retries ultimately fail, emit a terminal `error` and
  close the stream.
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
