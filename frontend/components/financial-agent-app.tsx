"use client";

import { FormEvent, useMemo, useState } from "react";
import { streamQuery, StreamEvent } from "@/lib/api";

const SESSION_ID = "portfolio-demo-session";

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

export function FinancialAgentApp() {
  const [query, setQuery] = useState(PROMPTS[0]);
  const [report, setReport] = useState("");
  const [status, setStatus] = useState("Ready");
  const [isLoading, setIsLoading] = useState(false);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [error, setError] = useState<string | null>(null);

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
    setIsLoading(true);
    setStatus("Starting research workflow");

    try {
      await streamQuery(query.trim(), SESSION_ID, (streamEvent: StreamEvent) => {
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

        if (streamEvent.type === "done") {
          setStatus(streamEvent.message ?? "Report complete");
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
                citations.map((citation, index) => (
                  <a className="citation" href={citation.url} key={`${citation.url}-${index}`} rel="noreferrer" target="_blank">
                    <span className="citation-title">{index + 1}. {citation.title}</span>
                    <span className="citation-url">{citation.url}</span>
                  </a>
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