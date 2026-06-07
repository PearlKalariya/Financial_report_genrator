# Structured Financial Statements Design

## Goal

Add normalized quarterly and annual income statements, balance sheets, and cash-flow statements to financial research reports. Retain every provider period, summarize the latest four quarters and three annual years in reports, and expose full history as structured frontend data.

## Provider Strategy

1. Query Yahoo Finance fundamentals time series for all supported metrics.
2. If Yahoo returns no usable statements, query Alpha Vantage:
   - `INCOME_STATEMENT`
   - `BALANCE_SHEET`
   - `CASH_FLOW`
3. Normalize both providers into one internal schema.
4. Never combine values from different providers inside the same statement bundle.

## Normalized Schema

```text
FinancialStatementBundle
  ticker
  source
  retrieved_at
  currency
  statements
    income_statement
      quarterly[]
      annual[]
    balance_sheet
      quarterly[]
      annual[]
    cash_flow
      quarterly[]
      annual[]

StatementPeriod
  period_end
  period_type
  currency
  values: canonical metric -> raw numeric value
```

Canonical metrics:

- Income statement: revenue, cost of revenue, gross profit, operating income, EBITDA, pretax income, net income, diluted EPS.
- Balance sheet: cash, current assets, total assets, current liabilities, total liabilities, total debt, stockholders' equity.
- Cash flow: operating cash flow, capital expenditure, free cash flow, investing cash flow, financing cash flow.

Missing metrics remain absent. Zero remains a valid value.

## Calculations

Calculations are deterministic and use only values from one normalized period:

- Gross margin = gross profit / revenue
- Operating margin = operating income / revenue
- Net margin = net income / revenue
- Free cash flow = operating cash flow + capital expenditure when the provider omits FCF and capex is reported as a negative outflow
- Period growth = current / previous - 1 only when statement type, currency, and cadence match

Calculated values are labeled as derived and never presented as provider-reported values.

## Caching

- In-memory cache keyed by normalized ticker.
- TTL: 15 minutes.
- Successful empty responses are cached for 2 minutes to reduce repeated provider failures.
- Cache is process-local and can later move to Redis.

## Agent Integration

- `market_data_agent` fetches statements for `financial_statement_analysis`.
- Comparison queries also fetch statements for each company so future comparisons can align periods.
- State receives `financial_statements`.
- The LLM prompt receives the normalized bundle as verified structured data.
- Numeric validation accepts only statement values, approved derived values, existing evidence, and market data.

## Report Behavior

Financial statement reports include:

- Executive Summary
- Income Statement
- Profitability and Growth
- Balance Sheet
- Cash Flow
- Data Quality
- Key Risks
- Outlook
- Sources
- Disclaimer

Markdown tables show the latest four quarterly periods and three annual periods. Full retained history is not dumped into the report.

## Frontend Data

The orchestrator emits a `financial_statements` stream event containing the complete normalized bundle before report text.

The frontend shows an unframed expandable Financial Statements section with:

- Tabs for Income Statement, Balance Sheet, and Cash Flow
- Quarterly/Annual segmented controls
- Horizontally scrollable full-history tables
- Provider, currency, and retrieval time

Values remain raw in transport and are formatted in the frontend.

## Failure Handling

- Provider errors return an empty bundle with an error summary.
- Report generation continues using source evidence when statements are unavailable.
- Mixed currency periods are not compared.
- Unsupported or malformed provider values are ignored.
- Index and macro-market queries do not fetch company statements.

## Acceptance Criteria

- Quarterly and annual data exist for all three statements when providers supply it.
- Every available provider period is retained in structured state.
- Reports show at most four quarters and three years.
- Full history reaches the frontend through a structured SSE event.
- All financial numbers in generated reports pass grounding validation.
- Missing values are never estimated.
- Yahoo failure uses Alpha Vantage when configured.
- Existing security and financial accuracy tests remain green.
