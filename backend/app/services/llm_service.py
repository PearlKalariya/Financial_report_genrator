import httpx

from app.core.config import settings


class GeminiReportResult:
    def __init__(
        self,
        *,
        report: str,
        used_fallback: bool,
        model: str,
        error: str | None = None,
    ) -> None:
        self.report = report
        self.used_fallback = used_fallback
        self.model = model
        self.error = error


class GeminiReportService:
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.google_api_key
        self.model = model or settings.gemini_model

    async def generate_report(self, *, fallback_report: str, state: dict) -> GeminiReportResult:
        if not self.api_key:
            return GeminiReportResult(
                report=self._fallback_with_reason(fallback_report, "Gemini API key is not configured."),
                used_fallback=True,
                model=self.model,
                error="Gemini API key is not configured.",
            )

        prompt = self._build_prompt(state)
        last_error = None
        for model in self._candidate_models():
            result, error = await self._generate_with_model(model=model, prompt=prompt)
            if result:
                return GeminiReportResult(report=result, used_fallback=False, model=model)
            last_error = error

        reason = last_error or "Gemini returned an empty response."
        return GeminiReportResult(
            report=self._fallback_with_reason(fallback_report, reason),
            used_fallback=True,
            model=self.model,
            error=reason,
        )

    async def _generate_with_model(self, *, model: str, prompt: str) -> tuple[str, str | None]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1800},
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return "", self._summarize_http_error(exc)
        except httpx.HTTPError as exc:
            return "", f"Gemini request failed: {exc.__class__.__name__}"

        text = self._extract_text(response.json())
        return text, None if text else "Gemini returned no text."

    def _build_prompt(self, state: dict) -> str:
        return f"""
Create a concise, citation-aware market insight report in markdown.

Rules:
- Do not invent financial numbers.
- Use only the supplied market_data for metrics.
- Use the supplied articles as citation sources.
- Include sections: Executive Summary, Price Action, Key Market Metrics, News Analysis, Sentiment, Key Risks, Outlook, Sources, Disclaimer.
- Include this disclaimer exactly: This report is for informational and educational purposes only. It is not financial advice, investment advice, or a recommendation to buy, sell, or hold any security.

Query: {state.get("query")}
Company: {state.get("company")}
Ticker: {state.get("ticker")}
Intent: {state.get("intent")}
Timeframe: {state.get("timeframe")}
Market data: {state.get("market_data")}
Sentiment: {state.get("sentiment")}
Articles: {state.get("articles")}
Memory context: {state.get("memory_context")}
"""

    def _extract_text(self, payload: dict) -> str:
        try:
            candidates = payload.get("candidates", [])
            parts = candidates[0].get("content", {}).get("parts", [])
        except (IndexError, AttributeError):
            return ""

        return "\n".join(part.get("text", "") for part in parts).strip()

    def _candidate_models(self) -> list[str]:
        candidates = [self.model, "gemini-2.5-flash", "gemini-2.0-flash"]
        deduped: list[str] = []
        for model in candidates:
            if model and model not in deduped:
                deduped.append(model)
        return deduped

    def _summarize_http_error(self, exc: httpx.HTTPStatusError) -> str:
        status_code = exc.response.status_code
        try:
            payload = exc.response.json()
            message = payload.get("error", {}).get("message", exc.response.text)
        except ValueError:
            message = exc.response.text

        compact_message = " ".join(message.split())
        return f"Gemini HTTP {status_code}: {compact_message[:500]}"

    def _fallback_with_reason(self, fallback_report: str, reason: str) -> str:
        return (
            f"{fallback_report}\n\n"
            "## Generation Notice\n"
            "The LLM-generated report was unavailable, so this structured fallback report was used.\n\n"
            f"Reason: {reason}\n"
        )


gemini_report_service = GeminiReportService()
