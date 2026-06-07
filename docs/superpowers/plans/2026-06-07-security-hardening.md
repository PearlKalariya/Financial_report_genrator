# Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Secure anonymous sessions, limit expensive requests, sanitize trust boundaries, redact telemetry, make storage atomic, and patch vulnerable dependencies.

**Architecture:** Introduce focused session and rate-limit services, route dependencies that derive identity from signed cookies, privacy-safe trace summaries, URL validation at backend and frontend boundaries, and locked atomic JSON persistence. Keep all controls process-local and compatible with the current FastAPI/Next.js deployment.

**Tech Stack:** FastAPI, Pydantic, Python standard-library HMAC/threading/tempfile, Next.js, TypeScript, pytest.

---

### Task 1: Signed Anonymous Sessions

- Add failing tests for valid, missing, and tampered cookies.
- Implement `SessionService` using HMAC-SHA256.
- Remove `session_id` from `QueryRequest`.
- Change query/history routes to resolve identity from cookies.
- Change frontend requests to use `credentials: "include"`.

### Task 2: In-Memory Rate and Concurrency Limits

- Add failing token-bucket and concurrency tests.
- Implement 5/minute refill, capacity 7, and two active reports per session.
- Return HTTP 429 and `Retry-After`.
- Release concurrency slots when streaming ends or fails.

### Task 3: Prompt, Citation, and Telemetry Boundaries

- Add tests for unsafe URL rejection, prompt instructions, and trace redaction.
- Add untrusted-data delimiters and instructions to Gemini prompts.
- Filter citations to HTTP(S) in backend report construction and frontend rendering.
- Replace full-state Langfuse payloads with redacted summaries and hashed session identity.

### Task 4: Atomic Storage and HTTP Headers

- Add concurrent-store and middleware tests.
- Lock storage operations and replace JSON atomically.
- Add trusted-host middleware, no-store streaming, and security headers.

### Task 5: Dependency Upgrades and Verification

- Upgrade audited backend dependencies.
- Add a patched PostCSS override and regenerate the lockfile.
- Run backend tests, frontend build, Bandit, pip-audit, npm audit, and secret scans.
