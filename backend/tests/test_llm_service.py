import asyncio
from unittest.mock import AsyncMock

from app.services.llm_service import GeminiReportService


def test_gemini_service_tries_fallback_model_when_primary_fails() -> None:
    service = GeminiReportService(api_key="fake-key", model="bad-model")
    service._generate_with_model = AsyncMock(side_effect=[("", "quota exceeded"), ("Generated report", None)])

    result = asyncio.run(service.generate_report(fallback_report="Fallback report", state={"query": "test"}))

    assert result.report == "Generated report"
    assert result.used_fallback is False
    assert result.model == "gemini-2.5-flash"


def test_gemini_service_includes_reason_when_all_models_fail() -> None:
    service = GeminiReportService(api_key="fake-key", model="bad-model")
    service._generate_with_model = AsyncMock(return_value=("", "quota exceeded"))

    result = asyncio.run(service.generate_report(fallback_report="Fallback report", state={"query": "test"}))

    assert result.used_fallback is True
    assert "## Generation Notice" in result.report
    assert "quota exceeded" in result.report

