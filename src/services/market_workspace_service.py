# -*- coding: utf-8 -*-
"""Cached, degradable multi-market aggregation for V113."""

from __future__ import annotations

import copy
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from src.services.a_share_enrichment_service import AShareEnrichmentService
from src.services.basic_query_service import BasicQueryService
from src.services.public_market_session_service import (
    PublicMarketSessionService,
    unknown_market_session,
)
from src.platform_watchlist import PlatformWatchlistService


SnapshotLoader = Callable[[str], Dict[str, Any]]
NewsLoader = Callable[[str], List[Dict[str, Any]]]
IndexLoader = Callable[[str], List[Dict[str, Any]]]

_DEFAULT_MARKET_SYMBOLS: Mapping[str, Sequence[str]] = {
    "cn": ("601318.SH", "600519.SH", "000001.SZ", "300750.SZ"),
    "hk": ("0700.HK", "9988.HK", "3690.HK", "1299.HK"),
    "us": ("AAPL", "MSFT", "NVDA", "AMZN", "TSLA"),
}


def _configured_market_symbols() -> Mapping[str, Sequence[str]]:
    result: Dict[str, Sequence[str]] = {}
    for market, defaults in _DEFAULT_MARKET_SYMBOLS.items():
        raw = os.getenv(f"PLATFORM_PUBLIC_MARKET_HOME_SYMBOLS_{market.upper()}", "")
        values = []
        seen = set()
        for item in raw.split(",") if raw.strip() else defaults:
            symbol = str(item).strip().upper()
            if not symbol or len(symbol) > 32 or not re.fullmatch(r"[A-Z0-9.-]+", symbol) or symbol in seen:
                continue
            seen.add(symbol)
            values.append(symbol)
            if len(values) >= 20:
                break
        result[market] = tuple(values or defaults)
    return result

_MARKET_OVERVIEW_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(4, int(os.getenv("PLATFORM_MARKET_WORKSPACE_MAX_WORKERS", "8"))),
    thread_name_prefix="market-workspace",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MarketWorkspaceService:
    _MARKET_CURRENCIES = {"cn": "CNY", "hk": "HKD", "us": "USD"}

    def __init__(
        self,
        snapshot_loader: Optional[SnapshotLoader] = None,
        detail_loader: Optional[SnapshotLoader] = None,
        news_loader: Optional[NewsLoader] = None,
        index_loader: Optional[IndexLoader] = None,
        market_symbols: Optional[Mapping[str, Sequence[str]]] = None,
        cache_ttl_seconds: Optional[int] = None,
        overview_timeout_seconds: Optional[float] = None,
        session_resolver: Optional[Callable[[str, str], Dict[str, Any]]] = None,
    ) -> None:
        if snapshot_loader is None:
            query_service = BasicQueryService(
                a_share_enrichment_service=AShareEnrichmentService(source_mode="off"),
                fetch_timeout_seconds=2.0,
                profile_timeout_seconds=0.8,
                reference_quote_timeout_seconds=0.4,
                stale_revalidation_timeout_seconds=0.3,
            )
            self.snapshot_loader = query_service.get_quote_card
            self.detail_loader = detail_loader or query_service.get_snapshot
        else:
            self.snapshot_loader = snapshot_loader
            self.detail_loader = detail_loader or snapshot_loader
        self.news_loader = news_loader
        self.index_loader = index_loader
        self.market_symbols = {key: tuple(value) for key, value in (market_symbols or _configured_market_symbols()).items()}
        self.cache_ttl_seconds = max(
            1,
            int(cache_ttl_seconds or os.getenv("PLATFORM_MARKET_WORKSPACE_CACHE_TTL_SECONDS", "60")),
        )
        self.overview_timeout_seconds = max(
            0.05,
            float(
                overview_timeout_seconds
                if overview_timeout_seconds is not None
                else os.getenv("PLATFORM_MARKET_WORKSPACE_OVERVIEW_TIMEOUT_SECONDS", "2.5")
            ),
        )
        self.session_resolver = session_resolver or PublicMarketSessionService().resolve
        self._cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._lock = Lock()

    def get_overview(self, market: str) -> Dict[str, Any]:
        normalized_market = self._normalize_market(market)
        cached = self._read_cache(normalized_market)
        if cached is not None:
            return cached

        fetched_at = _utc_now()
        items: List[Dict[str, Any]] = []
        warnings: List[str] = []
        symbols = tuple(self.market_symbols.get(normalized_market, ()))
        session_future = _MARKET_OVERVIEW_EXECUTOR.submit(
            self.session_resolver,
            normalized_market,
            fetched_at,
        )
        futures = [(symbol, _MARKET_OVERVIEW_EXECUTOR.submit(self.snapshot_loader, symbol)) for symbol in symbols]
        _, pending = wait(
            [session_future, *(future for _, future in futures)],
            timeout=self.overview_timeout_seconds,
        )
        if symbols:
            for symbol, future in futures:
                if future in pending:
                    future.cancel()
                    warnings.append(f"market_symbol_timeout:{symbol}")
                    continue
                try:
                    items.append(self._security_item(future.result(), normalized_market))
                except Exception:
                    warnings.append(f"market_symbol_unavailable:{symbol}")

        headlines: List[Dict[str, Any]] = []
        news_state = {
            "source": "market_news_pool",
            "status": "unavailable",
            "observed_at": None,
            "fetched_at": fetched_at,
            "delay_seconds": None,
            "warning_code": "market_news_unavailable",
        }
        if self.news_loader is not None:
            try:
                headlines = [self._headline(item, fetched_at) for item in self.news_loader(normalized_market)[:20]]
                news_state = {
                    "source": "market_news_pool",
                    "status": "fresh" if headlines else "unavailable",
                    "observed_at": fetched_at if headlines else None,
                    "fetched_at": fetched_at,
                    "delay_seconds": 0 if headlines else None,
                    "warning_code": None if headlines else "market_news_unavailable",
                }
            except Exception:
                headlines = []
        if news_state["status"] == "unavailable":
            warnings.append("market_news_unavailable")

        indices: List[Dict[str, Any]] = []
        if self.index_loader is not None:
            try:
                indices = [dict(item) for item in self.index_loader(normalized_market) if isinstance(item, dict)]
            except Exception:
                indices = []
        else:
            indices = items[:1]

        valid_changes = [item.get("change_percent") for item in items if item.get("change_percent") is not None]
        breadth = {
            "advancers": sum(1 for value in valid_changes if float(value) > 0),
            "decliners": sum(1 for value in valid_changes if float(value) < 0),
            "unchanged": sum(1 for value in valid_changes if float(value) == 0),
            "unavailable": not bool(valid_changes),
        }
        quote_states = [str(item["source_state"]["status"]) for item in items]
        if not quote_states or all(status == "unavailable" for status in quote_states):
            quote_status = "unavailable"
        elif all(status == "fresh" for status in quote_states):
            quote_status = "fresh"
        elif any(status in {"fresh", "cached"} for status in quote_states):
            quote_status = "cached"
        else:
            quote_status = "stale"
        quote_state = {
            "source": f"{normalized_market}_market_snapshot",
            "status": quote_status,
            "observed_at": max((item["source_state"].get("observed_at") or "" for item in items), default=None) or None,
            "fetched_at": fetched_at,
            "delay_seconds": 0 if quote_status == "fresh" else None,
            "warning_code": "market_quotes_unavailable" if quote_status == "unavailable" else None,
        }
        if quote_status == "unavailable":
            warnings.append("market_quotes_unavailable")
        sorted_items = sorted(
            items,
            key=lambda item: (item.get("change_percent") is None, -(float(item.get("change_percent") or 0))),
        )
        if session_future in pending:
            session_future.cancel()
            session = unknown_market_session("calendar_timeout")
        else:
            try:
                session = session_future.result()
            except Exception:
                session = unknown_market_session("calendar_error")
        if not isinstance(session, dict):
            session = unknown_market_session("calendar_error")
        payload = {
            "market": normalized_market,
            "as_of": fetched_at,
            **session,
            "indices": indices,
            "breadth": breadth,
            "movers": sorted_items,
            "heatmap": items,
            "headlines": headlines,
            "sources": [quote_state, news_state],
            "warnings": list(dict.fromkeys(warnings)),
            "cache": {"hit": False, "age_seconds": 0, "ttl_seconds": self.cache_ttl_seconds},
            "ai_used": False,
            "informational_only": True,
        }
        with self._lock:
            self._cache[normalized_market] = (time.monotonic(), copy.deepcopy(payload))
        return payload

    def get_symbol(self, symbol: str, *, personalization_user_id: Optional[int] = None) -> Dict[str, Any]:
        snapshot = self.detail_loader(symbol)
        market = self._normalize_snapshot_market(snapshot.get("market"), symbol)
        quote = dict(snapshot.get("quote") or {})
        profile = dict(snapshot.get("profile") or {})
        trend = snapshot.get("trend") or {}
        history = [dict(point) for point in trend.get("points") or []]
        freshness = str(quote.get("freshness") or "unavailable")
        if freshness not in {"fresh", "cached", "stale", "unavailable"}:
            freshness = "unavailable"
        observed_at = quote.get("update_time")
        source_state = {
            "source": str(quote.get("source") or f"{market}_quote"),
            "status": freshness,
            "observed_at": str(observed_at) if observed_at else None,
            "fetched_at": _utc_now(),
            "delay_seconds": None,
            "warning_code": None if freshness in {"fresh", "cached"} else "quote_not_current",
        }
        intelligence = snapshot.get("intelligence") or {}
        headlines = []
        for item in intelligence.get("items") or []:
            if str(item.get("category") or "") not in {"news", "announcements"}:
                continue
            headlines.append(self._headline(item, source_state["fetched_at"]))
        personalization = None
        if personalization_user_id is not None:
            watchlist = PlatformWatchlistService().list_items(int(personalization_user_id))
            watched = any(str(item.get("stock_code")) == str(snapshot.get("stock_code") or symbol).upper() for item in watchlist.get("items") or [])
            personalization = {"watchlisted": watched, "alert_count": 0}
        return {
            "symbol": str(snapshot.get("stock_code") or symbol).upper(),
            "name": str(snapshot.get("stock_name") or profile.get("company_name") or symbol),
            "market": market,
            "currency": profile.get("currency") or self._MARKET_CURRENCIES.get(market),
            "as_of": str(observed_at) if observed_at else None,
            "quote": quote,
            "history": history[:120],
            "indicators": dict(snapshot.get("indicators") or {}),
            "profile": profile,
            "headlines": headlines,
            "sources": [source_state],
            "warnings": [str(item.get("code")) for item in snapshot.get("warnings") or [] if isinstance(item, dict) and item.get("code")],
            "personalization": personalization,
            "ai_used": False,
            "informational_only": True,
        }

    def _read_cache(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._cache.get(key)
        if entry is None:
            return None
        created, payload = entry
        age = max(0, int(time.monotonic() - created))
        if age >= self.cache_ttl_seconds:
            return None
        result = copy.deepcopy(payload)
        result["cache"] = {"hit": True, "age_seconds": age, "ttl_seconds": self.cache_ttl_seconds}
        return result

    @staticmethod
    def _normalize_market(market: str) -> str:
        value = (market or "").strip().lower()
        if value not in {"cn", "hk", "us"}:
            raise ValueError("unsupported_market")
        return value

    @staticmethod
    def _normalize_snapshot_market(value: Any, symbol: str) -> str:
        market = str(value or "").lower()
        if market in {"cn", "a_share", "a"}:
            return "cn"
        if market in {"hk", "hong_kong"}:
            return "hk"
        if market in {"us", "usa"}:
            return "us"
        return PlatformWatchlistService.market_for_code(symbol)

    @classmethod
    def _security_item(cls, snapshot: Dict[str, Any], market: str) -> Dict[str, Any]:
        quote = snapshot.get("quote") or {}
        profile = snapshot.get("profile") or {}
        freshness = str(quote.get("freshness") or "unavailable")
        if freshness not in {"fresh", "cached", "stale", "unavailable"}:
            freshness = "unavailable"
        observed_at = quote.get("update_time")
        return {
            "symbol": str(snapshot.get("stock_code") or ""),
            "name": str(snapshot.get("stock_name") or profile.get("company_name") or snapshot.get("stock_code") or ""),
            "market": market,
            "currency": profile.get("currency") or cls._MARKET_CURRENCIES.get(market),
            "current_price": quote.get("current_price"),
            "change_percent": quote.get("change_percent"),
            "volume": quote.get("volume"),
            "turnover": quote.get("amount"),
            "market_cap": profile.get("market_cap"),
            "sector": profile.get("sector"),
            "source_state": {
                "source": str(quote.get("source") or f"{market}_quote"),
                "status": freshness,
                "observed_at": str(observed_at) if observed_at else None,
                "fetched_at": _utc_now(),
                "delay_seconds": None,
                "warning_code": None if freshness in {"fresh", "cached"} else "quote_not_current",
            },
        }

    @staticmethod
    def _headline(item: Dict[str, Any], fetched_at: str) -> Dict[str, Any]:
        observed_at = item.get("published_at") or item.get("updated_at")
        return {
            "title": str(item.get("title") or "Market information"),
            "summary": item.get("summary"),
            "publisher": item.get("publisher"),
            "published_at": str(observed_at) if observed_at else None,
            "url": item.get("url"),
            "source_state": {
                "source": str(item.get("source") or "market_news_pool"),
                "status": "fresh" if observed_at else "cached",
                "observed_at": str(observed_at) if observed_at else None,
                "fetched_at": fetched_at,
                "delay_seconds": None,
                "warning_code": None,
            },
        }
