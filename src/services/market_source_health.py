# -*- coding: utf-8 -*-
"""In-memory health registry for local market data sources."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Callable, Iterable, Optional


@dataclass
class SourceHealthState:
    source: str
    status: str = "ok"
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    last_latency_ms: Optional[int] = None
    cooling_until: float = 0.0
    updated_at: float = 0.0


class MarketSourceHealthRegistry:
    """Track local source failures and apply a bounded cooldown."""

    def __init__(
        self,
        *,
        failure_threshold: int = 2,
        cooling_seconds: int = 60,
        slow_threshold_ms: int = 3000,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooling_seconds = max(1, int(cooling_seconds))
        self.slow_threshold_ms = max(1, int(slow_threshold_ms))
        self._clock = clock or time.monotonic
        self._states: dict[str, SourceHealthState] = {}
        self._lock = RLock()

    def should_skip(self, source: str) -> bool:
        return self.snapshot(source)["status"] == "cooling_down"

    def snapshot(self, source: str) -> dict[str, object]:
        now = self._clock()
        with self._lock:
            state = self._states.get(source)
            if state is None:
                return self._payload(SourceHealthState(source=source, updated_at=now), now)
            return self._payload(state, now)

    def record_success(self, source: str, *, elapsed_ms: int) -> None:
        now = self._clock()
        status = "slow" if elapsed_ms >= self.slow_threshold_ms else "ok"
        with self._lock:
            self._states[source] = SourceHealthState(
                source=source,
                status=status,
                consecutive_failures=0,
                last_error=None,
                last_latency_ms=max(0, int(elapsed_ms)),
                cooling_until=0.0,
                updated_at=now,
            )

    def record_timeout(self, source: str, *, elapsed_ms: int) -> None:
        self._record_failure(source, error="timeout", elapsed_ms=elapsed_ms)

    def record_error(self, source: str, *, elapsed_ms: int) -> None:
        self._record_failure(source, error="error", elapsed_ms=elapsed_ms)

    def reset(self) -> None:
        with self._lock:
            self._states.clear()

    def reset_sources(self, sources: Iterable[str]) -> list[str]:
        reset: list[str] = []
        seen: set[str] = set()
        with self._lock:
            for source in sources or []:
                normalized = str(source).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                self._states.pop(normalized, None)
                reset.append(normalized)
        return reset

    def _record_failure(self, source: str, *, error: str, elapsed_ms: int) -> None:
        now = self._clock()
        with self._lock:
            previous = self._states.get(source)
            failures = (previous.consecutive_failures if previous else 0) + 1
            cooling_until = now + self.cooling_seconds if failures >= self.failure_threshold else 0.0
            status = "cooling_down" if cooling_until > now else "ok"
            self._states[source] = SourceHealthState(
                source=source,
                status=status,
                consecutive_failures=failures,
                last_error=error,
                last_latency_ms=max(0, int(elapsed_ms)),
                cooling_until=cooling_until,
                updated_at=now,
            )

    def _payload(self, state: SourceHealthState, now: float) -> dict[str, object]:
        status = state.status
        if status == "cooling_down" and state.cooling_until <= now:
            status = "ok"
        remaining = max(0, int(round(state.cooling_until - now))) if status == "cooling_down" else 0
        return {
            "source": state.source,
            "status": status,
            "consecutive_failures": state.consecutive_failures,
            "last_error": state.last_error,
            "last_latency_ms": state.last_latency_ms,
            "cooldown_remaining_sec": remaining,
        }


default_market_source_health = MarketSourceHealthRegistry()
