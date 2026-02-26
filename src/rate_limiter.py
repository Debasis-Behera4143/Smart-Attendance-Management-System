"""Simple in-memory fixed-window rate limiter for Flask APIs."""

from collections import defaultdict, deque
from threading import Lock
from time import time
from typing import Deque, Dict, Tuple


class RateLimiter:
    """Thread-safe rate limiter keyed by client identifier."""

    def __init__(self, window_seconds: int, max_requests: int):
        self.window_seconds = max(1, int(window_seconds))
        self.max_requests = max(1, int(max_requests))
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> Tuple[bool, int]:
        now = time()

        with self._lock:
            bucket = self._requests[key]
            self._evict_old(bucket, now)

            if len(bucket) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - bucket[0])) + 1
                return False, max(1, retry_after)

            bucket.append(now)
            return True, 0

    def _evict_old(self, bucket: Deque[float], now: float):
        cutoff = now - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
