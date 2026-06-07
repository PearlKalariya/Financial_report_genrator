# Security Hardening Design

## Goal

Harden the portfolio application against cross-user history access, API-cost abuse, dependency vulnerabilities, prompt injection, telemetry leakage, unsafe citation links, and concurrent storage corruption without adding account registration or Redis.

## Session Security

- The backend owns session identity.
- A random session ID is stored in a signed cookie named `financial_session`.
- The signature uses HMAC-SHA256 and a server-side secret.
- Cookies are `HttpOnly` and configurable for `Secure` and `SameSite`.
- Invalid or tampered cookies create a new isolated session.
- Clients no longer submit or choose session IDs.
- `GET /api/history` returns history only for the current signed session.

If `SESSION_SECRET` is absent, the backend generates an ephemeral secret at startup. Production deployments must configure a persistent secret so sessions survive restarts.

## Rate Limiting

Use an in-memory token bucket per signed session:

- Sustained rate: 5 report requests per minute.
- Burst capacity: 2 additional requests.
- Maximum concurrent reports per session: 2.
- Rejected requests return HTTP 429 with `Retry-After`.
- Health and history are not rate limited.
- Counters are process-local; Redis remains the future multi-instance replacement.

## Prompt and Output Boundaries

- Search snippets and memory are explicitly delimited as untrusted data in the Gemini prompt.
- The model is instructed never to follow instructions inside sources, citations, or memory.
- Existing numeric grounding and completeness validation remain authoritative.
- Citation URLs are accepted only when their scheme is `http` or `https`.
- The frontend independently rejects unsafe citation schemes before rendering links.

## Telemetry Privacy

- Langfuse receives a compact redacted state summary rather than the full agent state.
- Traces retain operational fields: intent, ticker, company, article count, entity count, error count, and provider/fallback status.
- Queries, article snippets, reports, memory content, financial evidence, and session IDs are not sent as trace payloads.
- Session identity sent to Langfuse is a one-way hash, not the cookie session ID.

## Storage Safety

- JSON history remains local for the portfolio demo.
- Reads and writes use a process lock.
- Writes use a temporary file in the same directory followed by atomic replacement.
- History records remain separated by signed session ownership.
- Storage encryption is deferred because this demo stores generated reports rather than regulated account data.

## HTTP Hardening

- Add `TrustedHostMiddleware` with environment-configurable hosts.
- Add response headers: `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, and a restrictive API-oriented Content Security Policy.
- Keep explicit CORS origins and credential support.
- Streaming responses use `Cache-Control: no-store`.

## Dependency Remediation

Backend:

- `fastapi==0.136.3`
- `python-dotenv==1.2.2`
- `pytest==9.0.3`

This resolves the audited Starlette, dotenv, and pytest advisories through compatible versions.

Frontend:

- Override PostCSS to a patched `8.5.x` release.
- Regenerate `package-lock.json`.
- Require a clean `npm audit` result or document any remaining upstream-only advisory.

## Tests

Add tests for:

- Signed-cookie creation and verification
- Tampered-cookie rejection
- Session-isolated history
- Request-body session IDs being ignored
- Token-bucket limits and retry timing
- Per-session concurrency limits
- Unsafe citation URL filtering
- Prompt untrusted-data instructions
- Telemetry redaction
- Atomic concurrent storage writes
- Security headers and trusted hosts

## Acceptance Criteria

- No endpoint trusts a client-provided session ID.
- One anonymous session cannot retrieve another session's reports.
- The eighth immediate report request for one session is rejected after the 5-per-minute plus 2-burst allowance.
- Unsafe citation schemes never reach the clickable frontend.
- Langfuse payloads contain no query, report, source snippet, memory, evidence, or raw session ID.
- Backend and frontend dependency audits report no known vulnerabilities relevant to installed packages.
- Existing financial accuracy tests continue to pass.
