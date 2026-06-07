from contextlib import suppress
import hashlib
from time import perf_counter
from typing import Any

from app.core.config import settings


def privacy_safe_user_id(session_id: str, secret: str) -> str:
    return hashlib.sha256(f"{secret}:{session_id}".encode("utf-8")).hexdigest()


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": state.get("ticker"),
        "company": state.get("company"),
        "intent": state.get("intent"),
        "timeframe": state.get("timeframe"),
        "entity_count": len(state.get("entities", [])),
        "article_count": len(state.get("articles", [])),
        "comparison_count": len(state.get("comparison_data", [])),
        "error_count": len(state.get("errors", [])),
        "report_used_fallback": state.get("report_used_fallback"),
        "report_model": state.get("report_model"),
    }


class TraceService:
    def __init__(self) -> None:
        self.enabled = bool(settings.langfuse_public_key and settings.langfuse_secret_key)
        self._client = None

        if self.enabled:
            with suppress(Exception):
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host.strip(),
                )

    def start(self, *, name: str, user_id: str, input_data: dict[str, Any]):
        if not self._client:
            return LocalTrace(name=name)

        with suppress(Exception):
            trace = self._client.trace(name=name, user_id=user_id, input=input_data)
            return LangfuseTrace(trace=trace, client=self._client, name=name)

        return LocalTrace(name=name)


class LocalTrace:
    def __init__(self, *, name: str) -> None:
        self.name = name
        self.started_at = perf_counter()

    def span(self, *, name: str, input_data: dict[str, Any] | None = None):
        return LocalSpan(name=name)

    def end(self, *, output: dict[str, Any] | None = None) -> None:
        return None


class LocalSpan:
    def __init__(self, *, name: str) -> None:
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class LangfuseTrace:
    def __init__(self, *, trace, client, name: str) -> None:
        self.trace = trace
        self.client = client
        self.name = name

    def span(self, *, name: str, input_data: dict[str, Any] | None = None):
        return LangfuseSpan(trace=self.trace, name=name, input_data=input_data)

    def end(self, *, output: dict[str, Any] | None = None) -> None:
        with suppress(Exception):
            self.trace.update(output=output)
            self.client.flush()


class LangfuseSpan:
    def __init__(self, *, trace, name: str, input_data: dict[str, Any] | None) -> None:
        self.trace = trace
        self.name = name
        self.input_data = input_data
        self.span = None

    def __enter__(self):
        with suppress(Exception):
            self.span = self.trace.span(name=self.name, input=self.input_data)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        with suppress(Exception):
            if self.span:
                self.span.end(output={"error": str(exc) if exc else None})


trace_service = TraceService()
