import httpx

from app.core.config import settings


# text-embedding-004 returns 768-dimensional vectors.
GEMINI_EMBEDDING_DIMENSIONS = 768


class EmbeddingService:
    """Wraps the Gemini text-embedding endpoint.

    Returns ``None`` on any failure so callers can fall back to a local
    deterministic embedding without breaking memory retrieval.
    """

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.google_api_key
        self.model = model or settings.embedding_model

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def embed(self, text: str) -> list[float] | None:
        if not self.api_key or not text or not text.strip():
            return None

        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model}:embedContent"
        )
        try:
            with httpx.Client(timeout=15) as client:
                response = client.post(
                    url,
                    headers={
                        "x-goog-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": f"models/{self.model}",
                        "content": {"parts": [{"text": text}]},
                    },
                )
                response.raise_for_status()
            values = response.json().get("embedding", {}).get("values")
        except (httpx.HTTPError, ValueError, KeyError):
            return None

        if isinstance(values, list) and values:
            return [float(value) for value in values]
        return None


embedding_service = EmbeddingService()
