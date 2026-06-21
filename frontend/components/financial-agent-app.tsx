"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchHistory,
  FinancialStatementBundle,
  ReportRecord,
  StatementPeriod,
  streamQuery,
  StreamEvent
} from "@/lib/api";

const PROMPTS = [
  "What is the outlook for TCS in Q3 2026?",
  "Summarize recent news for Reliance Industries.",
  "What are the risks for HDFC Bank?",
  "How is Infosys positioned this quarter?"
];

type Citation = {
  title?: string;
  url?: string;
};

const STATEMENT_LABELS = {
  income_statement: "Income Statement",
  balance_sheet: "Balance Sheet",
  cash_flow: "Cash Flow"
} as const;

type StatementKey = keyof typeof STATEMENT_LABELS;
type Cadence = "quarterly" | "annual";

export function FinancialAgentApp() {
  const [query, setQuery] = useState(PROMPTS[0]);
  const [report, setReport] = useState("");
  const [status, setStatus] = useState("Ready");
  const [isLoading, setIsLoading] = useState(false);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [statements, setStatements] = useState<FinancialStatementBundle | null>(null);
  const [statementKey, setStatementKey] = useState<StatementKey>("income_statement");
  const [cadence, setCadence] = useState<Cadence>("quarterly");
  const [history, setHistory] = useState<ReportRecord[]>([]);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await fetchHistory());
    } catch {
      // History is best-effort; ignore transient load failures.
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  function viewHistoryRecord(record: ReportRecord) {
    setQuery(record.query);
    setReport(record.report);
    setCitations(record.citations ?? []);
    setStatements(null);
    setError(null);
    setStatus(`Loaded saved report from ${formatTimestamp(record.created_at)}`);
  }

  const metrics = useMemo(
    () => [
      ["Workflow", isLoading ? "Running" : "Idle"],
      ["Memory", "Session"],
      ["Streaming", "SSE"],
      ["Mode", "MVP"]
    ],
    [isLoading]
  );

  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();

    if (!query.trim()) {
      return;
    }

    setReport("");
    setCitations([]);
    setError(null);
    setStatements(null);
    setIsLoading(true);
    setStatus("Starting research workflow");

    try {
      await streamQuery(query.trim(), (streamEvent: StreamEvent) => {
        if (streamEvent.type === "status") {
          setStatus(`${streamEvent.agent ?? "agent"}: ${streamEvent.message ?? "Working"}`);
        }

        if (streamEvent.type === "section" && streamEvent.title) {
          setStatus(`Writing ${streamEvent.title}`);
        }

        if (streamEvent.type === "delta" && streamEvent.content) {
          setReport((current) => current + streamEvent.content);
        }

        if (streamEvent.type === "citation") {
          setCitations((current) => [...current, streamEvent]);
        }

        if (streamEvent.type === "financial_statements" && streamEvent.data) {
          setStatements(streamEvent.data);
        }

        if (streamEvent.type === "done") {
          setStatus(streamEvent.message ?? "Report complete");
          void loadHistory();
        }
      });
    } catch (streamError) {
      setError(streamError instanceof Error ? streamError.message : "Unexpected streaming error.");
      setStatus("Error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <h1 className="brand-title">Financial AI Agent</h1>
            <p className="brand-subtitle">Multi-agent market research with streamed, citation-backed reports</p>
          </div>
          <div className="status-pill">{status}</div>
        </div>
      </header>

      <div className="workspace">
        <section className="main-panel">
          <div className="query-area">
            <form className="query-form" onSubmit={submit}>
              <textarea
                className="query-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ask about any stock, sector, or market event..."
              />
              <button className="primary-button" disabled={isLoading} type="submit">
                {isLoading ? "Running" : "Research"}
              </button>
            </form>

            <div className="prompt-row">
              {PROMPTS.map((prompt) => (
                <button className="prompt-chip" key={prompt} onClick={() => setQuery(prompt)} type="button">
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          <div className="agent-strip">{status}</div>

          <article className="report">
            {error ? <div className="notice">{error}</div> : null}
            {!report && !error ? (
              <div className="empty-state">
                <h2>Ask a market question</h2>
                <p>The report will stream here as the backend agents complete their work.</p>
              </div>
            ) : (
              <pre>{report}</pre>
            )}
          </article>

          {statements ? (
            <FinancialStatementsExplorer
              bundle={statements}
              cadence={cadence}
              onCadenceChange={setCadence}
              onStatementChange={setStatementKey}
              statementKey={statementKey}
            />
          ) : null}
        </section>

        <aside className="side-panel">
          <section className="side-section">
            <h2>Run Metrics</h2>
            <div className="metric-grid">
              {metrics.map(([label, value]) => (
                <div className="metric" key={label}>
                  <span className="metric-label">{label}</span>
                  <span className="metric-value">{value}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="side-section">
            <h2>Citations</h2>
            <div className="citation-list">
              {citations.length === 0 ? (
                <div className="notice">Sources will appear after report generation.</div>
              ) : (
                citations.filter((citation) => isSafeCitationUrl(citation.url)).map((citation, index) => (
                  <a className="citation" href={citation.url} key={`${citation.url}-${index}`} rel="noreferrer" target="_blank">
                    <span className="citation-title">{index + 1}. {citation.title}</span>
                    <span className="citation-url">{citation.url}</span>
                  </a>
                ))
              )}
            </div>
          </section>

          <section className="side-section">
            <h2>Session History</h2>
            <div className="history-list">
              {history.length === 0 ? (
                <div className="notice">Past reports for this session will appear here.</div>
              ) : (
                history
                  .slice()
                  .reverse()
                  .map((record) => (
                    <button
                      className="history-item"
                      key={record.report_id}
                      onClick={() => viewHistoryRecord(record)}
                      type="button"
                    >
                      <span className="history-query">{record.query}</span>
                      <span className="history-meta">
                        {[record.ticker, formatTimestamp(record.created_at)]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </button>
                  ))
              )}
            </div>
          </section>

          <section className="side-section">
            <h2>Safety</h2>
            <div className="notice">
              Informational and educational only. This MVP does not provide financial advice or trading recommendations.
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}

function FinancialStatementsExplorer({
  bundle,
  cadence,
  onCadenceChange,
  onStatementChange,
  statementKey
}: {
  bundle: FinancialStatementBundle;
  cadence: Cadence;
  onCadenceChange: (cadence: Cadence) => void;
  onStatementChange: (statement: StatementKey) => void;
  statementKey: StatementKey;
}) {
  const periods = bundle.statements[statementKey]?.[cadence] ?? [];
  const metrics = collectMetrics(periods);

  return (
    <section className="statements-section">
      <div className="statements-heading">
        <div>
          <h2>Financial Statements</h2>
          <p>{bundle.ticker} · {bundle.source} · {bundle.currency ?? "Currency unavailable"}</p>
        </div>
        <div className="segmented-control" aria-label="Statement cadence">
          {(["quarterly", "annual"] as Cadence[]).map((option) => (
            <button
              aria-pressed={cadence === option}
              className={cadence === option ? "is-active" : ""}
              key={option}
              onClick={() => onCadenceChange(option)}
              type="button"
            >
              {option === "quarterly" ? "Quarterly" : "Annual"}
            </button>
          ))}
        </div>
      </div>

      <div className="statement-tabs" role="tablist">
        {(Object.keys(STATEMENT_LABELS) as StatementKey[]).map((key) => (
          <button
            aria-selected={statementKey === key}
            className={statementKey === key ? "is-active" : ""}
            key={key}
            onClick={() => onStatementChange(key)}
            role="tab"
            type="button"
          >
            {STATEMENT_LABELS[key]}
          </button>
        ))}
      </div>

      {periods.length ? (
        <div className="statement-table-wrap">
          <table className="statement-table">
            <thead>
              <tr>
                <th>Metric</th>
                {periods.map((period) => <th key={period.period_end}>{period.period_end}</th>)}
              </tr>
            </thead>
            <tbody>
              {metrics.map((metric) => (
                <tr key={metric}>
                  <th>{formatMetricName(metric)}</th>
                  {periods.map((period) => (
                    <td key={`${metric}-${period.period_end}`}>
                      {formatStatementValue(period, metric)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="notice">No {cadence} data was returned for this statement.</div>
      )}
    </section>
  );
}

function collectMetrics(periods: StatementPeriod[]): string[] {
  const metrics = new Set<string>();
  periods.forEach((period) => {
    Object.keys(period.values).forEach((metric) => metrics.add(metric));
    Object.keys(period.derived).forEach((metric) => metrics.add(metric));
  });
  return Array.from(metrics);
}

function formatMetricName(metric: string): string {
  return metric
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatStatementValue(period: StatementPeriod, metric: string): string {
  const value = period.values[metric] ?? period.derived[metric];
  if (value === undefined) {
    return "—";
  }
  if (
    metric.endsWith("margin") ||
    metric.endsWith("growth") ||
    metric.endsWith("change")
  ) {
    return `${(value * 100).toFixed(2)}%`;
  }
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
    style: period.currency ? "currency" : "decimal",
    currency: period.currency || undefined
  }).format(value);
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function isSafeCitationUrl(value?: string): boolean {
  if (!value) {
    return false;
  }

  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}
