import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> RateLimitResult:
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < window_start:
                bucket.popleft()

            if len(bucket) >= self.limit:
                reset_seconds = int(max(1, self.window_seconds - (now - bucket[0])))
                return RateLimitResult(False, self.limit, 0, reset_seconds)

            bucket.append(now)
            remaining = self.limit - len(bucket)
            return RateLimitResult(True, self.limit, remaining, self.window_seconds)


def get_request_client_id(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"
