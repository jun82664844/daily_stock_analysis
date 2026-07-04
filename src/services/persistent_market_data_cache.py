# -*- coding: utf-8 -*-
"""JSON-backed local market data cache for quick/no-AI queries."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from src.services.market_data_cache import CacheHit, MarketDataCache


class PersistentMarketDataCache(MarketDataCache):
    """Small write-through cache that survives local WebUI restarts."""

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        default_ttl_seconds: int = 30,
        max_entries: int = 256,
    ) -> None:
        super().__init__(default_ttl_seconds=default_ttl_seconds)
        self.path = Path(path or os.getenv("MARKET_DATA_CACHE_PATH", "local/market_data_cache.json"))
        self.max_entries = max(1, int(max_entries))
        self._origins: dict[str, str] = {}
        self._load_from_disk()

    @property
    def persistent_mode(self) -> str:
        return "local_json"

    @property
    def storage_label(self) -> str:
        return "local_market_cache"

    def set(self, key: str, value: Any, *, source: str, ttl_seconds: int | None = None) -> None:
        if not self._is_json_safe(value):
            return
        ttl = self.default_ttl_seconds if ttl_seconds is None else max(0, int(ttl_seconds))
        created_at = time.time()
        with self._lock:
            self._items[key] = (value, source, created_at, ttl)
            self._origins[key] = "memory"
            self._trim_locked()
            self._write_to_disk_locked()

    def get(self, key: str) -> CacheHit | None:
        with self._lock:
            item = self._items.get(key)
            origin = self._origins.get(key, "memory")
        if item is None:
            return None
        value, source, created_at, ttl = item
        age = time.time() - created_at
        freshness = "cached" if age <= ttl else "stale"
        return CacheHit(value=value, source=source, freshness=freshness, age_seconds=age, origin=origin)

    def _load_from_disk(self) -> None:
        try:
            if not self.path.exists():
                return
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            items = payload.get("items") if isinstance(payload, dict) else None
            if not isinstance(items, dict):
                return
        except Exception:
            return
        with self._lock:
            for key, item in items.items():
                if not isinstance(key, str) or not isinstance(item, dict):
                    continue
                value = item.get("value")
                source = str(item.get("source") or "unknown")
                created_at = self._float_or_default(item.get("created_at"), time.time())
                ttl = max(0, int(self._float_or_default(item.get("ttl"), self.default_ttl_seconds)))
                self._items[key] = (value, source, created_at, ttl)
                self._origins[key] = "disk"
            self._trim_locked()

    def _write_to_disk_locked(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            items = {
                key: {
                    "value": value,
                    "source": source,
                    "created_at": created_at,
                    "ttl": ttl,
                }
                for key, (value, source, created_at, ttl) in self._items.items()
            }
            temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            temp_path.write_text(
                json.dumps({"version": 1, "items": items}, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            temp_path.replace(self.path)
        except Exception:
            return

    def _trim_locked(self) -> None:
        if len(self._items) <= self.max_entries:
            return
        ordered = sorted(self._items.items(), key=lambda item: item[1][2])
        for key, _ in ordered[: len(self._items) - self.max_entries]:
            self._items.pop(key, None)
            self._origins.pop(key, None)

    def _is_json_safe(self, value: Any) -> bool:
        try:
            json.dumps(value, ensure_ascii=False)
            return True
        except (TypeError, ValueError):
            return False

    def _float_or_default(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


default_persistent_market_data_cache = PersistentMarketDataCache(
    default_ttl_seconds=max(0, int(os.getenv("MARKET_DATA_CACHE_TTL_SECONDS", "300")))
)
