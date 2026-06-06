# Live Accuracy Evaluation Design

## Objective

Add a manually invoked evaluation suite that runs the financial research system against current live APIs and measures factual safety, query understanding, report completeness, multi-company coverage, citations, relevance, and latency.

The evaluator is a development and portfolio-quality tool. It does not run during normal `pytest` execution and does not block application startup.

## Command

Run from `backend/`:

```powershell
python -m app.evaluation.run_live
```

Optional arguments:

```powershell
python -m app.evaluation.run_live --case meta-google-amazon
python -m app.evaluation.run_live --category comparison
python -m app.evaluation.run_live --limit 5
python -m app.evaluation.run_live --output evaluation_results
```

The default run executes every enabled benchmark case sequentially. Sequential execution limits provider bursts and makes failures easier to diagnose.

## Scope

### Included

- Live query understanding
- Live Tavily or Serper research
- Live Yahoo Finance or Alpha Vantage market data
- Live Gemini report generation
- Deterministic validation
- Gemini-based qualitative judging
- Timing and provider/fallback reporting
- Timestamped JSON and human-readable Markdown results

### Excluded

- Automated scheduled runs
- CI execution
- Historical backtesting
- Investment-return prediction accuracy
- Trading recommendations
- Provider-response mocking
- Frontend browser testing

## Package Structure

```text
backend/app/evaluation/
  __init__.py
  benchmark_cases.py
  deterministic_checks.py
  judge_service.py
  models.py
  runner.py
  run_live.py

backend/evaluation_results/
  .gitkeep
  live-eval-<timestamp>.json
  live-eval-<timestamp>.md

backend/tests/
  test_evaluation_checks.py
  test_evaluation_scoring.py
```

Generated result files are ignored by Git. The evaluator implementation and its deterministic unit tests are committed.

## Benchmark Cases

Each case has a stable ID, category, query, expected entities, expected intent, expected behavior, and scoring metadata.

Initial suite:

| ID | Category | Query | Required behavior |
|---|---|---|---|
| `lt-sentiment` | single company | What do you think about LT and its sentiment? | Resolve Larsen & Toubro, not the word "sentiment" |
| `apple-outlook` | single company | Analyze Apple. | Resolve Apple/AAPL |
| `meta-alias` | alias | What do you think about Meta? | Resolve Meta Platforms/META |
| `infosys-misspelling` | misspelling | Analze Infosis | Resolve Infosys/INFY.NS |
| `tata-ambiguous` | clarification | Analyze Tata. | Ask for clarification and list plausible Tata companies |
| `adani-ambiguous` | clarification | Generate a financial report on profit and loss of Adani. | Ask which Adani company |
| `tata-motors-explicit` | disambiguation | Analyze Tata Motors. | Do not ask which Tata company |
| `us-comparison` | comparison | Compare Meta, Google and Amazon. | Cover all three entities |
| `india-comparison` | comparison | Compare Reliance, Adani Ports, and Tata Motors. | Cover all three entities |
| `adani-power-pnl` | P&L | Generate a profit and loss report for Adani Power. | Produce P&L sections and grounded figures |
| `birlasoft-pnl` | P&L | Generate a profit and loss report for Birlasoft. | Preserve available source figures and mark missing metrics unavailable |
| `reliance-outlook` | single company | What is the outlook for Reliance Industries? | Resolve Reliance Industries/RELIANCE.NS |

Benchmark cases must not assert exact live prices or sentiment scores because those values change. They assert identity, structure, provenance, and internal consistency.

## Execution Flow

For every benchmark case:

1. Create an isolated session ID prefixed with `live-eval`.
2. Run `run_query_agent` and retain its structured state.
3. If clarification is expected, evaluate the clarification response and stop the case.
4. Otherwise run research, market data, sentiment, memory, and report agents using the production implementations.
5. Capture the final state, report, citations, provider metadata, fallback status, errors, and stage timings.
6. Run deterministic checks.
7. Submit the query, expectations, report, citations, and deterministic findings to the qualitative judge.
8. Calculate the weighted score.
9. Write the case result immediately so an interrupted run retains completed cases.

Evaluation sessions must not pollute normal report history. The runner will execute agents directly and will not call `report_store.add`.

## Deterministic Checks

Each check returns `pass`, `fail`, or `not_applicable`, plus evidence and a score from 0 to 1.

### Entity Accuracy

- Expected company aliases are present in parsed entities.
- Expected ticker symbols match normalized ticker aliases.
- No unrelated word from the query is selected as the company or ticker.
- Explicit subsidiaries such as Tata Motors bypass parent-group clarification.

### Intent Accuracy

- Comparison queries resolve to `comparison`.
- P&L queries resolve to `financial_statement_analysis`.
- Sentiment/outlook queries resolve to the appropriate supported intent.
- Ambiguous parent-group queries request clarification.

### Multi-Company Coverage

- Every expected comparison entity appears in structured comparison data.
- Every expected entity has its own market-data and research result object.
- Every expected entity appears in the final report.
- No single company receives more than 60% of company-specific report mentions when three companies are requested.

### Report Completeness

- Required headings exist for the detected intent.
- The disclaimer is present exactly.
- The report is at least 500 characters unless it is a clarification response.
- The stream/report terminates with a completed result rather than a truncated sentence.

### Citation Quality

- At least one valid HTTP(S) citation is present for report-producing cases.
- Citation URLs are unique after normalization.
- Report source references map to returned citations or evidence source IDs.
- P&L numeric evidence includes `[F#/S#]` or `[O#/S#]` provenance.

The evaluator does not require every citation URL to return HTTP 200 because publisher bot protection can produce false failures. URL reachability is recorded as diagnostic data and does not affect the primary score.

### Numeric Grounding

- Every financial number in a P&L report must be permitted by structured facts, source observations, or market data using the production validator.
- Missing values must remain unavailable rather than being replaced with estimates.
- Source observations must preserve their original numeric statement.
- Market price claims must match the captured market-data value after formatting normalization.

### Runtime Health

- No unhandled exception occurred.
- Required provider keys are configured.
- Report fallback status is recorded.
- Total and per-stage latency are recorded.

## Qualitative Judge

Gemini evaluates dimensions that deterministic checks cannot reliably measure:

- Query relevance
- Analytical usefulness
- Clarity and organization
- Balance and uncertainty handling
- Comparison fairness
- Whether conclusions stay within supplied evidence

The judge receives only the benchmark expectation, final report, citations, structured evidence, and deterministic findings. It must return strict JSON validated by Pydantic:

```json
{
  "relevance": 0,
  "clarity": 0,
  "usefulness": 0,
  "evidence_discipline": 0,
  "comparison_fairness": null,
  "critical_findings": [],
  "reasoning": "Short explanation"
}
```

Scores are integers from 0 to 5. `comparison_fairness` is null for non-comparison cases.

The judge uses temperature 0 and receives explicit instructions not to reward confident language, length, or unsupported specificity. Judge failure does not discard deterministic results; the qualitative portion becomes unavailable and the run is marked incomplete.

## Scoring

### Case Score

| Dimension | Weight |
|---|---:|
| Entity and ticker accuracy | 20% |
| Intent or clarification accuracy | 15% |
| Numeric grounding | 20% |
| Citation quality | 10% |
| Completeness | 10% |
| Multi-company coverage | 10% |
| LLM qualitative score | 15% |

`not_applicable` dimensions are removed and the remaining weights are normalized.

### Run Score

The overall score is the arithmetic mean of completed case scores. Category scores are also reported separately so a strong single-company score cannot hide weak comparison behavior.

### Result Levels

- `90-100`: excellent
- `80-89.99`: good
- `70-79.99`: needs improvement
- `<70`: failing

### Critical Failures

Any of the following fails the run regardless of average score:

- Wrong company or ticker on an unambiguous query
- Missing a requested company in comparison structured data
- Unsupported financial number in a P&L report
- Invented citation URL
- Explicit company query incorrectly requests parent-group clarification
- Unhandled exception

The command exits:

- `0` when score is at least 80, no critical failures exist, and the judge completed.
- `1` for quality failures or critical failures.
- `2` for invalid configuration, missing required keys, or an unusable judge.

## Output

### JSON

The JSON result contains:

- Run ID and UTC timestamp
- Git commit and dirty-worktree flag
- Configured provider names without secret values
- Model name
- Total duration
- Overall and category scores
- Critical failures
- Per-case expectations, captured state, checks, judge result, latency, errors, and fallback usage

Secrets, full environment values, and API request headers are never written.

### Markdown

The Markdown summary contains:

- Overall score and result level
- Critical failures
- Category score table
- Case score table
- Failed checks with concise evidence
- Fallback and latency summary
- Paths to the corresponding JSON result

Console output stays compact and prints progress, case result, duration, and final artifact paths.

## Configuration and Cost Controls

Before execution, validate:

- `GOOGLE_API_KEY`
- At least one of `TAVILY_API_KEY` or `SERPER_API_KEY`

Market data may use Yahoo Finance without a key; Alpha Vantage remains an optional fallback.

Default protections:

- Sequential cases
- Maximum 12 cases per complete run
- One qualitative judge call per case
- `--limit` and `--case` selectors
- No automatic retries beyond existing provider-service behavior
- Estimated API-call count printed before execution
- Explicit confirmation required only when more than 12 cases are requested

## Error Handling

- A provider failure is captured against the affected case instead of aborting the whole run.
- Rate limits are identified separately from application failures.
- A case timeout produces a failed runtime-health check and execution continues.
- Partial artifacts are flushed after each case.
- Keyboard interruption writes completed results and exits with code 1.
- Missing required keys stops before any provider calls and exits with code 2.

## Testing Strategy

Normal unit tests never call live APIs.

Unit tests cover:

- Benchmark schema validation
- Entity and ticker matching
- Comparison coverage
- Required heading checks
- Citation normalization and mapping
- Numeric grounding integration
- Weight normalization
- Critical-failure precedence
- Exit-code selection
- JSON judge response validation
- Artifact serialization with secret-field exclusion

The live command itself is the integration test. Its output records provider instability separately from product accuracy failures.

## Acceptance Criteria

- The manual command runs the curated live benchmark without starting FastAPI or Next.js.
- At least 12 cases span single-company, alias, misspelling, clarification, comparison, and P&L behavior.
- Every case receives deterministic results and, when Gemini is available, qualitative scores.
- Unsupported report numbers trigger a critical failure.
- Comparison reports are checked for every requested entity.
- Result artifacts are timestamped and contain no secrets.
- A failed case does not prevent later cases from running.
- The process exits nonzero when quality is below threshold or any critical failure occurs.
- Existing unit tests continue to pass without making network calls.
