# -*- coding: utf-8 -*-
"""Public, no-AI three-market home aggregation for V116."""

from __future__ import annotations

import copy
import os
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, Optional

from src.services.market_workspace_service import MarketWorkspaceService


MARKETS = ("cn", "hk", "us")
_HOME_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="public-market-home")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PublicMarketHomeService:
    def __init__(
        self,
        workspace_service: Optional[MarketWorkspaceService] = None,
        *,
        timeout_seconds: Optional[float] = None,
        cache_ttl_seconds: Optional[int] = None,
        max_items_per_market: Optional[int] = None,
        clock: Callable[[], str] = _utc_now,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        self.workspace_service = workspace_service or MarketWorkspaceService()
        raw_timeout = timeout_seconds if timeout_seconds is not None else os.getenv("PLATFORM_PUBLIC_MARKET_HOME_TIMEOUT_SECONDS", "3.5")
        self.timeout_seconds = max(0.05, min(float(raw_timeout), 10.0))
        self.cache_ttl_seconds = max(1, int(cache_ttl_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_HOME_CACHE_TTL_SECONDS", "60")))
        self.max_items_per_market = max(1, min(int(max_items_per_market or os.getenv("PLATFORM_PUBLIC_MARKET_HOME_MAX_ITEMS_PER_MARKET", "6")), 20))
        self.clock = clock
        self.executor = executor or _HOME_EXECUTOR
        self._cache: Optional[tuple[float, Dict[str, Any]]] = None
        self._lock = Lock()

    def build(self) -> Dict[str, Any]:
        cached = self._read_cache()
        if cached is not None:
            return cached
        futures = {market: self.executor.submit(self.workspace_service.get_overview, market) for market in MARKETS}
        completed, pending = wait(futures.values(), timeout=self.timeout_seconds)
        for future in pending:
            future.cancel()
        sections = []
        for market in MARKETS:
            future = futures[market]
            if future not in completed or future.exception() is not None:
                sections.append(self._unavailable_section(market))
            else:
                sections.append(self._section(market, future.result()))
        payload = {
            "as_of": self.clock(),
            "markets": sections,
            "ai_used": False,
            "informational_only": True,
        }
        with self._lock:
            self._cache = (time.monotonic(), copy.deepcopy(payload))
        return payload

    def _read_cache(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._cache
        if entry is None or time.monotonic() - entry[0] >= self.cache_ttl_seconds:
            return None
        return copy.deepcopy(entry[1])

    def _section(self, market: str, overview: Dict[str, Any]) -> Dict[str, Any]:
        items = [dict(item) for item in overview.get("movers") or [] if isinstance(item, dict)]
        items.sort(key=self._attention_key)
        return {
            "market": market,
            "session_state": overview.get("session_state") if overview.get("session_state") in {"open", "closed", "unknown"} else "unknown",
            "display_mode": self._display_mode(),
            "ranking_scope": "configured_universe",
            "selection_basis": "turnover_then_absolute_change",
            "indices": list(overview.get("indices") or []),
            "attention": items[: self.max_items_per_market],
            "headlines": list(overview.get("headlines") or [])[:10],
            "sources": list(overview.get("sources") or []),
            "warnings": list(dict.fromkeys(overview.get("warnings") or [])),
        }

    def _unavailable_section(self, market: str) -> Dict[str, Any]:
        return {
            "market": market,
            "session_state": "unknown",
            "display_mode": self._display_mode(),
            "ranking_scope": "configured_universe",
            "selection_basis": "turnover_then_absolute_change",
            "indices": [], "attention": [], "headlines": [], "sources": [],
            "warnings": ["market_home_unavailable"],
        }

    @staticmethod
    def _attention_key(item: Dict[str, Any]) -> tuple[Any, ...]:
        turnover = PublicMarketHomeService._number(item.get("turnover"))
        change = PublicMarketHomeService._number(item.get("change_percent"))
        return (turnover is None, -(turnover or 0), change is None, -abs(change or 0), str(item.get("symbol") or ""))

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _display_mode() -> str:
        requested = os.getenv("PLATFORM_MARKET_DATA_DISPLAY_MODE", "latest_available").strip().lower()
        if requested == "delayed":
            return "delayed"
        if requested == "realtime" and os.getenv("DSA_MARKET_DATA_LICENSE_APPROVED", "false").strip().lower() in {"1", "true", "yes", "on"}:
            return "realtime"
        return "latest_available"
