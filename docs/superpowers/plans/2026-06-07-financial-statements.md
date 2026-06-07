# Structured Financial Statements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add normalized full-history financial statements to the agent workflow, grounded reports, and expandable frontend tables.

**Architecture:** A focused statement service fetches Yahoo first and Alpha Vantage second, normalizes provider payloads, computes explicitly labeled derived metrics, and caches bundles. The market-data agent adds bundles to state, the report and validator consume them, and SSE transports full history to a frontend statement explorer.

**Tech Stack:** Python, httpx, FastAPI/Pydantic-style dictionaries, pytest, Next.js/TypeScript.

---

### Task 1: Normalized Statement Service

- Write failing normalization, fallback, calculation, and cache tests.
- Implement Yahoo and Alpha Vantage adapters.
- Retain all quarterly and annual periods.

### Task 2: Agent and Report Integration

- Add statement bundle to agent state.
- Fetch bundles for statement and comparison intents.
- Add latest-period report tables and statement-aware Gemini grounding.

### Task 3: Structured Streaming and Frontend Explorer

- Extend stream events with financial statement data.
- Emit the full bundle before report text.
- Add statement tabs, cadence control, and full-history tables.

### Task 4: Verification

- Run backend tests and compile checks.
- Run frontend production build.
- Execute live AAPL and Indian ticker statement smokes.
- Confirm report numeric validation and provider fallback behavior.
