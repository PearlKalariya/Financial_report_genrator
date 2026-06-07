import hashlib
import hmac
import re
import secrets
from urllib.parse import urlparse

from app.core.config import settings


_EPHEMERAL_SESSION_SECRET = secrets.token_urlsafe(48)
_SESSION_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


class SessionService:
    def __init__(
        self,
        *,
        secret: str | None = None,
        cookie_name: str = "financial_session",
    ) -> None:
        self.secret = (
            secret
            if secret is not None
            else settings.session_secret or _EPHEMERAL_SESSION_SECRET
        ).encode("utf-8")
        self.cookie_name = cookie_name

    def sign(self, session_id: str) -> str:
        signature = hmac.new(
            self.secret,
            session_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{session_id}.{signature}"

    def resolve(self, cookie_value: str | None) -> tuple[str, str, bool]:
        session_id = self._verify(cookie_value)
        if session_id:
            return session_id, cookie_value or self.sign(session_id), False

        session_id = secrets.token_hex(16)
        return session_id, self.sign(session_id), True

    def cookie_options(self) -> dict:
        return {
            "httponly": True,
            "secure": settings.session_cookie_secure,
            "samesite": settings.session_cookie_samesite,
            "max_age": settings.session_cookie_max_age,
            "path": "/",
        }

    def _verify(self, cookie_value: str | None) -> str | None:
        if not cookie_value or "." not in cookie_value:
            return None
        session_id, signature = cookie_value.rsplit(".", 1)
        if not _SESSION_ID_PATTERN.fullmatch(session_id):
            return None
        expected = self.sign(session_id).rsplit(".", 1)[1]
        if not hmac.compare_digest(signature, expected):
            return None
        return session_id


def is_safe_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def sanitize_citations(citations: list[dict]) -> list[dict]:
    return [
        citation
        for citation in citations
        if is_safe_http_url(citation.get("url"))
    ]


session_service = SessionService()
