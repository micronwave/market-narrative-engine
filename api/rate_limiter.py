import functools
import inspect
import threading
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException


@dataclass
class TokenBucket:
    capacity: float
    refill_rate: float  # tokens per second
    tokens: float
    last_refill: float

    @classmethod
    def create(cls, capacity: float, refill_rate: float) -> "TokenBucket":
        now = time.time()
        return cls(
            capacity=capacity,
            refill_rate=refill_rate,
            tokens=capacity,
            last_refill=now,
        )

    def allow(self) -> bool:
        now = time.time()
        elapsed = max(0.0, now - self.last_refill)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, TokenBucket] = {}

    def allow(self, key: str, requests_per_minute: int) -> bool:
        rpm = max(1, int(requests_per_minute))
        capacity = float(rpm)
        refill_rate = capacity / 60.0
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket.create(capacity=capacity, refill_rate=refill_rate)
                self._buckets[key] = bucket
            else:
                bucket.capacity = capacity
                bucket.refill_rate = refill_rate
            return bucket.allow()


def make_require_rate_limit(
    limiter: InMemoryRateLimiter,
    enabled_getter: Callable[[], bool],
    rpm_getter: Callable[[], int],
) -> Callable[[str], Callable]:
    def require_rate_limit(bucket_name: str) -> Callable:
        def decorator(func):
            if inspect.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    if enabled_getter():
                        user = kwargs.get("user") or {}
                        user_id = str(user.get("user_id") or "stub_user")
                        key = f"{bucket_name}:{user_id}"
                        if not limiter.allow(key, rpm_getter()):
                            raise HTTPException(status_code=429, detail="Rate limit exceeded")
                    return await func(*args, **kwargs)
                async_wrapper.__signature__ = inspect.signature(func)
                return async_wrapper

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                if enabled_getter():
                    user = kwargs.get("user") or {}
                    user_id = str(user.get("user_id") or "stub_user")
                    key = f"{bucket_name}:{user_id}"
                    if not limiter.allow(key, rpm_getter()):
                        raise HTTPException(status_code=429, detail="Rate limit exceeded")
                return func(*args, **kwargs)
            sync_wrapper.__signature__ = inspect.signature(func)
            return sync_wrapper

        return decorator

    return require_rate_limit
