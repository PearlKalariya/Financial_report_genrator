import math
import threading
import time
from dataclasses import dataclass
from typing import Callable

from app.core.config import settings


@dataclass
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0
    reason: str | None = None


@dataclass
class _Bucket:
    tokens: float
    updated_at: float
    active: int = 0


class InMemoryRateLimiter:
    def __init__(
        self,
        *,
        requests_per_minute: int,
        burst: int,
        max_concurrent: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.refill_rate = requests_per_minute / 60
        self.capacity = requests_per_minute + burst
        self.max_concurrent = max_concurrent
        self.clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()
        self._last_cleanup = self.clock()

    def acquire(self, session_id: str) -> RateLimitDecision:
        with self._lock:
            now = self.clock()
            self._cleanup_stale_buckets(now)
            bucket = self._buckets.setdefault(
                session_id,
                _Bucket(tokens=float(self.capacity), updated_at=now),
            )
            elapsed = max(0, now - bucket.updated_at)
            bucket.tokens = min(
                float(self.capacity),
                bucket.tokens + elapsed * self.refill_rate,
            )
            bucket.updated_at = now

            if bucket.active >= self.max_concurrent:
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=1,
                    reason="concurrency",
                )
            if bucket.tokens < 1:
                retry_after = math.ceil((1 - bucket.tokens) / self.refill_rate)
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=max(1, retry_after),
                    reason="rate",
                )

            bucket.tokens -= 1
            bucket.active += 1
            return RateLimitDecision(allowed=True)

    def release(self, session_id: str) -> None:
        with self._lock:
            bucket = self._buckets.get(session_id)
            if bucket:
                bucket.active = max(0, bucket.active - 1)

    def _cleanup_stale_buckets(self, now: float) -> None:
        if now - self._last_cleanup < 300:
            return
        stale_before = now - 3600
        self._buckets = {
            key: bucket
            for key, bucket in self._buckets.items()
            if bucket.active > 0 or bucket.updated_at >= stale_before
        }
        self._last_cleanup = now


report_rate_limiter = InMemoryRateLimiter(
    requests_per_minute=settings.report_requests_per_minute,
    burst=settings.report_request_burst,
    max_concurrent=settings.max_concurrent_reports_per_session,
)

report_ip_rate_limiter = InMemoryRateLimiter(
    requests_per_minute=settings.report_requests_per_ip_minute,
    burst=settings.report_request_ip_burst,
    max_concurrent=settings.max_concurrent_reports_per_ip,
)
