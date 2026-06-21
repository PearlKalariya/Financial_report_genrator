# LangGraph Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Implemented (commit `35e8835`). Deviation from plan: `merge_comparison_data` lives in `app/graphs/financial_research_graph.py`, not `app/agents/state.py`.

**Goal:** Replace the sequential orchestration service with a compiled LangGraph workflow that runs research and market-provider retrieval concurrently without changing the public SSE API.

**Architecture:** A `StateGraph` owns query routing, parallel research and market-provider nodes, sentiment, an analysis join, memory, and report generation. Existing agents remain business-logic boundaries; graph adapters return narrow updates, and the join builds financial evidence only after both articles and market data are available.

**Tech Stack:** Python 3.13, LangGraph 1.1.10, FastAPI, Pydantic, pytest, asyncio

---

### Task 1: Add LangGraph Dependency

**Files:**
- Modify: `backend/requirements.txt`

- [x] **Step 1: Add the pinned runtime dependency**

Add:

```text
langgraph==1.1.10
```

- [x] **Step 2: Install the backend dependencies**

Run:

```powershell
python -m pip install -r requirements.txt
```

Expected: installation succeeds and `langgraph 1.1.10` is available.

- [x] **Step 3: Verify the import**

Run:

```powershell
python -c "from langgraph.graph import START, END, StateGraph; print('langgraph-ok')"
```

Expected: `langgraph-ok`.

### Task 2: Define Parallel-State Merge Behavior

**Files:**
- Modify: `backend/app/agents/state.py`
- Create: `backend/tests/test_financial_research_graph.py`

- [x] **Step 1: Write failing reducer tests**

Add tests that import `merge_comparison_data` and verify entries with the same
ticker retain articles, market data, financial statements, evidence, and
sentiment when updates arrive from different branches.

- [x] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -m pytest tests/test_financial_research_graph.py -q
```

Expected: collection fails because the graph module or reducer does not exist.

- [x] **Step 3: Add reducer annotations and merge helper**

Annotate parallel state fields using `typing.Annotated`. Implement a
deterministic `merge_comparison_data(left, right)` that merges dictionaries by
ticker and preserves input order.

- [x] **Step 4: Run the focused test and verify GREEN**

Run:

```powershell
python -m pytest tests/test_financial_research_graph.py -q
```

Expected: reducer test passes.

### Task 3: Build the Compiled Financial Research Graph

**Files:**
- Create: `backend/app/graphs/__init__.py`
- Create: `backend/app/graphs/financial_research_graph.py`
- Modify: `backend/tests/test_financial_research_graph.py`

- [x] **Step 1: Write failing graph-order tests**

Add tests with injected node functions and `asyncio.Event` coordination that
assert:

- query routes non-clarification state into both branches;
- research and market-provider nodes are active concurrently;
- sentiment starts after research completes;
- join waits for sentiment and market-provider completion;
- memory and report execute after join;
- clarification reaches `END` without downstream calls.

- [x] **Step 2: Run the graph tests and verify RED**

Run:

```powershell
python -m pytest tests/test_financial_research_graph.py -q
```

Expected: graph construction API is missing.

- [x] **Step 3: Implement graph node adapters**

Create adapters with these ownership rules:

```python
query_node -> query/entity/clarification fields
research_node -> articles and comparison articles
market_provider_node -> market data/statements per entity
sentiment_node -> sentiment and comparison sentiment
join_analysis_node -> merged comparison data and financial evidence
memory_node -> memory_context
report_node -> report/citations/model/fallback/error
```

The market-provider node must fetch using `entities` directly and must not
require research-side `comparison_data`.

- [x] **Step 4: Compile the graph**

Build:

```text
START -> query
query -> END when clarification is required
query -> research
query -> market_provider
research -> sentiment
sentiment -> join_analysis
market_provider -> join_analysis
join_analysis -> memory -> report -> END
```

Expose a factory for tests and one application-level compiled graph.

- [x] **Step 5: Run graph tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_financial_research_graph.py -q
```

Expected: all graph tests pass.

### Task 4: Migrate the SSE Orchestrator

**Files:**
- Modify: `backend/app/services/orchestrator.py`
- Modify: `backend/tests/test_services.py`

- [x] **Step 1: Write failing orchestrator compatibility tests**

Add tests that replace the compiled graph with a fake async graph and verify:

- existing status, section, delta, citation, statements, and done events remain;
- clarification does not persist a report;
- successful execution persists exactly one report;
- graph exceptions emit one generic error event and persist nothing.

- [x] **Step 2: Run compatibility tests and verify RED**

Run:

```powershell
python -m pytest tests/test_services.py -q
```

Expected: tests fail because the orchestrator still calls agents directly.

- [x] **Step 3: Replace direct agent calls with graph invocation**

Inject the compiled graph into `FinancialResearchOrchestrator`. Invoke it with:

```python
await self.graph.ainvoke(initial_state, config={"configurable": {"trace": trace}})
```

Keep SSE formatting and persistence in the orchestrator. Catch unexpected graph
exceptions, end the trace with sanitized failure metadata, emit a generic
`error` event, and return without persistence.

- [x] **Step 4: Run compatibility tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_services.py tests/test_security.py -q
```

Expected: compatibility and security tests pass.

### Task 5: Regression and Live Verification

**Files:**
- Modify only if a regression is discovered in files owned by this phase.

- [x] **Step 1: Run the full backend suite**

Run:

```powershell
python -m pytest tests -q
```

Expected: all tests pass.

- [x] **Step 2: Compile backend modules**

Run:

```powershell
python -m compileall app
```

Expected: exit code 0.

- [x] **Step 3: Build the frontend**

Run from `frontend/`:

```powershell
npm.cmd run build
```

Expected: Next.js production build succeeds.

- [x] **Step 4: Restart local services**

Restart FastAPI on `127.0.0.1:8000` and Next.js development mode on
`127.0.0.1:3000`.

- [x] **Step 5: Run a live SSE smoke test**

Submit:

```text
Compare Apple, Meta, and Amazon.
```

Verify the stream returns a comparison report, citations, `done`, no error
event, and one new stored report.

- [x] **Step 6: Verify the graph dependency and runtime**

Confirm `/api/health` is healthy and inspect the compiled graph nodes to verify
`query`, `research`, `market_provider`, `sentiment`, `join_analysis`, `memory`,
and `report` are present.
