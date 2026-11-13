"""Per-client sliding-window rate limiter. In-memory: fine for a single-instance demo."""

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from datetime import time as dt_time

WINDOW_SECONDS = 60.0


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window_s: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._limit = limit
        self._window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self._window_s:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True


class DailyLimiter:
    """Global per-UTC-day admission counter (cost guard for a public demo).

    In memory: a process restart resets the count, and multiple instances would each have
    their own. The OpenAI-side monthly key limit is the real backstop; this only bounds the
    expected daily spend.
    """

    def __init__(self, limit: int, clock: Callable[[], datetime] | None = None):
        self._limit = limit
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._day = self._clock().date()
        self._count = 0

    def allow(self) -> bool:
        """Count one admission; False once the day's budget is spent."""
        with self._lock:
            now = self._clock()
            if now.date() != self._day:
                self._day, self._count = now.date(), 0
            if self._count >= self._limit:
                return False
            self._count += 1
            return True

    def seconds_until_reset(self) -> int:
        """Whole seconds (at least 1) until the next UTC midnight."""
        now = self._clock()
        midnight = datetime.combine(now.date() + timedelta(days=1), dt_time.min, tzinfo=UTC)
        return max(1, math.ceil((midnight - now).total_seconds()))
