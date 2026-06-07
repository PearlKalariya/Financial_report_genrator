from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.memory.store import PersistentReportStore
from app.schemas.query import QueryRequest
from app.services.rate_limit_service import InMemoryRateLimiter
from app.services.security_service import (
    SessionService,
    is_safe_http_url,
    sanitize_citations,
)
from app.services.trace_service import privacy_safe_user_id, summarize_state


def test_session_service_round_trips_signed_cookie() -> None:
    service = SessionService(secret="test-secret")

    session_id, cookie, created = service.resolve(None)
    resolved_id, resolved_cookie, resolved_created = service.resolve(cookie)

    assert created is True
    assert resolved_id == session_id
    assert resolved_cookie == cookie
    assert resolved_created is False


def test_session_service_rejects_tampered_cookie() -> None:
    service = SessionService(secret="test-secret")
    session_id, cookie, _ = service.resolve(None)

    resolved_id, resolved_cookie, created = service.resolve(cookie + "tampered")

    assert created is True
    assert resolved_id != session_id
    assert resolved_cookie != cookie


def test_query_schema_ignores_client_session_id() -> None:
    request = QueryRequest.model_validate(
        {"query": "Analyze Apple", "session_id": "attacker-controlled"}
    )

    assert not hasattr(request, "session_id")


def test_query_endpoint_sets_http_only_cookie_and_ignores_body_session(
    monkeypatch,
) -> None:
    from app.routes import query as query_route
    from app.schemas.events import StreamEvent

    captured = {}

    async def fake_stream_report(*, query: str, session_id: str):
        captured["query"] = query
        captured["session_id"] = session_id
        yield StreamEvent(type="done", message="Complete")

    monkeypatch.setattr(
        query_route.orchestrator,
        "stream_report",
        fake_stream_report,
    )
    client = TestClient(app)

    response = client.post(
        "/api/query",
        json={"query": "Analyze Apple", "session_id": "attacker-controlled"},
    )

    assert response.status_code == 200
    assert captured["query"] == "Analyze Apple"
    assert captured["session_id"] != "attacker-controlled"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"


def test_history_uses_signed_cookie_instead_of_path_session(tmp_path: Path, monkeypatch) -> None:
    from app.routes import history as history_route

    store = PersistentReportStore(storage_path=tmp_path)
    session_a = "a" * 32
    session_b = "b" * 32
    store.add(
        session_id=session_a,
        query="Apple",
        ticker="AAPL",
        company="Apple",
        report="Private A",
        citations=[],
    )
    store.add(
        session_id=session_b,
        query="Meta",
        ticker="META",
        company="Meta Platforms",
        report="Private B",
        citations=[],
    )
    monkeypatch.setattr(history_route, "report_store", store)
    cookie = history_route.session_service.sign(session_a)

    client = TestClient(app)
    client.cookies.set(history_route.session_service.cookie_name, cookie)
    response = client.get("/api/history")

    assert response.status_code == 200
    assert [item["report"] for item in response.json()["items"]] == ["Private A"]
    assert client.get(f"/api/history/{session_b}").status_code == 404


def test_rate_limiter_allows_five_per_minute_plus_two_burst() -> None:
    now = [100.0]
    limiter = InMemoryRateLimiter(
        requests_per_minute=5,
        burst=2,
        max_concurrent=2,
        clock=lambda: now[0],
    )

    for _ in range(7):
        decision = limiter.acquire("session-a")
        assert decision.allowed is True
        limiter.release("session-a")

    rejected = limiter.acquire("session-a")

    assert rejected.allowed is False
    assert rejected.retry_after_seconds > 0


def test_rate_limiter_rejects_third_concurrent_report() -> None:
    limiter = InMemoryRateLimiter(
        requests_per_minute=5,
        burst=2,
        max_concurrent=2,
    )

    assert limiter.acquire("session-a").allowed is True
    assert limiter.acquire("session-a").allowed is True
    decision = limiter.acquire("session-a")

    assert decision.allowed is False
    assert decision.reason == "concurrency"


def test_citations_allow_only_http_and_https() -> None:
    citations = sanitize_citations(
        [
            {"title": "Good", "url": "https://example.com"},
            {"title": "Also good", "url": "http://example.com"},
            {"title": "Bad", "url": "javascript:alert(1)"},
            {"title": "Local file", "url": "file:///etc/passwd"},
        ]
    )

    assert [citation["title"] for citation in citations] == ["Good", "Also good"]
    assert is_safe_http_url("javascript:alert(1)") is False


def test_trace_summary_excludes_sensitive_content() -> None:
    state = {
        "query": "secret query",
        "session_id": "raw-session",
        "ticker": "AAPL",
        "company": "Apple",
        "intent": "outlook",
        "articles": [{"snippet": "untrusted source text"}],
        "memory_context": [{"query": "old private query"}],
        "report": "private report",
        "financial_evidence": {"facts": [{"value": "100"}]},
        "entities": [{"ticker": "AAPL"}],
        "errors": [],
    }

    summary = summarize_state(state)
    serialized = str(summary)

    assert summary["ticker"] == "AAPL"
    assert summary["article_count"] == 1
    assert "secret query" not in serialized
    assert "raw-session" not in serialized
    assert "private report" not in serialized
    assert privacy_safe_user_id("raw-session", "trace-secret") != "raw-session"


def test_store_handles_concurrent_writes_without_losing_records(tmp_path: Path) -> None:
    store = PersistentReportStore(storage_path=tmp_path)

    def add_record(index: int) -> None:
        store.add(
            session_id="session-a",
            query=f"Query {index}",
            ticker="AAPL",
            company="Apple",
            report=f"Report {index}",
            citations=[],
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(add_record, range(20)))

    assert len(store.list_by_session("session-a")) == 20


def test_api_returns_security_headers_and_rejects_untrusted_host() -> None:
    client = TestClient(app)

    response = client.get("/api/health")
    untrusted = client.get(
        "/api/health",
        headers={"host": "attacker.example"},
    )

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert untrusted.status_code == 400
