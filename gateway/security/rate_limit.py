from __future__ import annotations
import time
from dataclasses import dataclass

@dataclass
class TokenBucket:
    rate: float
    burst: int
    tokens: float
    last: float

    def allow(self, cost: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

class RateLimiter:
    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self._buckets: dict[str, TokenBucket] = {}

    def allow(self, principal: str, cost: float = 1.0) -> bool:
        b = self._buckets.get(principal)
        if b is None:
            b = TokenBucket(rate=self.rate, burst=self.burst, tokens=float(self.burst), last=time.monotonic())
            self._buckets[principal] = b
        return b.allow(cost=cost)
