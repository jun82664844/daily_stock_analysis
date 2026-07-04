# -*- coding: utf-8 -*-
"""Small in-memory cache for local V1 market data lookups."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class CacheHit:
    value: Any
    source: str
    freshness: str
    age_seconds: float
    origin: str = "memory"


class MarketDataCache:
    def __init__(self, *, default_ttl_seconds: int = 30):
        self.default_ttl_seconds = max(0, int(default_ttl_seconds))
        self._items: dict[str, tuple[Any, str, float, int]] = {}
        self._lock = RLock()

    def set(self, key: str, value: Any, *, source: str, ttl_seconds: int | None = None) -> None:
        ttl = self.default_ttl_seconds if ttl_seconds is None else max(0, int(ttl_seconds))
        with self._lock:
            self._items[key] = (value, source, time.time(), ttl)

    def get(self, key: str) -> CacheHit | None:
        with self._lock:
            item = self._items.get(key)
        if item is None:
            return None
        value, source, created_at, ttl = item
        age = time.time() - created_at
        freshness = "cached" if age <= ttl else "stale"
        return CacheHit(value=value, source=source, freshness=freshness, age_seconds=age, origin="memory")


default_market_data_cache = MarketDataCache(default_ttl_seconds=30)
