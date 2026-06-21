# Financial AI Agent for Market Insights

Product Requirements Document + Technical Design Document

Version: 3.0  
Author: Pearl  
Status: In Progress (Milestones 1-5 implemented; memory, observability, and deployment ongoing)  
Last Updated: June 2026

## 1. Product Vision

Financial AI Agent for Market Insights is a production-grade multi-agent financial research platform that converts a natural language market question into a structured, citation-backed investment research report in real time.

The product is designed as a portfolio-grade AI systems engineering project. It should demonstrate multi-agent orchestration, LangGraph workflows, live streaming, financial data integration, retrieval memory, modern frontend architecture, observability, and deployment readiness.

The system should help users move from scattered research to a coherent first-pass market view without manually checking news sites, filings, charts, and financial APIs.

## 2. Problem Statement

Retail investors, finance students, and finance-curious developers spend significant time gathering market context from multiple sources:

- News articles
- Earnings reports
- Company filings
- Stock price data
- Analyst commentary
- Historical context

Existing tools usually provide either raw financial data or generic AI summaries. Raw tools require manual interpretation, while generic summaries often lack source grounding, structured reasoning, and financial data validation.

There is a need for a lightweight research assistant that combines live news, market data, sentiment analysis, memory, and multi-agent reasoning into one transparent workflow.

## 3. Goals and Non-Goals

### 3.1 Product Goals

- Accept plain-English financial queries about stocks, sectors, companies, or market events.
- Retrieve live financial information from web and market data sources.
- Generate structured reports with citations and separated sections.
- Stream responses to the frontend in real time.
- Store useful interaction history for future context.
- Provide an impressive portfolio artifact for AI Systems Engineering and GenAI Engineering roles.

### 3.2 Technical Goals

- Implement LangGraph-based orchestration.
- Use specialized agents with clear responsibilities.
- Wrap external APIs inside service classes.
- Use FastAPI for backend APIs and SSE streaming.
- Use Next.js (App Router) and TypeScript for the frontend. The current build runs Next.js 16 with React 19 and plain CSS; Tailwind CSS and shadcn/ui remain a future styling upgrade, not part of the shipped MVP.
- Add ChromaDB-based memory.
- Add Langfuse observability for traces, latency, costs, errors, and tool calls.
- Maintain production-quality structure, tests, logging, and environment-based configuration.

### 3.3 Non-Goals

- The product is not a trading platform.
- The product will not place orders or integrate with brokerages.
- The product is not a financial advisor and must not present outputs as investment recommendations.
- The MVP does not need real-time tick-by-tick market data.
- The MVP does not need authenticated user accounts.

## 4. Target Users

### 4.1 Finance Student

Needs:

- Quick stock research
- Market concept explanations
- Company outlook summaries
- Risk and sentiment understanding

### 4.2 Retail Investor

Needs:

- Recent news summaries
- Price action context
- Sentiment tracking
- Key risk identification
- Source-backed research

### 4.3 Recruiter or Technical Evaluator

Needs:

- Evidence of AI engineering skill
- Evidence of backend system design
- Evidence of clean architecture
- A public demo that works without local setup
- Clear README, diagrams, and traceable implementation choices

## 5. Core User Story

As a user, I want to type:

```text
What is the outlook for TCS in Q3 2026?
```

and receive a structured report covering executive summary, recent news, price action, market metrics, sentiment, key risks, outlook, and citations, so that I can form an informed first-pass view quickly.

## 6. User Journey

1. User enters a natural language financial query.
2. System extracts intent, company, ticker, market, and timeframe.
3. System searches recent web sources such as news, filings, and earnings material.
4. System retrieves market data such as price, volume, market cap, 52-week range, and valuation ratios.
5. System analyzes source sentiment.
6. System retrieves relevant prior context from memory.
7. System generates a structured markdown report with citations.
8. System streams the report to the frontend.
9. System stores the interaction for history and future retrieval.

## 7. MVP Scope

### 7.1 MVP Features

| ID | Feature | Description |
| --- | --- | --- |
| F1 | Natural language query input | Single text input supporting company names, tickers, sectors, and market events. |
| F2 | Query understanding | Extract ticker, company, intent, region, and timeframe. |
| F3 | Multi-agent orchestration | LangGraph workflow with specialized agents and shared state. |
| F4 | Live web research | Pull recent articles, snippets, URLs, source names, and dates. |
| F5 | Market data fetch | Retrieve current price, historical performance, volume, market cap, PE ratio, and 52-week range. |
| F6 | Sentiment analysis | Score relevant headlines and snippets using an LLM or classifier. |
| F7 | Structured report | Generate markdown report with sections for summary, price action, news, sentiment, risks, and outlook. |
| F8 | Citations | Include source references for claims and news-backed statements. |
| F9 | SSE streaming | Stream report chunks and status updates to the frontend. |
| F10 | Basic history | Store past reports and allow session-level retrieval. |

### 7.2 Post-MVP Features

| ID | Feature | Description |
| --- | --- | --- |
| P1 | Conversation memory | Follow-up questions reference prior reports and session context. |
| P2 | Comparison mode | Queries such as "Compare Infosys vs TCS" trigger parallel company analysis. |
| P3 | Watchlist | Users save tickers for repeated tracking. |
| P4 | Weekly digest | Scheduled digest for watchlist tickers. |
| P5 | Chart embeds | Inline price charts using Recharts. |
| P6 | PDF export | One-click export of reports. |
| P7 | Portfolio analysis | Analyze a basket of holdings and summarize exposure. |

## 8. Report Requirements

Every generated report must include:

1. Executive Summary
2. Company or Asset Context
3. Price Action
4. Key Market Metrics
5. News Analysis
6. Sentiment Summary
7. Key Risks
8. Outlook
9. Sources and Citations
10. Informational Disclaimer

Reports must avoid uncited factual claims where possible. Market numbers must come from market data APIs, not from LLM guesses.

## 9. System Architecture

```text
User
  |
  v
Next.js 15 Frontend
  |
  v
FastAPI Gateway
  |
  v
LangGraph Orchestrator
  |
  +--> Query Understanding Agent
  |
  +--> Parallel Branch
       +--> Research Agent
       +--> Market Data Agent
       +--> Sentiment Agent
  |
  +--> Memory Agent
  |
  +--> Report Agent
  |
  v
SSE Streaming Layer
  |
  v
Frontend Report View
```

## 10. Agent Architecture

### 10.1 Query Understanding Agent

Responsibilities:

- Intent classification
- Ticker extraction
- Company/entity extraction
- Timeframe detection
- Market/region inference

Input:

```json
{
  "query": "What is the outlook for TCS in Q3 2026?"
}
```

Output:

```json
{
  "ticker": "TCS.NS",
  "company": "Tata Consultancy Services",
  "intent": "outlook",
  "timeframe": "Q3 2026",
  "region": "India"
}
```

### 10.2 Research Agent

Responsibilities:

- Search recent financial news.
- Search earnings reports and filings where available.
- Gather source metadata.
- Return source snippets and URLs.

Tools:

- Tavily
- Serper
- Optional fallback web search provider

Output:

```json
{
  "articles": [
    {
      "title": "Article title",
      "url": "https://example.com",
      "source": "Source name",
      "published_at": "2026-06-01",
      "snippet": "Short summary..."
    }
  ]
}
```

### 10.3 Market Data Agent

Responsibilities:

- Fetch current price.
- Fetch recent historical performance.
- Fetch volume, market cap, PE ratio, 52-week high/low, and other available metrics.
- Normalize market data into a consistent schema.

Tools:

- yfinance
- Alpha Vantage

### 10.4 Sentiment Agent

Responsibilities:

- Analyze article titles and snippets.
- Score overall sentiment.
- Explain major drivers of sentiment.
- Return confidence and source count.

Output:

```json
{
  "label": "positive",
  "score": 0.74,
  "confidence": 0.82,
  "drivers": ["strong deal wins", "stable earnings outlook"]
}
```

### 10.5 Memory Agent

Responsibilities:

- Retrieve prior reports by ticker, company, session, and semantic similarity.
- Provide historical context to the report agent.
- Store completed reports after generation.

Tools:

- ChromaDB
- text-embedding-004 or equivalent embedding model

### 10.6 Report Agent

Responsibilities:

- Combine research, market data, sentiment, and memory context.
- Generate final markdown report.
- Include citations.
- Avoid unsupported financial claims.
- Include informational disclaimer.

## 11. LangGraph Workflow

```text
START
  |
  v
Query Understanding Agent
  |
  v
Research Agent + Market Data Agent + Sentiment Agent
  |
  v
Memory Agent
  |
  v
Report Agent
  |
  v
END
```

The Research Agent, Market Data Agent, and Sentiment Agent should run as parallel branches where possible. Sentiment may either run directly from research output or run after research completes, depending on implementation complexity.

## 12. Shared State Schema

```python
from typing import TypedDict

class AgentState(TypedDict, total=False):
    session_id: str
    query: str
    ticker: str
    company: str
    intent: str
    timeframe: str
    region: str
    articles: list[dict]
    market_data: dict
    sentiment: dict
    memory_context: list[dict]
    report: str
    citations: list[dict]
    errors: list[dict]
```

## 13. Backend Design

Framework:

- FastAPI
- Python 3.11+
- Pydantic
- LangGraph

Recommended structure:

```text
backend/
  agents/
    query_agent.py
    research_agent.py
    market_data_agent.py
    sentiment_agent.py
    memory_agent.py
    report_agent.py
  graphs/
    financial_research_graph.py
  prompts/
    query_understanding.md
    sentiment.md
    report.md
  services/
    llm_service.py
    search_service.py
    market_data_service.py
    citation_service.py
  tools/
    tavily_tool.py
    yfinance_tool.py
    alpha_vantage_tool.py
  routes/
    query.py
    history.py
    health.py
  models/
  schemas/
    query.py
    report.py
    events.py
  memory/
    chroma_store.py
  tests/
  config.py
  main.py
```

Backend rules:

- No business logic inside routes.
- All agent logic must be isolated.
- All prompts must live in the prompts directory.
- External APIs must be wrapped inside service classes.
- All request and response payloads must use Pydantic schemas.
- Structured logging must be used across API, agent, and tool layers.

## 14. API Design

### 14.1 POST /api/query

Starts a financial research workflow and returns an SSE stream.

Request:

```json
{
  "query": "What is the outlook for Reliance Industries?",
  "session_id": "abc123"
}
```

SSE events:

```text
data: {"type": "status", "agent": "research", "message": "Searching recent sources"}
data: {"type": "section", "title": "Executive Summary"}
data: {"type": "delta", "content": "Reliance Industries has recently..."}
data: {"type": "citation", "url": "https://example.com", "title": "Source title"}
data: {"type": "done"}
```

### 14.2 GET /api/history

Returns past queries and report summaries for the current signed-cookie session. The session ID is never accepted from the client; it is derived from the `financial_session` HMAC-signed cookie.

### 14.3 GET /api/report/{report_id}

Returns a stored report by ID.

### 14.4 GET /api/health

Returns backend, LLM, market data, search, and memory health status.

## 15. Frontend Design

### 15.1 Shipped MVP (current)

Framework:

- Next.js 16 (App Router)
- React 19
- TypeScript
- Plain CSS (no Tailwind/shadcn yet)

Current structure:

```text
frontend/
  app/
    layout.tsx
    page.tsx
  components/
    financial-agent-app.tsx   # single-page query + streamed report + statements explorer
  lib/
    api.ts                    # SSE client, typed stream events, http(s) citation filter
```

The MVP is one streaming page: query input, live section/delta rendering, citation list (http/https only), and an expandable Financial Statements explorer (Income Statement / Balance Sheet / Cash Flow tabs with quarterly/annual history). Requests use `credentials: "include"` for the signed-cookie session.

### 15.2 Target structure (not yet built)

The following modular layout and component split are a future refactor target, not the current implementation:

```text
frontend/
  app/
    page.tsx
    report/[id]/page.tsx
    history/page.tsx
  components/
    query-input.tsx
    report-view.tsx
    report-section.tsx
    metrics-panel.tsx
    stock-chart.tsx
    citations-list.tsx
    agent-status.tsx
  hooks/
    use-query-stream.ts
    use-history.ts
  services/
    api-client.ts
  lib/
    markdown.ts
  types/
    api.ts
```

Tailwind CSS, shadcn/ui, and Recharts charts are deferred to this phase.

## 16. UI Screens

> Status: design target. The shipped MVP (see 15.1) implements the home query input, streaming report view, citations, and the Financial Statements explorer on a single page. Separate Report and History screens and the loading/skeleton states below are not yet built.

### 16.1 Home Screen

Primary elements:

- Centered query input
- Placeholder: "Ask about any stock, sector, or market event..."
- Suggested prompts
- Recent queries
- Submit/loading state

### 16.2 Report View

Left panel:

- Streamed markdown report
- Section-by-section rendering
- Citations as numbered references

Right panel:

- Stock chart
- Key metrics card
- Sources list
- Session history

Report sections:

- Executive Summary
- Price Action
- News Analysis
- Sentiment
- Key Risks
- Outlook
- Citations

### 16.3 History View

Features:

- Past reports
- Search history
- Saved reports
- Filter by ticker or company

### 16.4 UI States

Loading:

- Skeleton loader
- Active agent status label
- Progress-style status messages

Streaming:

- Token-by-token report rendering
- Sections appear as available
- Citations populate progressively

Error:

- Friendly error message
- Retry action
- Clear explanation when external APIs fail

## 17. Memory Architecture

Database:

- ChromaDB

Collection:

- financial_reports

Stored metadata:

```json
{
  "report_id": "uuid",
  "session_id": "abc123",
  "ticker": "TCS.NS",
  "company": "Tata Consultancy Services",
  "query": "What is the outlook for TCS in Q3 2026?",
  "report_summary": "Short summary...",
  "timestamp": "2026-06-03T10:00:00Z"
}
```

Stored document:

- Full report text
- Optional source summaries

Embedding model:

- text-embedding-004 or equivalent

Retrieval behavior:

- Retrieve by ticker match first.
- Then retrieve semantically similar prior reports.
- Limit memory context to the most relevant 3 to 5 records.

## 18. Observability

Tool:

- Langfuse

Track:

- Agent latency
- Prompt inputs and outputs
- Token usage
- LLM cost
- Tool calls
- External API errors
- Graph execution path
- User query and session ID

Each request should create one trace with child spans for agents and tools.

## 19. Security and Safety

Requirements:

- Store API keys in environment variables.
- Never expose API keys to the frontend.
- Add input validation for query length and content.
- Add rate limiting.
- Add request timeout handling.
- Add external API error fallbacks.
- Add financial disclaimer to every report.
- Avoid presenting outputs as personalized financial advice.
- Log errors without leaking secrets.

Required disclaimer:

```text
This report is for informational and educational purposes only. It is not financial advice, investment advice, or a recommendation to buy, sell, or hold any security.
```

## 20. Deployment

Frontend:

- Vercel

Backend:

- Railway or Render

Database:

- ChromaDB with persistent volume

Observability:

- Langfuse Cloud

Environment variables:

```text
GOOGLE_API_KEY=
TAVILY_API_KEY=
SERPER_API_KEY=
ALPHA_VANTAGE_API_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
CHROMA_DB_PATH=
```

## 21. Performance Targets

| Metric | Target |
| --- | --- |
| Time to first token | Under 5 seconds |
| Full report generation | Under 30 seconds |
| Concurrent users | 5 portfolio-demo users |
| Cost per query | Under $0.01 |
| Articles per report | 5 to 8 relevant sources |
| Memory retrieval | Under 1 second |

## 22. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| yfinance or Alpha Vantage rate limits | Medium | Medium | Cache data for 5 minutes per ticker and provide graceful fallback. |
| Hallucinated financial numbers | High | High | Require market numbers to come from API data only. Add source attribution. |
| Weak ticker extraction | Medium | High | Use LLM extraction plus symbol lookup fallback. |
| LangGraph complexity | Medium | Medium | Build single-agent MVP first, then migrate to multi-agent graph. |
| SSE timeout on free hosting | Low | Medium | Send heartbeat events every 15 seconds. |
| Search result noise | Medium | Medium | Rank sources by relevance, recency, and financial-source credibility. |
| API failures | Medium | Medium | Return partial report with clear missing-data notes. |

## 23. Success Metrics

The project is successful when:

- It generates useful reports for at least 10 different stock or market queries.
- Reports include citations and avoid unsupported financial numbers.
- Streaming works from backend to frontend.
- LangGraph traces show the full agent workflow.
- ChromaDB memory retrieves prior context.
- Langfuse traces are visible.
- The app is deployed publicly.
- README includes architecture diagrams, setup instructions, and demo examples.
- A recruiter can test the project without local setup.

## 24. Milestones

| Phase | Milestone | Output |
| --- | --- | --- |
| 1 | Single-agent MVP | One backend endpoint produces a basic cited report. |
| 2 | Market data and sentiment | Report includes price metrics and sentiment score. |
| 3 | LangGraph orchestration | Query, research, market, sentiment, memory, and report agents wired together. |
| 4 | Streaming | FastAPI streams report chunks through SSE. |
| 5 | Frontend | Next.js UI submits queries and renders streamed reports. |
| 6 | Memory | ChromaDB stores and retrieves prior reports. |
| 7 | Observability | Langfuse traces show graph execution and tool calls. |
| 8 | Deployment and polish | Public app, README, diagrams, examples, and tests. |

## 25. Coding Standards

Requirements:

- Type hints everywhere.
- Pydantic schemas for API boundaries.
- Modular backend architecture.
- Unit tests for services, agents, and schema behavior.
- Integration tests for the graph and streaming endpoint.
- Structured logging.
- Environment-based configuration.
- Clear error handling.
- Prompts versioned as separate files.
- Services must abstract external APIs.
- Routes must stay thin.

## 26. Testing Strategy

Unit tests:

- Query parsing
- Market data normalization
- Sentiment response parsing
- Citation formatting
- Memory storage and retrieval

Integration tests:

- Full graph execution with mocked tools
- API query endpoint with mocked graph
- SSE event formatting
- History retrieval

Manual demo tests:

- "What is the outlook for TCS in Q3 2026?"
- "Summarize recent news for Reliance Industries."
- "Compare Infosys vs TCS."
- "What are the risks for HDFC Bank?"
- "How is the Indian IT sector performing?"

## 27. Definition of Done

The project is complete when:

- The multi-agent graph executes successfully.
- Reports contain citations.
- Market numbers come from API data.
- Streaming works in the browser.
- Memory storage and retrieval works.
- Langfuse traces are visible.
- Public frontend and backend deployments are available.
- README contains architecture diagrams and demo instructions.
- Tests cover core service and graph behavior.
- Recruiters can open the deployed URL, submit a query, and see a complete streamed report.

