from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, per_minute: int = 30, cooldown_seconds: float = 2.0):
        self.per_minute = max(1, per_minute)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._last_success: dict[str, float] = {}

    def allow_request(self, key: str) -> tuple[bool, str]:
        now = time.time()
        events = self._events[key]
        while events and events[0] < now - 60:
            events.popleft()
        if len(events) >= self.per_minute:
            return False, "Too many DexTilt requests arrived in a short time. Wait a moment and try again."
        events.append(now)
        return True, "ok"

    def allow_success(self, key: str) -> tuple[bool, str]:
        if self.cooldown_seconds <= 0:
            return True, "ok"
        now = time.time()
        last = self._last_success.get(key)
        if last is not None and (now - last) < self.cooldown_seconds:
            return False, "DexTilt is cooling down after the last command. Try again in a moment."
        self._last_success[key] = now
        return True, "ok"
