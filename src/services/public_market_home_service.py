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
from src.services.public_market_event_service import PublicMarketEventService
from src.services.public_market_session_service import (
    PublicMarketSessionService,
    unknown_market_session,
)


MARKETS = ("cn", "hk", "us")
_HOME_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="public-market-home")


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
        ranking_loader: Optional[Callable[[str], Dict[str, Any]]] = None,
        session_resolver: Optional[Callable[[str, str], Dict[str, Any]]] = None,
        event_builder: Optional[Callable[[list[Dict[str, Any]], str], list[Dict[str, Any]]]] = None,
    ) -> None:
        self.workspace_service = workspace_service or MarketWorkspaceService()
        raw_timeout = timeout_seconds if timeout_seconds is not None else os.getenv("PLATFORM_PUBLIC_MARKET_HOME_TIMEOUT_SECONDS", "5.5")
        self.timeout_seconds = max(0.05, min(float(raw_timeout), 10.0))
        self.cache_ttl_seconds = max(1, int(cache_ttl_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_HOME_CACHE_TTL_SECONDS", "60")))
        self.max_items_per_market = max(1, min(int(max_items_per_market or os.getenv("PLATFORM_PUBLIC_MARKET_HOME_MAX_ITEMS_PER_MARKET", "6")), 20))
        self.clock = clock
        self.executor = executor or _HOME_EXECUTOR
        self.ranking_loader = ranking_loader
        self.session_resolver = session_resolver or PublicMarketSessionService().resolve
        self.event_builder = event_builder or PublicMarketEventService().build
        self._cache: Optional[tuple[float, Dict[str, Any]]] = None
        self._lock = Lock()

    def build(self) -> Dict[str, Any]:
        cached = self._read_cache()
        if cached is not None:
            return cached
        as_of = self.clock()
        sessions = {market: self._resolve_session(market, as_of) for market in MARKETS}
        futures = {market: self.executor.submit(self.workspace_service.get_overview, market) for market in MARKETS}
        ranking_futures = {
            market: self.executor.submit(self.ranking_loader, market)
            for market in MARKETS
        } if self.ranking_loader is not None else {}
        completed, pending = wait([*futures.values(), *ranking_futures.values()], timeout=self.timeout_seconds)
        for future in pending:
            future.cancel()
        sections = []
        for market in MARKETS:
            future = futures[market]
            overview = None if future not in completed or future.exception() is not None else future.result()
            if self.ranking_loader is None:
                if overview is None:
                    sections.append(self._unavailable_section(market, sessions[market]))
                else:
                    sections.append(self._section(market, overview, sessions[market]))
                continue
            ranking_future = ranking_futures[market]
            rankings = None if ranking_future not in completed or ranking_future.exception() is not None else ranking_future.result()
            if overview is None and rankings is None:
                sections.append(self._unavailable_section(market, sessions[market]))
            else:
                sections.append(self._dynamic_section(market, overview or {}, rankings, sessions[market]))
        try:
            events = list(self.event_builder(sections, as_of) or [])
        except Exception:
            events = []
            for section in sections:
                section["warnings"] = list(dict.fromkeys([
                    *(section.get("warnings") or []),
                    "market_events_unavailable",
                ]))
        payload = {
            "as_of": as_of,
            "markets": sections,
            "events": events,
            "ai_used": False,
            "informational_only": True,
        }
        cacheable = self.ranking_loader is None or all(
            section.get("ranking_scope") == "market_wide" for section in sections
        )
        if cacheable:
            with self._lock:
                self._cache = (time.monotonic(), copy.deepcopy(payload))
        return payload

    def _read_cache(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._cache
        if entry is None or time.monotonic() - entry[0] >= self.cache_ttl_seconds:
            return None
        return copy.deepcopy(entry[1])

    def _section(self, market: str, overview: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
        items = [dict(item) for item in overview.get("movers") or [] if isinstance(item, dict)]
        items.sort(key=self._attention_key)
        return {
            "market": market,
            **session,
            "display_mode": self._display_mode(),
            "ranking_scope": "configured_universe",
            "selection_basis": "turnover_then_absolute_change",
            "indices": list(overview.get("indices") or []),
            "attention": items[: self.max_items_per_market],
            "headlines": list(overview.get("headlines") or [])[:10],
            "sources": list(overview.get("sources") or []),
            "warnings": list(dict.fromkeys([*(overview.get("warnings") or []), *session.get("session_warning_codes", [])])),
        }

    def _unavailable_section(self, market: str, session: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "market": market,
            **session,
            "display_mode": self._display_mode(),
            "ranking_scope": "unavailable" if self.ranking_loader is not None else "configured_universe",
            "selection_basis": "turnover_then_absolute_change",
            "indices": [], "attention": [], "most_active": [], "gainers": [], "losers": [],
            "sector_highlights": [], "ranking_cache": {"hit": False, "age_seconds": 0, "ttl_seconds": 120},
            "headlines": [], "sources": [],
            "warnings": list(dict.fromkeys(["market_home_unavailable", *session.get("session_warning_codes", [])])),
        }

    def _dynamic_section(self, market: str, overview: Dict[str, Any], rankings: Optional[Dict[str, Any]], session: Dict[str, Any]) -> Dict[str, Any]:
        ranking = rankings or {}
        most_active = list(ranking.get("most_active") or [])[: self.max_items_per_market]
        gainers = list(ranking.get("gainers") or [])[: self.max_items_per_market]
        losers = list(ranking.get("losers") or [])[: self.max_items_per_market]
        has_market_rankings = bool(most_active or gainers or losers)
        warnings = [
            warning for warning in (overview.get("warnings") or [])
            if warning != "market_quotes_unavailable"
        ]
        if not overview:
            warnings.append("market_context_unavailable")
        warnings.extend(ranking.get("warnings") or [])
        if rankings is None:
            warnings.append("market_rankings_unavailable")
        warnings.extend(session.get("session_warning_codes", []))
        return {
            "market": market,
            **session,
            "display_mode": self._display_mode(),
            "ranking_scope": "market_wide" if has_market_rankings else "unavailable",
            "selection_basis": "market_wide_public_rankings_with_liquidity_filter",
            "indices": list(overview.get("indices") or []),
            "attention": most_active,
            "most_active": most_active,
            "gainers": gainers,
            "losers": losers,
            "sector_highlights": list(ranking.get("sector_highlights") or [])[: self.max_items_per_market],
            "ranking_cache": dict(ranking.get("cache") or {"hit": False, "age_seconds": 0, "ttl_seconds": 120}),
            "headlines": list(overview.get("headlines") or [])[:10],
            "sources": [
                *[
                    state for state in (overview.get("sources") or [])
                    if not str(state.get("source") if isinstance(state, dict) else "").endswith("_market_snapshot")
                ],
                *list(ranking.get("sources") or []),
            ],
            "warnings": list(dict.fromkeys(warnings)),
        }

    def _resolve_session(self, market: str, as_of: str) -> Dict[str, Any]:
        try:
            payload = dict(self.session_resolver(market, as_of) or {})
        except Exception:
            return unknown_market_session("calendar_error")
        if payload.get("session_phase") not in {
            "premarket", "intraday", "lunch_break", "closing_auction",
            "postmarket", "non_trading", "unknown",
        }:
            return unknown_market_session("calendar_error")
        return payload

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
