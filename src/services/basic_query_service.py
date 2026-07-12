# -*- coding: utf-8 -*-
"""No-AI stock snapshot service."""

from __future__ import annotations

import concurrent.futures
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional

from data_provider.base import normalize_stock_code
from src.services.stock_code_utils import normalize_crypto_symbol
from src.services.market_data_cache import CacheHit, MarketDataCache
from src.services.market_source_health import MarketSourceHealthRegistry, default_market_source_health
from src.services.persistent_market_data_cache import default_persistent_market_data_cache
from src.services.a_share_enrichment_service import AShareEnrichmentService
from src.services.stock_service import StockService


_BASIC_QUERY_FETCH_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(2, int(os.getenv("BASIC_QUERY_FETCH_MAX_WORKERS", "8")))
)
_DEFAULT_FETCH_TIMEOUT_SECONDS = float(os.getenv("BASIC_QUERY_FETCH_TIMEOUT_SEC", "4"))
_DEFAULT_PROFILE_TIMEOUT_SECONDS = float(os.getenv("BASIC_QUERY_PROFILE_TIMEOUT_SEC", "2"))
_DEFAULT_REFERENCE_QUOTE_TIMEOUT_SECONDS = float(os.getenv("BASIC_QUERY_REFERENCE_QUOTE_TIMEOUT_SEC", "1.2"))
_DEFAULT_STALE_REVALIDATION_TIMEOUT_SECONDS = float(os.getenv("BASIC_QUERY_STALE_REVALIDATION_TIMEOUT_SEC", "0.8"))


@dataclass(frozen=True)
class MarketRoute:
    input_code: str
    normalized_code: str
    market: str
    channel: str
    data_source_lane: str
    quote_sources: tuple[str, ...]
    history_sources: tuple[str, ...]
    profile_sources: tuple[str, ...] = ()
    ai_required: bool = False

    def to_payload(self) -> Dict[str, Any]:
        return {
            "input_code": self.input_code,
            "normalized_code": self.normalized_code,
            "market": self.market,
            "channel": self.channel,
            "data_source_lane": self.data_source_lane,
            "quote_sources": list(self.quote_sources),
            "history_sources": list(self.history_sources),
            "profile_sources": list(self.profile_sources),
            "ai_required": self.ai_required,
        }


class BasicQueryService:
    """Build fast stock snapshots from deterministic market data only."""

    def __init__(
        self,
        stock_service: Optional[StockService] = None,
        cache: Optional[MarketDataCache] = None,
        fetch_timeout_seconds: Optional[float] = None,
        profile_timeout_seconds: Optional[float] = None,
        reference_quote_timeout_seconds: Optional[float] = None,
        stale_revalidation_timeout_seconds: Optional[float] = None,
        source_health: Optional[MarketSourceHealthRegistry] = None,
        a_share_enrichment_service: Optional[Any] = None,
        global_equity_enrichment_service: Optional[Any] = None,
    ):
        self.stock_service = stock_service or StockService()
        self.cache = cache or default_persistent_market_data_cache
        self.source_health = source_health or default_market_source_health
        self.a_share_enrichment_service = a_share_enrichment_service or AShareEnrichmentService()
        self.global_equity_enrichment_service = global_equity_enrichment_service
        self.fetch_timeout_seconds = (
            _DEFAULT_FETCH_TIMEOUT_SECONDS if fetch_timeout_seconds is None else max(0.001, float(fetch_timeout_seconds))
        )
        self.profile_timeout_seconds = (
            _DEFAULT_PROFILE_TIMEOUT_SECONDS if profile_timeout_seconds is None else max(0.001, float(profile_timeout_seconds))
        )
        self.reference_quote_timeout_seconds = (
            _DEFAULT_REFERENCE_QUOTE_TIMEOUT_SECONDS
            if reference_quote_timeout_seconds is None
            else max(0.001, float(reference_quote_timeout_seconds))
        )
        self.stale_revalidation_timeout_seconds = (
            _DEFAULT_STALE_REVALIDATION_TIMEOUT_SECONDS
            if stale_revalidation_timeout_seconds is None
            else max(0.001, float(stale_revalidation_timeout_seconds))
        )

    def get_snapshot(self, stock_code: str, *, force_refresh: bool = False) -> Dict[str, Any]:
        started = time.perf_counter()
        route = self._resolve_route(stock_code)
        code = route.normalized_code
        cached_history_available = bool(
            not force_refresh and self.cache.get(f"history:{code}:daily:30") is not None
        )
        (
            quote,
            quote_freshness,
            quote_cache,
            quote_elapsed_ms,
            quote_source,
            quote_timeout,
            quote_fallback,
            quote_error,
            quote_health,
            quote_cache_origin,
        ) = self._get_quote(
            code,
            route=route,
            force_refresh=force_refresh,
            cached_history_available=cached_history_available,
        )
        (
            history,
            history_freshness,
            history_cache,
            history_elapsed_ms,
            history_source,
            history_timeout,
            history_fallback,
            history_error,
            history_health,
            history_cache_origin,
        ) = self._get_history(code, route=route, force_refresh=force_refresh)
        (
            profile,
            profile_freshness,
            profile_cache,
            profile_elapsed_ms,
            profile_source,
            profile_timeout,
            profile_fallback,
            profile_error,
            profile_health,
            profile_cache_origin,
        ) = self._get_profile(code, route=route, quote=quote, force_refresh=force_refresh)
        history_rows = (history or {}).get("data", [])
        indicators = self._compute_indicators(history_rows)
        trend = self._trend_payload(
            history_rows,
            source=(history or {}).get("source") or history_source,
        )
        if not quote and route.market == "hk":
            history_quote = self._quote_from_history_close_fallback(
                code=code,
                route=route,
                history=history,
                history_rows=history_rows,
                history_source=history_source,
            )
            if history_quote:
                quote = history_quote
                quote_freshness = "stale" if history_freshness == "stale" else "cached"
                quote_cache = "fallback"
                quote_source = str(history_quote.get("source") or history_source)
                quote_fallback = "history_last_close"
                quote_health = history_health
                quote_cache_origin = history_cache_origin
        warnings = self._build_warnings(
            quote=quote,
            quote_freshness=quote_freshness,
            history=history,
            route=route,
            quote_error=quote_error,
            history_error=history_error,
            quote_fallback=quote_fallback,
        )
        quote_payload = self._quote_payload(
            quote,
            freshness=quote_freshness,
            source_fallback=route.quote_sources[0],
        )
        profile_payload = self._profile_payload(
            profile,
            freshness=profile_freshness,
            source_fallback=profile_source,
        )
        a_share_enrichment = self._a_share_enrichment_payload(
            route=route,
            code=code,
            stock_name=self._stock_name(quote, history, profile),
            quote=quote_payload,
            profile=profile_payload,
            indicators=indicators,
        )
        global_equity_enrichment = self._global_equity_enrichment_payload(
            route=route,
            code=code,
            stock_name=(profile_payload or {}).get("company_name") or self._stock_name(quote, history, profile),
            profile=profile_payload,
            force_refresh=force_refresh,
        )

        return {
            "stock_code": code,
            "stock_name": self._stock_name(quote, history, profile),
            "market": route.market,
            "quote": quote_payload,
            "profile": profile_payload,
            "indicators": indicators,
            "trend": trend,
            "intelligence": self._intelligence_payload(
                route=route,
                quote=quote_payload,
                profile=profile_payload,
                indicators=indicators,
                trend=trend,
                warnings=warnings,
                a_share_enrichment=a_share_enrichment,
                global_equity_enrichment=global_equity_enrichment,
            ),
            "route": route.to_payload(),
            "warnings": warnings,
            "degradation": self._degradation_payload(warnings),
            "diagnostics": self._diagnostics_payload(
                started=started,
                route=route,
                quote_elapsed_ms=quote_elapsed_ms,
                history_elapsed_ms=history_elapsed_ms,
                profile_elapsed_ms=profile_elapsed_ms,
                quote_cache=quote_cache,
                history_cache=history_cache,
                profile_cache=profile_cache,
                quote_source=quote_source,
                history_source=history_source,
                profile_source=profile_source,
                quote_freshness=quote_freshness,
                history_freshness=history_freshness,
                profile_freshness=profile_freshness,
                quote_timeout=quote_timeout,
                history_timeout=history_timeout,
                profile_timeout=profile_timeout,
                quote_fallback=quote_fallback,
                history_fallback=history_fallback,
                profile_fallback=profile_fallback,
                quote_error=quote_error,
                history_error=history_error,
                profile_error=profile_error,
                quote_health=quote_health,
                history_health=history_health,
                profile_health=profile_health,
                quote_cache_origin=quote_cache_origin,
                history_cache_origin=history_cache_origin,
                profile_cache_origin=profile_cache_origin,
                force_refresh=force_refresh,
            ),
            "ai_used": False,
        }

    def prewarm_snapshots(self, stock_codes: Iterable[str]) -> Dict[str, Any]:
        started = time.perf_counter()
        seen: set[str] = set()
        symbols: list[str] = []
        results: Dict[str, Dict[str, Any]] = {}
        warmed = 0
        degraded = 0
        for raw_code in stock_codes or []:
            route = self._resolve_route(str(raw_code))
            code = route.normalized_code
            if code in seen:
                continue
            seen.add(code)
            symbols.append(code)
            try:
                snapshot = self.get_snapshot(code)
                diagnostics = snapshot.get("diagnostics") or {}
                quote_ready = (snapshot.get("quote") or {}).get("freshness") != "unavailable"
                history_ready = bool((snapshot.get("indicators") or {}).get("last_close") is not None)
                status = "warmed" if quote_ready or history_ready else "degraded"
                if status == "warmed":
                    warmed += 1
                else:
                    degraded += 1
                results[code] = {
                    "status": status,
                    "market": snapshot.get("market"),
                    "route_lane": diagnostics.get("route_lane"),
                    "cache": diagnostics.get("cache"),
                    "fallback": diagnostics.get("fallback"),
                    "source_health": diagnostics.get("source_health"),
                    "warnings": [item.get("code") for item in snapshot.get("warnings", [])],
                }
            except Exception:
                degraded += 1
                results[code] = {
                    "status": "error",
                    "warnings": ["prewarm_failed"],
                }
        return {
            "requested": len(symbols),
            "warmed": warmed,
            "degraded": degraded,
            "symbols": symbols,
            "results": results,
            "elapsed_ms": self._elapsed_ms(started),
            "ai_used": False,
        }

    def _get_quote(
        self,
        code: str,
        *,
        route: MarketRoute,
        force_refresh: bool = False,
        cached_history_available: bool = False,
    ) -> tuple[Optional[Dict[str, Any]], str, str, int, str, bool, str, Optional[str], Dict[str, Any], str]:
        started = time.perf_counter()
        cache_key = f"quote:{code}"
        hit = None if force_refresh else self.cache.get(cache_key)
        if hit is not None and hit.freshness != "stale":
            source = self._payload_source(hit.value, hit.source or route.quote_sources[0])
            fallback = self._cache_fallback(hit)
            return hit.value, hit.freshness, "hit", self._elapsed_ms(started), source, False, fallback, None, self.source_health.snapshot(source), hit.origin
        stale_hit = hit if hit is not None and hit.freshness == "stale" else None
        source_id = route.quote_sources[0]
        health = self.source_health.snapshot(source_id)
        if health.get("status") == "cooling_down":
            if stale_hit is not None:
                source = self._payload_source(stale_hit.value, stale_hit.source or source_id)
                return stale_hit.value, "stale", "stale_fallback", self._elapsed_ms(started), source, False, self._cache_fallback(stale_hit), "cooling_down", health, stale_hit.origin
            return None, "unavailable", "unavailable", self._elapsed_ms(started), source_id, False, "none", "cooling_down", health, "none"
        quote, error = self._call_with_timeout(
            lambda: self.stock_service.get_realtime_quote(code),
            timeout_seconds=(
                min(self.fetch_timeout_seconds, self.stale_revalidation_timeout_seconds)
                if stale_hit is not None or cached_history_available
                else None
            ),
        )
        elapsed_ms = self._elapsed_ms(started)
        if quote:
            quote = dict(quote)
            quote.setdefault("source", source_id)
            self.cache.set(cache_key, quote, source=quote.get("source") or source_id)
            self.source_health.record_success(source_id, elapsed_ms=elapsed_ms)
        elif error == "timeout":
            self.source_health.record_timeout(source_id, elapsed_ms=elapsed_ms)
        elif error == "error":
            self.source_health.record_error(source_id, elapsed_ms=elapsed_ms)
        elif stale_hit is not None:
            error = "unavailable"
        health = self.source_health.snapshot(source_id)
        if not quote and stale_hit is not None:
            source = self._payload_source(stale_hit.value, stale_hit.source or source_id)
            return stale_hit.value, "stale", "stale_fallback", elapsed_ms, source, error == "timeout", self._cache_fallback(stale_hit), error, health, stale_hit.origin
        source = self._payload_source(quote, source_id)
        cache_state = "refresh" if force_refresh and quote else ("revalidated" if stale_hit is not None and quote else ("miss" if error is None else "unavailable"))
        fallback = "live" if quote else "none"
        return quote, "fresh" if quote else "unavailable", cache_state, elapsed_ms, source, error == "timeout", fallback, error, health, "none"

    def _get_history(
        self,
        code: str,
        *,
        route: MarketRoute,
        force_refresh: bool = False,
    ) -> tuple[Optional[Dict[str, Any]], str, str, int, str, bool, str, Optional[str], Dict[str, Any], str]:
        started = time.perf_counter()
        cache_key = f"history:{code}:daily:30"
        hit = None if force_refresh else self.cache.get(cache_key)
        if hit is not None and hit.freshness != "stale":
            source = self._payload_source(hit.value, hit.source or route.history_sources[0])
            fallback = self._cache_fallback(hit)
            return hit.value, hit.freshness, "hit", self._elapsed_ms(started), source, False, fallback, None, self.source_health.snapshot(source), hit.origin
        stale_hit = hit if hit is not None and hit.freshness == "stale" else None
        source_id = route.history_sources[0]
        health = self.source_health.snapshot(source_id)
        if health.get("status") == "cooling_down":
            if stale_hit is not None:
                source = self._payload_source(stale_hit.value, stale_hit.source or source_id)
                return stale_hit.value, "stale", "stale_fallback", self._elapsed_ms(started), source, False, self._cache_fallback(stale_hit), "cooling_down", health, stale_hit.origin
            return None, "unavailable", "unavailable", self._elapsed_ms(started), source_id, False, "none", "cooling_down", health, "none"
        history, error = self._call_with_timeout(
            lambda: self.stock_service.get_history_data(code, period="daily", days=30),
            timeout_seconds=(
                min(self.fetch_timeout_seconds, self.stale_revalidation_timeout_seconds)
                if stale_hit is not None
                else None
            ),
        )
        elapsed_ms = self._elapsed_ms(started)
        if history:
            history = dict(history)
            history.setdefault("source", source_id)
            self.cache.set(cache_key, history, source=history.get("source") or source_id)
            self.source_health.record_success(source_id, elapsed_ms=elapsed_ms)
        elif error == "timeout":
            self.source_health.record_timeout(source_id, elapsed_ms=elapsed_ms)
        elif error == "error":
            self.source_health.record_error(source_id, elapsed_ms=elapsed_ms)
        elif stale_hit is not None:
            error = "unavailable"
        health = self.source_health.snapshot(source_id)
        if not history and stale_hit is not None:
            source = self._payload_source(stale_hit.value, stale_hit.source or source_id)
            return stale_hit.value, "stale", "stale_fallback", elapsed_ms, source, error == "timeout", self._cache_fallback(stale_hit), error, health, stale_hit.origin
        source = self._payload_source(history, source_id)
        cache_state = "refresh" if force_refresh and history else ("revalidated" if stale_hit is not None and history else ("miss" if error is None else "unavailable"))
        fallback = "live" if history else "none"
        return history, "fresh" if history else "unavailable", cache_state, elapsed_ms, source, error == "timeout", fallback, error, health, "none"

    def _get_profile(
        self,
        code: str,
        *,
        route: MarketRoute,
        quote: Optional[Dict[str, Any]],
        force_refresh: bool = False,
    ) -> tuple[Optional[Dict[str, Any]], str, str, int, str, bool, str, Optional[str], Dict[str, Any], str]:
        started = time.perf_counter()
        source_id = route.profile_sources[0] if route.profile_sources else self._profile_source_for_route(route)
        cache_key = f"profile:{code}"
        hit = None if force_refresh else self.cache.get(cache_key)
        if hit is not None and hit.freshness != "stale":
            source = self._payload_source(hit.value, hit.source or source_id)
            fallback = self._cache_fallback(hit)
            return hit.value, hit.freshness, "hit", self._elapsed_ms(started), source, False, fallback, None, self.source_health.snapshot(source), hit.origin
        stale_hit = hit if hit is not None and hit.freshness == "stale" else None

        health = self.source_health.snapshot(source_id)
        if health.get("status") == "cooling_down":
            if stale_hit is not None:
                source = self._payload_source(stale_hit.value, stale_hit.source or source_id)
                return stale_hit.value, "stale", "stale_fallback", self._elapsed_ms(started), source, False, self._cache_fallback(stale_hit), "cooling_down", health, stale_hit.origin
            profile = self._profile_from_quote(code, quote, source=source_id)
            freshness = "fresh" if profile else "unavailable"
            return profile, freshness, "unavailable", self._elapsed_ms(started), source_id, False, "quote", "cooling_down", health, "none"

        profile, error = self._call_with_timeout(
            lambda: self._fetch_profile_from_stock_service(code, route=route),
            timeout_seconds=(
                min(self.profile_timeout_seconds, self.stale_revalidation_timeout_seconds)
                if stale_hit is not None
                else self.profile_timeout_seconds
            ),
        )
        if not isinstance(profile, dict):
            profile = None
        profile = self._merge_profile_with_quote(code, profile, quote, source_fallback=source_id)
        elapsed_ms = self._elapsed_ms(started)
        if profile:
            profile.setdefault("source", source_id)
            self.cache.set(cache_key, profile, source=profile.get("source") or source_id)
            self.source_health.record_success(source_id, elapsed_ms=elapsed_ms)
        elif error == "timeout":
            self.source_health.record_timeout(source_id, elapsed_ms=elapsed_ms)
        elif error == "error":
            self.source_health.record_error(source_id, elapsed_ms=elapsed_ms)
        elif stale_hit is not None:
            error = "unavailable"
        health = self.source_health.snapshot(source_id)
        if not profile and stale_hit is not None:
            source = self._payload_source(stale_hit.value, stale_hit.source or source_id)
            return stale_hit.value, "stale", "stale_fallback", elapsed_ms, source, error == "timeout", self._cache_fallback(stale_hit), error, health, stale_hit.origin
        source = self._payload_source(profile, source_id)
        cache_state = "refresh" if force_refresh and profile else ("revalidated" if stale_hit is not None and profile else ("miss" if error is None else "unavailable"))
        fallback = "live" if profile else "none"
        return profile, "fresh" if profile else "unavailable", cache_state, elapsed_ms, source, error == "timeout", fallback, error, health, "none"

    def _quote_payload(
        self,
        quote: Optional[Dict[str, Any]],
        *,
        freshness: str = "fresh",
        source_fallback: str = "stock_service",
    ) -> Dict[str, Any]:
        if not quote:
            return {"source": source_fallback, "freshness": "unavailable"}
        return {
            "current_price": quote.get("current_price"),
            "change": quote.get("change"),
            "change_percent": quote.get("change_percent"),
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "prev_close": quote.get("prev_close"),
            "volume": quote.get("volume"),
            "amount": quote.get("amount"),
            "update_time": quote.get("update_time"),
            "source": quote.get("source") or source_fallback,
            "freshness": freshness if freshness in {"cached", "stale"} else quote.get("freshness") or freshness,
        }

    def _profile_payload(
        self,
        profile: Optional[Dict[str, Any]],
        *,
        freshness: str = "fresh",
        source_fallback: str = "profile_unavailable",
    ) -> Optional[Dict[str, Any]]:
        if not profile:
            return None
        return {
            "company_name": profile.get("company_name"),
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
            "exchange": profile.get("exchange"),
            "currency": profile.get("currency"),
            "country": profile.get("country"),
            "website": profile.get("website"),
            "market_cap": self._float_or_none(profile.get("market_cap")),
            "pe_ratio": self._float_or_none(profile.get("pe_ratio")),
            "pb_ratio": self._float_or_none(profile.get("pb_ratio")),
            "dividend_yield": self._float_or_none(profile.get("dividend_yield")),
            "revenue": self._float_or_none(profile.get("revenue")),
            "net_profit": self._float_or_none(profile.get("net_profit")),
            "revenue_growth": self._float_or_none(profile.get("revenue_growth")),
            "earnings_growth": self._float_or_none(profile.get("earnings_growth")),
            "source": profile.get("source") or source_fallback,
            "freshness": freshness if freshness in {"cached", "stale"} else profile.get("freshness") or freshness,
        }

    def _stock_name(
        self,
        quote: Optional[Dict[str, Any]],
        history: Optional[Dict[str, Any]],
        profile: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if quote and quote.get("stock_name"):
            return quote.get("stock_name")
        if history and history.get("stock_name"):
            return history.get("stock_name")
        if profile and profile.get("company_name"):
            return profile.get("company_name")
        return None

    def _diagnostics_payload(
        self,
        *,
        started: float,
        route: MarketRoute,
        quote_elapsed_ms: int,
        history_elapsed_ms: int,
        profile_elapsed_ms: int,
        quote_cache: str,
        history_cache: str,
        profile_cache: str,
        quote_source: str,
        history_source: str,
        profile_source: str,
        quote_freshness: str,
        history_freshness: str,
        profile_freshness: str,
        quote_timeout: bool,
        history_timeout: bool,
        profile_timeout: bool,
        quote_fallback: str,
        history_fallback: str,
        profile_fallback: str,
        quote_error: Optional[str],
        history_error: Optional[str],
        profile_error: Optional[str],
        quote_health: Dict[str, Any],
        history_health: Dict[str, Any],
        profile_health: Dict[str, Any],
        quote_cache_origin: str,
        history_cache_origin: str,
        profile_cache_origin: str,
        force_refresh: bool,
    ) -> Dict[str, Any]:
        elapsed_ms = self._elapsed_ms(started)
        slow_threshold_ms = 3000
        timed_out = quote_timeout or history_timeout or profile_timeout
        cache_states = (quote_cache, history_cache, profile_cache)
        stale_revalidation = any(state in {"revalidated", "stale_fallback"} for state in cache_states)
        return {
            "elapsed_ms": elapsed_ms,
            "quote_elapsed_ms": quote_elapsed_ms,
            "history_elapsed_ms": history_elapsed_ms,
            "profile_elapsed_ms": profile_elapsed_ms,
            "cache": {
                "quote": quote_cache,
                "history": history_cache,
                "profile": profile_cache,
            },
            "sources": {
                "quote": quote_source,
                "history": history_source,
                "profile": profile_source,
            },
            "freshness": {
                "quote": quote_freshness,
                "history": history_freshness,
                "profile": profile_freshness,
            },
            "timeouts": {
                "quote": quote_timeout,
                "history": history_timeout,
                "profile": profile_timeout,
            },
            "errors": {
                "quote": quote_error,
                "history": history_error,
                "profile": profile_error,
            },
            "fallback": {
                "quote": quote_fallback,
                "history": history_fallback,
                "profile": profile_fallback,
            },
            "source_health": {
                "quote": quote_health,
                "history": history_health,
                "profile": profile_health,
            },
            "persistent_cache": {
                "quote": quote_cache_origin,
                "history": history_cache_origin,
                "profile": profile_cache_origin,
                "mode": getattr(self.cache, "persistent_mode", "memory"),
                "storage": getattr(self.cache, "storage_label", "memory"),
            },
            "refresh": {
                "mode": "force_refresh" if force_refresh else ("stale_while_revalidate" if stale_revalidation else "cache_first"),
                "requested": bool(force_refresh or stale_revalidation),
                "quote": bool(force_refresh or quote_cache in {"revalidated", "stale_fallback"}),
                "history": bool(force_refresh or history_cache in {"revalidated", "stale_fallback"}),
                "profile": bool(force_refresh or profile_cache in {"revalidated", "stale_fallback"}),
                "stale_timeout_seconds": self.stale_revalidation_timeout_seconds,
            },
            "route_lane": route.data_source_lane,
            "performance": {
                "status": "slow" if timed_out or elapsed_ms > slow_threshold_ms else "ok",
                "slow_threshold_ms": slow_threshold_ms,
            },
        }

    def _call_with_timeout(
        self,
        callback: Callable[[], Optional[Dict[str, Any]]],
        *,
        timeout_seconds: Optional[float] = None,
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        future = _BASIC_QUERY_FETCH_EXECUTOR.submit(callback)
        try:
            timeout = self.fetch_timeout_seconds if timeout_seconds is None else timeout_seconds
            return future.result(timeout=timeout), None
        except concurrent.futures.TimeoutError:
            future.cancel()
            return None, "timeout"
        except Exception:
            return None, "error"

    def _fetch_profile_from_stock_service(self, code: str, *, route: MarketRoute) -> Optional[Dict[str, Any]]:
        if route.market not in {"us", "hk"}:
            return None
        class_method = getattr(type(self.stock_service), "get_basic_company_profile", None)
        if not callable(class_method):
            return None
        method = getattr(self.stock_service, "get_basic_company_profile", None)
        if not callable(method):
            return None
        profile = method(code)
        return profile if isinstance(profile, dict) else None

    def _profile_source_for_route(self, route: MarketRoute) -> str:
        if route.market in {"us", "hk"}:
            return "yfinance_profile"
        return "quote_profile"

    def _merge_profile_with_quote(
        self,
        code: str,
        profile: Optional[Dict[str, Any]],
        quote: Optional[Dict[str, Any]],
        *,
        source_fallback: str,
    ) -> Optional[Dict[str, Any]]:
        merged: Dict[str, Any] = dict(profile or {})
        quote_profile = self._profile_from_quote(code, quote, source=source_fallback)
        for key, value in quote_profile.items():
            if merged.get(key) in (None, "") and value not in (None, ""):
                merged[key] = value
        if not self._has_profile_content(merged):
            return None
        merged.setdefault("stock_code", code)
        merged.setdefault("source", source_fallback)
        return merged

    def _profile_from_quote(
        self,
        code: str,
        quote: Optional[Dict[str, Any]],
        *,
        source: str,
    ) -> Dict[str, Any]:
        if not quote:
            return {"stock_code": code, "source": source}
        return {
            "stock_code": code,
            "company_name": quote.get("stock_name") or quote.get("company_name"),
            "market_cap": quote.get("market_cap") or quote.get("total_mv"),
            "pe_ratio": quote.get("pe_ratio"),
            "pb_ratio": quote.get("pb_ratio"),
            "source": quote.get("profile_source") or quote.get("source") or source,
        }

    def _has_profile_content(self, profile: Dict[str, Any]) -> bool:
        meaningful_keys = {
            "sector",
            "industry",
            "exchange",
            "currency",
            "country",
            "website",
            "market_cap",
            "pe_ratio",
            "pb_ratio",
            "dividend_yield",
            "revenue",
            "net_profit",
            "revenue_growth",
            "earnings_growth",
        }
        return any(profile.get(key) not in (None, "") for key in meaningful_keys)

    def _cache_fallback(self, hit: CacheHit) -> str:
        if hit.origin == "disk":
            return "stale_disk_cache" if hit.freshness == "stale" else "disk_cache"
        return "stale_cache" if hit.freshness == "stale" else "cache"

    def _payload_source(self, payload: Optional[Dict[str, Any]], fallback: str) -> str:
        if isinstance(payload, dict) and payload.get("source"):
            return str(payload.get("source"))
        return fallback

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int(round((time.perf_counter() - started) * 1000)))

    def _compute_indicators(self, rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        closes: list[float] = []
        volumes: list[float] = []
        for row in rows or []:
            close = self._float_or_none(row.get("close"))
            if close is not None:
                closes.append(close)
            volume = self._float_or_none(row.get("volume"))
            if volume is not None:
                volumes.append(volume)

        return {
            "ma5": self._moving_average(closes, 5),
            "ma10": self._moving_average(closes, 10),
            "ma20": self._moving_average(closes, 20),
            "volume_ma5": self._moving_average(volumes, 5),
            "last_close": closes[-1] if closes else None,
            "price_change_5d": self._percent_change(closes, 5),
            "price_change_20d": self._percent_change(closes, 20),
            "volume_change_vs_ma5": self._volume_change_vs_ma(volumes, 5),
            "volume_price_signal": self._volume_price_signal(closes, volumes),
        }

    def _trend_payload(
        self,
        rows: Iterable[Dict[str, Any]],
        *,
        source: str = "history",
        max_points: int = 20,
    ) -> Optional[Dict[str, Any]]:
        points: list[Dict[str, Any]] = []
        for row in rows or []:
            close = self._float_or_none(row.get("close"))
            if close is None:
                continue
            volume = self._float_or_none(row.get("volume"))
            raw_date = row.get("date") or row.get("datetime") or row.get("timestamp")
            points.append({
                "date": str(raw_date) if raw_date is not None else None,
                "close": close,
                "volume": volume,
            })

        points = points[-max(1, int(max_points)):]
        if not points:
            return None

        closes = [point["close"] for point in points]
        first_close = closes[0]
        last_close = closes[-1]
        change_percent = None if first_close == 0 else round(((last_close - first_close) / first_close) * 100, 4)
        return {
            "window": len(points),
            "source": source or "history",
            "points": points,
            "min_close": min(closes),
            "max_close": max(closes),
            "change_percent": change_percent,
        }

    def _quote_from_history_close_fallback(
        self,
        *,
        code: str,
        route: MarketRoute,
        history: Optional[Dict[str, Any]],
        history_rows: Iterable[Dict[str, Any]],
        history_source: str,
    ) -> Optional[Dict[str, Any]]:
        rows = [row for row in (history_rows or []) if isinstance(row, dict)]
        if not rows:
            return None
        latest = None
        for row in reversed(rows):
            if self._float_or_none(row.get("close")) is not None:
                latest = row
                break
        if latest is None:
            return None
        previous = None
        for row in reversed(rows[: rows.index(latest)]):
            if self._float_or_none(row.get("close")) is not None:
                previous = row
                break

        current_price = self._float_or_none(latest.get("close"))
        prev_close = self._float_or_none(previous.get("close")) if previous else None
        change = None
        change_percent = None
        if current_price is not None and prev_close not in (None, 0):
            change = round(current_price - prev_close, 4)
            change_percent = round((change / prev_close) * 100, 4)

        source_base = str((history or {}).get("source") or history_source or route.history_sources[0])
        update_time = latest.get("date") or latest.get("datetime") or latest.get("timestamp")
        return {
            "stock_code": code,
            "stock_name": (history or {}).get("stock_name"),
            "current_price": current_price,
            "change": change,
            "change_percent": change_percent,
            "open": self._float_or_none(latest.get("open")),
            "high": self._float_or_none(latest.get("high")),
            "low": self._float_or_none(latest.get("low")),
            "prev_close": prev_close,
            "volume": self._float_or_none(latest.get("volume")),
            "amount": self._float_or_none(latest.get("amount")),
            "update_time": str(update_time) if update_time is not None else None,
            "source": f"{source_base}_last_close",
            "freshness": "cached",
        }

    def _intelligence_payload(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        indicators: Dict[str, Any],
        trend: Optional[Dict[str, Any]],
        warnings: list[Dict[str, str]],
        a_share_enrichment: Optional[Dict[str, Any]] = None,
        global_equity_enrichment: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        financial_summary, financial_status = self._financial_intelligence_summary(profile, route=route)
        quote_updated_at = quote.get("update_time") if isinstance(quote, dict) else None
        warning_note = " Current market data is degraded." if warnings else ""
        comparison_targets = self._comparison_targets_with_reference_quotes(
            route=route,
            profile=profile,
        )
        return {
            "mode": "no_ai_low_cost",
            "ai_used": False,
            "market_brief": self._market_brief_payload(route=route, profile=profile),
            "free_insights": self._free_insights_payload(
                route=route,
                quote=quote,
                profile=profile,
                indicators=indicators,
                warnings=warnings,
            ),
            "peer_comparison": self._peer_comparison_payload(
                route=route,
                quote=quote,
                profile=profile,
                indicators=indicators,
                comparison_targets=comparison_targets,
            ),
            "signal_score": self._signal_score_payload(
                route=route,
                quote=quote,
                profile=profile,
                indicators=indicators,
                warnings=warnings,
            ),
            "retention_brief": self._retention_brief_payload(
                route=route,
                quote=quote,
                profile=profile,
                indicators=indicators,
                warnings=warnings,
            ),
            "news_center": self._news_center_payload(
                route=route,
                quote=quote,
                profile=profile,
                indicators=indicators,
                warnings=warnings,
                global_equity_enrichment=global_equity_enrichment,
            ),
            "kline_forecast": self._kline_forecast_payload(
                route=route,
                quote=quote,
                indicators=indicators,
                trend=trend,
                warnings=warnings,
            ),
            "a_share_enrichment": a_share_enrichment,
            "global_equity_enrichment": global_equity_enrichment,
            "items": [
                {
                    "category": "news",
                    "title": "News",
                    "summary": (
                        f"No realtime news source is enabled in free no-AI mode for {route.channel}. "
                        f"No AI or public search was used.{warning_note}"
                    ),
                    "status": "degraded",
                    "source": "no_ai_quick_snapshot",
                    "updated_at": quote_updated_at,
                },
                {
                    "category": "announcements",
                    "title": "Announcements",
                    "summary": (
                        f"No filing or announcement source is enabled in free no-AI mode for {route.market.upper()}. "
                        "Deep analysis can add filings, announcements, and source links when configured."
                    ),
                    "status": "degraded",
                    "source": "no_ai_quick_snapshot",
                    "updated_at": quote_updated_at,
                },
                {
                    "category": "financials",
                    "title": "Financial snapshot",
                    "summary": financial_summary,
                    "status": financial_status,
                    "source": (profile or {}).get("source") or route.profile_sources[0] if route.profile_sources else "profile_unavailable",
                    "updated_at": quote_updated_at,
                },
            ],
            "watch_points": self._watch_points_payload(
                route=route,
                quote=quote,
                profile=profile,
                indicators=indicators,
                warnings=warnings,
            ),
            "comparison_targets": comparison_targets,
            "boundary": "Information analysis only; not investment advice.",
        }

    def _a_share_enrichment_payload(
        self,
        *,
        route: MarketRoute,
        code: str,
        stock_name: Optional[str],
        quote: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        indicators: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if route.market != "cn":
            return None
        try:
            return self.a_share_enrichment_service.get_enrichment(
                code,
                stock_name=stock_name,
                profile=profile,
                quote=quote,
                indicators=indicators,
            )
        except Exception:
            return {
                "title": "A-share enrichment",
                "summary": f"{stock_name or code} A-share enrichment is temporarily degraded; the basic quote snapshot remains available.",
                "status": "degraded",
                "source": "a_stock_data_poc_adapter",
                "ai_used": False,
                "public_search_used": False,
                "channels": [],
                "premium_unlock": "Premium can expand announcement, research, fund-flow, sector, and dragon-tiger sources.",
                "boundary": "Information analysis only; not investment advice.",
            }

    def _global_equity_enrichment_payload(
        self,
        *,
        route: MarketRoute,
        code: str,
        stock_name: Optional[str],
        profile: Optional[Dict[str, Any]],
        force_refresh: bool,
    ) -> Optional[Dict[str, Any]]:
        if route.market not in {"us", "hk"}:
            return None
        if self.global_equity_enrichment_service is None:
            return None
        try:
            return self.global_equity_enrichment_service.get_enrichment(
                code,
                market=route.market,
                stock_name=stock_name,
                profile=profile,
                force_refresh=force_refresh,
            )
        except Exception:
            market_label = "US equity" if route.market == "us" else "Hong Kong equity"
            return {
                "title": f"{market_label} public data expansion",
                "summary": (
                    f"{stock_name or code} public information sources are temporarily unavailable; "
                    "the basic quote snapshot remains available."
                ),
                "market": route.market,
                "status": "degraded",
                "source": "global_equity_public_adapter",
                "ai_used": False,
                "public_search_used": False,
                "channels": [],
                "diagnostics": {"cache_hit": False, "errors": [{"channel": "adapter", "error": "unavailable"}]},
                "premium_unlock": "Configured API feeds can add broader coverage and higher refresh limits.",
                "boundary": "Information and data only; not investment advice or a trading instruction.",
            }

    def _retention_brief_payload(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        indicators: Dict[str, Any],
        warnings: list[Dict[str, str]],
    ) -> Dict[str, Any]:
        current_price = self._float_or_none(quote.get("current_price"))
        change_percent = self._float_or_none(quote.get("change_percent"))
        ma5 = self._float_or_none(indicators.get("ma5"))
        ma20 = self._float_or_none(indicators.get("ma20"))
        low = self._float_or_none(quote.get("low"))
        high = self._float_or_none(quote.get("high"))
        sector = str((profile or {}).get("sector") or "").strip()
        industry = str((profile or {}).get("industry") or "").strip()
        context = " / ".join(bit for bit in (sector, industry) if bit) or route.channel.replace("_", " ")

        if current_price is not None and ma20 is not None:
            trend_text = (
                f"above MA20 {self._format_plain_number(ma20)}"
                if current_price >= ma20
                else f"below MA20 {self._format_plain_number(ma20)}"
            )
        elif current_price is not None:
            trend_text = "with incomplete MA20 context"
        else:
            trend_text = "without a reliable latest price"

        change_text = (
            self._format_signed_percent_value(change_percent)
            if change_percent is not None
            else "unknown change"
        )
        support_candidates = [value for value in (low, ma20, ma5) if value is not None]
        resistance_candidates = [value for value in (high, current_price, ma5, ma20) if value is not None]
        support_text = self._format_plain_number(min(support_candidates)) if support_candidates else "unavailable"
        resistance_text = self._format_plain_number(max(resistance_candidates)) if resistance_candidates else "unavailable"
        warning_text = warnings[0].get("message") if warnings else None

        next_steps = [
            f"Refresh once before market action and confirm whether price stays {trend_text}.",
            f"Compare this move with {self._comparison_targets_payload(route=route, profile=profile)[0]['symbol']} instead of reading it alone.",
            "Use deep analysis only when you need news, filings, fundamentals, or a longer AI-written report.",
        ]
        if warning_text:
            next_steps.insert(0, f"Resolve data warning first: {warning_text}")

        return {
            "headline": f"{route.normalized_code} quick read: {change_text}, {trend_text}.",
            "why_it_matters": (
                f"This free snapshot turns quote, moving averages, volume and {context} context "
                "into a first-pass checklist without spending AI quota."
            ),
            "support_resistance": f"support {support_text}; resistance {resistance_text}",
            "next_steps": next_steps[:4],
            "upgrade_hint": "Login to save history, build a watchlist, keep quota state, and unlock deeper analysis when needed.",
            "boundary": "Information analysis only; not investment advice.",
            "source": "no_ai_retention_rules",
        }

    def _news_center_payload(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        indicators: Dict[str, Any],
        warnings: list[Dict[str, str]],
        global_equity_enrichment: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        quote_updated_at = quote.get("update_time") if isinstance(quote, dict) else None
        sector = str((profile or {}).get("sector") or "").strip()
        industry = str((profile or {}).get("industry") or "").strip()
        company_context = " / ".join(bit for bit in (sector, industry) if bit) or route.channel.replace("_", " ")
        current_price = self._format_plain_number(quote.get("current_price"))
        change_percent = self._format_signed_percent_value(quote.get("change_percent"))
        volume_signal = str(indicators.get("volume_price_signal") or "insufficient_data").replace("_", " ")
        financial_summary, financial_status = self._financial_intelligence_summary(profile, route=route)

        if route.market == "crypto":
            announcement_title = "Protocol and exchange events"
            announcement_summary = (
                "Equity filings do not apply to crypto. Free mode keeps an event lane for exchange notices, "
                "protocol risk, liquidity shifts, and regulatory headlines when configured."
            )
        elif route.market == "cn":
            announcement_title = "Announcements lane"
            announcement_summary = (
                "A-share announcements and exchange filings are reserved for configured deep sources. "
                "Free mode keeps the lane visible so users know what deeper analysis will add."
            )
        elif route.market == "hk":
            announcement_title = "HKEX filings lane"
            announcement_summary = (
                "Hong Kong filings and corporate actions are reserved for configured deep sources. "
                "Free mode shows the lane without public search calls."
            )
        else:
            announcement_title = "SEC filings lane"
            announcement_summary = (
                "SEC filings, earnings call notes, and source links are reserved for deep mode or configured feeds. "
                "Free mode avoids public search and AI cost."
            )

        items: list[Dict[str, Any]] = [
            {
                "category": "news",
                "title": "Market-moving news lane",
                "summary": (
                    f"{route.normalized_code} is at {current_price} with {change_percent}. "
                    "Realtime public news/search is off in free local mode, so this lane is a checklist placeholder."
                ),
                "status": "degraded",
                "source": "no_ai_news_center_rules",
                "action": "Use deep analysis or configured news feeds for realtime links.",
                "updated_at": quote_updated_at,
            },
            {
                "category": "announcements",
                "title": announcement_title,
                "summary": announcement_summary,
                "status": "degraded",
                "source": "no_ai_news_center_rules",
                "action": "Upgrade or configure a filings source when source links are required.",
                "updated_at": quote_updated_at,
            },
            {
                "category": "financials",
                "title": "Financial snapshot lane",
                "summary": financial_summary,
                "status": financial_status,
                "source": (profile or {}).get("source") or "profile_unavailable",
                "action": "Compare valuation and fundamentals before relying on price action alone.",
                "updated_at": quote_updated_at,
            },
            {
                "category": "sector",
                "title": "Sector and peer lane",
                "summary": (
                    f"Context is {company_context}. Current volume-price signal is {volume_signal}. "
                    "Compare against route-based peers before reading this symbol in isolation."
                ),
                "status": "available" if company_context else "degraded",
                "source": "no_ai_news_center_rules",
                "action": "Open peer comparison or deep sector view for richer cross-asset context.",
                "updated_at": quote_updated_at,
            },
        ]
        if global_equity_enrichment:
            real_items: list[Dict[str, Any]] = []
            for channel in global_equity_enrichment.get("channels") or []:
                category = str(channel.get("category") or "information")
                channel_items = channel.get("items") or []
                for source_item in channel_items[:2]:
                    if not isinstance(source_item, dict) or not source_item.get("title"):
                        continue
                    real_items.append(
                        {
                            "category": "announcements" if category == "filings" else category,
                            "title": str(source_item.get("title")),
                            "summary": str(source_item.get("summary") or channel.get("summary") or "Source data available."),
                            "status": "available",
                            "source": str(source_item.get("source") or channel.get("source") or "global_equity_public_adapter"),
                            "action": str(channel.get("action") or "Open the source and confirm its timestamp."),
                            "updated_at": source_item.get("published_at") or global_equity_enrichment.get("updated_at"),
                            "url": source_item.get("url"),
                        }
                    )
                if not channel_items and category == "filings":
                    real_items.append(
                        {
                            "category": "announcements",
                            "title": str(channel.get("title") or announcement_title),
                            "summary": str(channel.get("summary") or announcement_summary),
                            "status": str(channel.get("status") or "degraded"),
                            "source": str(channel.get("source") or "global_equity_public_adapter"),
                            "action": str(channel.get("action") or "Confirm through the official filing source."),
                            "updated_at": global_equity_enrichment.get("updated_at"),
                            "url": channel.get("official_url"),
                        }
                    )
            if real_items:
                retained = [item for item in items if item["category"] not in {"news", "announcements"}]
                items = real_items + retained
        if warnings:
            items.append(
                {
                    "category": "data_quality",
                    "title": "Data quality lane",
                    "summary": warnings[0].get("message") or "Market data is degraded; refresh before comparing signals.",
                    "status": "degraded",
                    "source": "no_ai_news_center_rules",
                    "action": "Refresh market data before treating the quick snapshot as current.",
                    "updated_at": quote_updated_at,
                }
            )
        return {
            "title": "Public information center" if global_equity_enrichment else "Local news center",
            "summary": (
                (
                    f"{route.normalized_code} direct public-source lanes include linked news, filing status, "
                    "financial facts, sector context, and data quality. No AI or general web search was used."
                    if global_equity_enrichment
                    else f"{route.normalized_code} information lanes for {company_context}: news, announcements, "
                    "financials, sector context, and data quality. No AI or public search was used."
                )
            ),
            "items": items,
            "source": "global_equity_public_adapter" if global_equity_enrichment else "no_ai_news_center_rules",
            "ai_used": False,
            "public_search_used": False,
            "premium_unlock": (
                "Premium can use configured API feeds for broader coverage and higher refresh limits; "
                "the visible module structure remains the same."
                if global_equity_enrichment
                else "Premium can add realtime news, filings, source links, sector comparison, and AI summaries."
            ),
            "boundary": "Information and data only; not investment advice or a trading instruction.",
        }

    def _kline_forecast_payload(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        indicators: Dict[str, Any],
        trend: Optional[Dict[str, Any]],
        warnings: list[Dict[str, str]],
    ) -> Dict[str, Any]:
        current_price = self._float_or_none(quote.get("current_price"))
        ma5 = self._float_or_none(indicators.get("ma5"))
        ma10 = self._float_or_none(indicators.get("ma10"))
        ma20 = self._float_or_none(indicators.get("ma20"))
        low = self._float_or_none(quote.get("low"))
        high = self._float_or_none(quote.get("high"))
        change_percent = self._float_or_none(quote.get("change_percent"))
        change_5d = self._float_or_none(indicators.get("price_change_5d"))
        change_20d = self._float_or_none(indicators.get("price_change_20d"))
        volume_change = self._float_or_none(indicators.get("volume_change_vs_ma5"))
        trend_change = self._float_or_none((trend or {}).get("change_percent"))
        score = 50

        if current_price is None:
            score -= 18
        if current_price is not None and ma20 is not None:
            score += 14 if current_price >= ma20 else -14
        if current_price is not None and ma5 is not None:
            score += 8 if current_price >= ma5 else -8
        if change_percent is not None:
            score += 6 if change_percent > 0 else -6
        if change_5d is not None:
            score += 8 if change_5d > 0 else -7
        if change_20d is not None:
            score += 6 if change_20d > 0 else -5
        if trend_change is not None:
            score += 5 if trend_change > 0 else -4
        if volume_change is not None:
            score += 5 if volume_change >= 20 else (-3 if volume_change <= -20 else 0)
        if warnings:
            score -= 10
        score = max(5, min(95, int(round(score))))

        if current_price is None or ma20 is None:
            direction = "insufficient_data"
            label = "Insufficient K-line context"
        elif score >= 62:
            direction = "upside_bias"
            label = "Upside-biased preview"
        elif score <= 38:
            direction = "downside_risk"
            label = "Downside-risk preview"
        else:
            direction = "range_watch"
            label = "Range-watch preview"

        confidence = max(35, min(85, 40 + abs(score - 50)))
        support_candidates = [value for value in (low, ma20, ma10, ma5) if value is not None]
        resistance_candidates = [value for value in (high, current_price, ma5, ma10, ma20) if value is not None]
        support = min(support_candidates) if support_candidates else None
        resistance = max(resistance_candidates) if resistance_candidates else None
        support_text = self._format_plain_number(support)
        resistance_text = self._format_plain_number(resistance)
        ma20_text = self._format_plain_number(ma20)
        volume_text = self._format_signed_percent_value(volume_change)

        bullish_probability = max(10, min(80, score))
        bearish_probability = max(10, min(75, 100 - score))
        range_probability = max(20, min(70, 100 - abs(score - 50)))
        scenarios = [
            {
                "label": label,
                "direction": direction,
                "probability": int(bullish_probability if direction == "upside_bias" else range_probability),
                "trigger": f"Hold above MA20 {ma20_text} and keep volume change near {volume_text}.",
                "detail": (
                    f"Local rules read support near {support_text} and resistance near {resistance_text}. "
                    "This is not Kronos inference."
                ),
            },
            {
                "label": "Breakout confirmation",
                "direction": "upside_bias",
                "probability": int(max(15, min(75, score + 8))),
                "trigger": f"Price closes above resistance {resistance_text} with expanding volume.",
                "detail": "Treat this as a checklist for the next refresh, not a trade instruction.",
            },
            {
                "label": "Pullback risk",
                "direction": "downside_risk",
                "probability": int(bearish_probability),
                "trigger": f"Price loses support {support_text} or data freshness degrades.",
                "detail": "Recheck source freshness and broad-market references before interpreting weakness.",
            },
        ]
        return {
            "title": "K-line forecast lab",
            "horizon": "next_5_bars",
            "direction": direction,
            "confidence": int(confidence),
            "support": support,
            "resistance": resistance,
            "scenarios": scenarios,
            "adapter_status": "Kronos adapter ready; local rules preview only; Kronos model not installed or invoked.",
            "source": "local_kline_rules_kronos_ready",
            "ai_used": False,
            "kronos_model_used": False,
            "premium_unlock": "Premium can run a configured Kronos or local-model forecast lane after model/data approval.",
            "boundary": "Experimental model preview; information analysis only; not investment advice.",
        }

    def _peer_comparison_payload(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        indicators: Dict[str, Any],
        comparison_targets: Optional[list[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        targets = comparison_targets or self._comparison_targets_payload(route=route, profile=profile)
        current_signal = self._current_signal_summary(route=route, quote=quote, indicators=indicators)
        target_symbols = ", ".join(target["symbol"] for target in targets) if targets else route.data_source_lane
        rows = []
        for target in targets:
            row = {
                "symbol": target["symbol"],
                "label": target["label"],
                "role": self._comparison_role_for_target(target=target, route=route),
                "reason": target["reason"],
                "current_signal": current_signal,
                "compare_next": (
                    f"Check whether {route.normalized_code} confirms faster or weaker than "
                    f"{target['symbol']} on the next refresh."
                ),
                "source": "no_ai_route_rules",
            }
            reference_quote = target.get("reference_quote")
            if isinstance(reference_quote, dict):
                row["reference_quote"] = reference_quote
            rows.append(row)
        return {
            "title": "Peer and market comparison",
            "summary": f"Compare {route.normalized_code} against {target_symbols} before reading it in isolation.",
            "rows": rows,
        }

    def _signal_score_payload(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        indicators: Dict[str, Any],
        warnings: list[Dict[str, str]],
    ) -> Dict[str, Any]:
        current_price = self._float_or_none(quote.get("current_price"))
        ma5 = self._float_or_none(indicators.get("ma5"))
        ma20 = self._float_or_none(indicators.get("ma20"))
        freshness = str(quote.get("freshness") or "unavailable")
        signal = str(indicators.get("volume_price_signal") or "insufficient_data")
        volume_change = self._float_or_none(indicators.get("volume_change_vs_ma5"))

        if current_price is None or ma20 is None:
            trend_score = 35
            trend_status = "missing"
            trend_detail = "Trend score is limited because latest price or MA20 is unavailable."
        elif ma5 is not None and current_price >= ma5 and current_price >= ma20:
            trend_score = 90
            trend_status = "positive"
            trend_detail = (
                f"Price {self._format_plain_number(current_price)} is above MA5 "
                f"{self._format_plain_number(ma5)} and MA20 {self._format_plain_number(ma20)}."
            )
        elif current_price >= ma20:
            trend_score = 74
            trend_status = "positive"
            trend_detail = f"Price holds above MA20 {self._format_plain_number(ma20)}, but short-term confirmation is mixed."
        elif ma5 is not None and current_price >= ma5:
            trend_score = 58
            trend_status = "neutral"
            trend_detail = f"Price is above MA5 {self._format_plain_number(ma5)} but below MA20 {self._format_plain_number(ma20)}."
        else:
            trend_score = 42
            trend_status = "warning"
            trend_detail = f"Price is below MA20 {self._format_plain_number(ma20)}; trend repair still needs confirmation."

        volume_detail_suffix = (
            f" Volume is {self._format_signed_percent_value(volume_change)} versus MA5."
            if volume_change is not None
            else ""
        )
        if signal == "price_volume_confirmed":
            volume_score = 84
            volume_status = "positive"
            volume_detail = "Price and volume confirm each other in the quick rules." + volume_detail_suffix
        elif signal == "price_above_trend_volume_soft":
            volume_score = 66
            volume_status = "neutral"
            volume_detail = "Price is above trend, while volume confirmation is still soft." + volume_detail_suffix
        elif signal == "volume_expanded_price_below_trend":
            volume_score = 54
            volume_status = "warning"
            volume_detail = "Volume expanded while price remains below trend, so confirmation is mixed." + volume_detail_suffix
        elif signal == "neutral":
            volume_score = 50
            volume_status = "neutral"
            volume_detail = "Volume-price behavior is neutral in the quick rules." + volume_detail_suffix
        else:
            volume_score = 34
            volume_status = "missing"
            volume_detail = "Volume-price score is limited because recent volume history is incomplete."

        freshness_scores = {
            "fresh": (100, "positive", "Quote data is fresh for this quick snapshot."),
            "cached": (76, "neutral", "Quote data came from cache; refresh before comparing intraday moves."),
            "stale": (45, "warning", "Quote data is stale; treat the quick signal as provisional."),
            "unavailable": (20, "missing", "Latest quote is unavailable; signal confidence is limited."),
        }
        freshness_score, freshness_status, freshness_detail = freshness_scores.get(
            freshness,
            (40, "warning", f"Quote freshness is {freshness}; confirm data before comparing signals."),
        )
        if warnings:
            freshness_score = max(0, freshness_score - 10)
            freshness_status = "warning" if freshness_status == "positive" else freshness_status
            freshness_detail = f"{freshness_detail} {warnings[0].get('message') or 'A data warning is present.'}"

        if route.market == "crypto":
            profile_score = 72
            profile_status = "neutral"
            profile_detail = "Crypto assets do not use stock fundamentals; quick context uses market lane and quote data."
        elif profile and self._has_profile_content(profile):
            profile_fields = [
                "sector",
                "industry",
                "market_cap",
                "pe_ratio",
                "pb_ratio",
                "dividend_yield",
                "revenue",
                "net_profit",
            ]
            available_fields = sum(1 for field in profile_fields if profile.get(field) not in (None, ""))
            profile_score = min(100, 55 + available_fields * 7)
            profile_status = "positive" if profile_score >= 76 else "neutral"
            context = " / ".join(
                str(value) for value in (profile.get("sector"), profile.get("industry")) if value not in (None, "")
            )
            profile_detail = context or "Company profile has usable valuation or financial fields."
        elif profile:
            profile_score = 52
            profile_status = "neutral"
            profile_detail = "Basic company name is available, but valuation and sector fields are limited."
        else:
            profile_score = 34
            profile_status = "missing"
            profile_detail = "Company profile is unavailable in quick mode; deep mode can add fuller context."

        components = [
            {
                "key": "trend",
                "label": "Trend",
                "score": trend_score,
                "status": trend_status,
                "detail": trend_detail,
            },
            {
                "key": "volume",
                "label": "Volume",
                "score": volume_score,
                "status": volume_status,
                "detail": volume_detail,
            },
            {
                "key": "freshness",
                "label": "Data freshness",
                "score": freshness_score,
                "status": freshness_status,
                "detail": freshness_detail,
            },
            {
                "key": "profile",
                "label": "Profile completeness",
                "score": profile_score,
                "status": profile_status,
                "detail": profile_detail,
            },
        ]
        weights = {
            "trend": 0.36,
            "volume": 0.24,
            "freshness": 0.25,
            "profile": 0.15,
        }
        score = int(round(sum(component["score"] * weights[component["key"]] for component in components)))
        score = max(0, min(100, score))
        if score >= 80:
            label = "Strong quick signal"
        elif score >= 65:
            label = "Constructive quick signal"
        elif score >= 50:
            label = "Mixed quick signal"
        else:
            label = "Weak quick signal"
        return {
            "score": score,
            "label": label,
            "summary": (
                f"{route.normalized_code} signal is {score}/100 from trend, volume, "
                "data freshness, and profile completeness. No AI or public search was used."
            ),
            "components": components,
            "source": "no_ai_rules",
            "ai_used": False,
        }

    def _current_signal_summary(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        indicators: Dict[str, Any],
    ) -> str:
        current_price = self._float_or_none(quote.get("current_price"))
        change_percent = self._float_or_none(quote.get("change_percent"))
        ma20 = self._float_or_none(indicators.get("ma20"))
        volume_signal = str(indicators.get("volume_price_signal") or "insufficient_data").replace("_", " ")
        if current_price is not None and ma20 is not None:
            trend = "above MA20" if current_price >= ma20 else "below MA20"
        else:
            trend = "with incomplete MA20 context"
        change_text = self._format_signed_percent_value(change_percent) if change_percent is not None else "unknown change"
        return f"{route.normalized_code} is {trend} with {change_text}; volume signal is {volume_signal}."

    def _comparison_role_for_target(self, *, target: Dict[str, str], route: MarketRoute) -> str:
        symbol = str(target.get("symbol") or "")
        label = str(target.get("label") or "").lower()
        reason = str(target.get("reason") or "").lower()
        if "sector" in label or "sector" in reason or symbol in {"XLK", "2800.HK"}:
            return "Sector lens"
        if symbol.startswith("^") or "index" in label or "composite" in label or "300" in symbol:
            return "Index lens"
        if route.market == "crypto" or "crypto" in reason:
            return "Crypto beta"
        return "Broad market"

    def _free_insights_payload(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        indicators: Dict[str, Any],
        warnings: list[Dict[str, str]],
    ) -> list[Dict[str, Any]]:
        movement = self._movement_free_insight(quote=quote, indicators=indicators)
        peer_context = self._peer_context_free_insight(route=route, profile=profile)
        risk = self._risk_free_insight(route=route, quote=quote, warnings=warnings)
        return [movement, peer_context, risk]

    def _movement_free_insight(
        self,
        *,
        quote: Dict[str, Any],
        indicators: Dict[str, Any],
    ) -> Dict[str, Any]:
        current_price = self._float_or_none(quote.get("current_price"))
        change_percent = self._float_or_none(quote.get("change_percent"))
        ma20 = self._float_or_none(indicators.get("ma20"))
        volume_change = self._float_or_none(indicators.get("volume_change_vs_ma5"))
        signal = str(indicators.get("volume_price_signal") or "insufficient_data")

        move_text = (
            f"price changed {self._format_signed_percent_value(change_percent)}"
            if change_percent is not None
            else "latest intraday change is unavailable"
        )
        if current_price is not None and ma20 is not None:
            trend_text = (
                f"holds above MA20 {self._format_plain_number(ma20)}"
                if current_price >= ma20
                else f"stays below MA20 {self._format_plain_number(ma20)}"
            )
        else:
            trend_text = "MA20 context is incomplete"

        if volume_change is None:
            volume_text = "volume confirmation is incomplete"
        else:
            volume_text = f"volume is {self._format_signed_percent_value(volume_change)} versus MA5"

        if signal == "price_volume_confirmed":
            tone = "positive"
        elif signal in {"volume_expanded_price_below_trend", "neutral"}:
            tone = "warning"
        elif signal == "price_above_trend_volume_soft":
            tone = "neutral"
        else:
            tone = "info"

        return {
            "category": "movement",
            "title": "Move explanation",
            "summary": f"Today's quick read: {move_text}, {trend_text}, and {volume_text}.",
            "tone": tone,
            "bullets": [
                f"Last price {self._format_plain_number(current_price)}",
                trend_text,
                volume_text,
            ],
            "source": "no_ai_rules",
        }

    def _peer_context_free_insight(
        self,
        *,
        route: MarketRoute,
        profile: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        targets = self._comparison_targets_payload(route=route, profile=profile)
        symbols = [item["symbol"] for item in targets[:3]]
        sector = str((profile or {}).get("sector") or "").strip()
        industry = str((profile or {}).get("industry") or "").strip()
        context_bits = [bit for bit in (sector, industry) if bit]
        context_text = " / ".join(context_bits) if context_bits else route.channel.replace("_", " ")
        target_text = ", ".join(symbols) if symbols else route.data_source_lane
        return {
            "category": "peer_context",
            "title": "Peer context",
            "summary": f"Read this move against {target_text}; quick profile context is {context_text}.",
            "tone": "info",
            "bullets": symbols or [route.data_source_lane],
            "source": "no_ai_route_rules",
        }

    def _risk_free_insight(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        warnings: list[Dict[str, str]],
    ) -> Dict[str, Any]:
        if warnings:
            warning_messages = [item.get("message") for item in warnings if item.get("message")]
            risk_summary = "Data warning: " + " ".join(warning_messages[:2])
            tone = "warning"
        else:
            freshness = quote.get("freshness") or "fresh"
            risk_summary = (
                f"No-AI quick view for {route.channel}: quote freshness is {freshness}; "
                "realtime news, filings, external search, and investment advice are not included."
            )
            tone = "info"
        return {
            "category": "risk",
            "title": "Key risks",
            "summary": risk_summary,
            "tone": tone,
            "bullets": [
                f"Lane {route.data_source_lane}",
                "No AI used",
                "Information analysis only",
            ],
            "source": "no_ai_rules",
        }

    def _market_brief_payload(
        self,
        *,
        route: MarketRoute,
        profile: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if route.market == "cn":
            return {
                "market": "cn",
                "title": "A-share quick view",
                "summary": "A-share lane focuses on quote, moving averages, volume-price behavior, and broad-market context without AI.",
                "lane": route.data_source_lane,
                "focus_points": [
                    "Price versus MA20",
                    "Volume confirmation",
                    "CSI 300 and SSE Composite context",
                    "Announcements require deep mode or configured sources",
                ],
                "deep_unlock": "Deep analysis can add announcements, fundamentals, sector flow, and longer AI report.",
            }
        if route.market == "hk":
            return {
                "market": "hk",
                "title": "Hong Kong equity quick view",
                "summary": "Hong Kong lane focuses on quote, trend, liquidity, and Hang Seng context without AI.",
                "lane": route.data_source_lane,
                "focus_points": [
                    "Price versus MA20",
                    "Volume confirmation",
                    "Hang Seng and Hong Kong ETF context",
                    "Company filings require deep mode or configured sources",
                ],
                "deep_unlock": "Deep analysis can add Hong Kong filings, news, sector comparison, and AI interpretation.",
            }
        if route.market == "crypto":
            return {
                "market": "crypto",
                "title": "Crypto quick view",
                "summary": "Crypto lane focuses on 24/7 price action, trend, volume behavior, and BTC/ETH context without stock fundamentals.",
                "lane": route.data_source_lane,
                "focus_points": [
                    "Price versus MA20",
                    "Volume confirmation",
                    "BTC and ETH market beta context",
                    "Equity filings and financial statements do not apply",
                ],
                "deep_unlock": "Deep analysis can add crypto news, risk events, liquidity context, and AI interpretation when configured.",
            }
        sector = str((profile or {}).get("sector") or "").strip()
        sector_focus = "Nasdaq and sector ETF context" if sector else "Nasdaq context"
        return {
            "market": "us",
            "title": "US equity quick view",
            "summary": "US equity lane uses quote, history, profile, Nasdaq and sector references without AI.",
            "lane": route.data_source_lane,
            "focus_points": [
                "Price versus MA20",
                "Volume confirmation",
                sector_focus,
                "Filings and full news require deep mode or configured sources",
            ],
            "deep_unlock": "Deep analysis can add news, filings, sector comparison, and AI report.",
        }

    def _watch_points_payload(
        self,
        *,
        route: MarketRoute,
        quote: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        indicators: Dict[str, Any],
        warnings: list[Dict[str, str]],
    ) -> list[Dict[str, str]]:
        current_price = self._float_or_none(quote.get("current_price"))
        ma5 = self._float_or_none(indicators.get("ma5"))
        ma20 = self._float_or_none(indicators.get("ma20"))
        volume_change = self._float_or_none(indicators.get("volume_change_vs_ma5"))
        watch_points: list[Dict[str, str]] = []

        if current_price is not None and ma20 is not None:
            if current_price >= ma20:
                watch_points.append(
                    {
                        "category": "trend",
                        "title": "Trend confirmation",
                        "detail": f"Watch whether price can hold above MA20 {self._format_plain_number(ma20)} after the next refresh.",
                        "priority": "high",
                        "source": "no_ai_rules",
                    }
                )
            else:
                watch_points.append(
                    {
                        "category": "trend",
                        "title": "Trend repair",
                        "detail": f"Watch whether price can reclaim MA20 {self._format_plain_number(ma20)} before treating the structure as repaired.",
                        "priority": "high",
                        "source": "no_ai_rules",
                    }
                )
        elif current_price is not None and ma5 is not None:
            watch_points.append(
                {
                    "category": "trend",
                    "title": "Short trend check",
                    "detail": f"MA20 is incomplete; watch whether price stays near MA5 {self._format_plain_number(ma5)}.",
                    "priority": "medium",
                    "source": "no_ai_rules",
                }
            )
        else:
            watch_points.append(
                {
                    "category": "trend",
                    "title": "Trend data check",
                    "detail": "Moving-average context is incomplete; refresh market data before comparing trend structure.",
                    "priority": "medium",
                    "source": "no_ai_rules",
                }
            )

        if volume_change is None:
            volume_detail = "Volume confirmation is incomplete; watch the next refresh for volume versus MA5."
            volume_priority = "medium"
        elif volume_change >= 20:
            volume_detail = f"Volume is {self._format_percent_value(volume_change)} versus MA5; watch if price also confirms the move."
            volume_priority = "high"
        elif volume_change <= -20:
            volume_detail = f"Volume is {self._format_percent_value(volume_change)} versus MA5; momentum confirmation is weaker."
            volume_priority = "medium"
        else:
            volume_detail = f"Volume is {self._format_percent_value(volume_change)} versus MA5; watch for expansion before upgrading confidence."
            volume_priority = "low"
        watch_points.append(
            {
                "category": "volume",
                "title": "Volume confirmation",
                "detail": volume_detail,
                "priority": volume_priority,
                "source": "no_ai_rules",
            }
        )

        if warnings:
            risk_detail = warnings[0].get("message") or "Market data has a degradation warning; refresh before comparing decisions."
            risk_priority = "high" if any(item.get("severity") == "error" for item in warnings) else "medium"
        else:
            risk_detail = "Keep the analysis informational, confirm source freshness, and treat this as a no-AI quick view."
            risk_priority = "medium"
        watch_points.append(
            {
                "category": "risk",
                "title": "Risk boundary",
                "detail": risk_detail,
                "priority": risk_priority,
                "source": "no_ai_rules",
            }
        )

        if profile:
            profile_bits = [profile.get("sector"), profile.get("industry")]
            profile_context = " / ".join(str(bit) for bit in profile_bits if bit)
            watch_points.append(
                {
                    "category": "fundamentals",
                    "title": "Profile context",
                    "detail": profile_context or "Company profile is available; compare valuation fields before relying on price signals alone.",
                    "priority": "low",
                    "source": "no_ai_rules",
                }
            )
        else:
            watch_points.append(
                {
                    "category": "fundamentals",
                    "title": "Profile gap",
                    "detail": f"{route.channel} company profile is unavailable in quick mode; deep analysis can add fuller fundamentals.",
                    "priority": "low",
                    "source": "no_ai_rules",
                }
            )
        return watch_points

    def _comparison_targets_payload(
        self,
        *,
        route: MarketRoute,
        profile: Optional[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        targets: list[Dict[str, str]]
        if route.market == "cn":
            targets = [
                {"label": "CSI 300", "symbol": "000300.SH", "reason": "A-share broad-market reference."},
                {"label": "SSE Composite", "symbol": "000001.SH", "reason": "A-share market sentiment reference."},
            ]
        elif route.market == "hk":
            targets = [
                {"label": "Hang Seng Index", "symbol": "^HSI", "reason": "Hong Kong market reference."},
                {"label": "Tracker Fund", "symbol": "2800.HK", "reason": "Hong Kong ETF market context."},
            ]
        elif route.market == "crypto":
            targets = [
                {"label": "Bitcoin", "symbol": "BTC-USD", "reason": "Crypto market beta reference."},
                {"label": "Ethereum", "symbol": "ETH-USD", "reason": "Large-cap crypto rotation reference."},
            ]
        else:
            targets = [
                {"label": "QQQ", "symbol": "QQQ", "reason": "US growth and technology benchmark."},
                {"label": "Nasdaq Composite", "symbol": "^IXIC", "reason": "US market index context."},
            ]
            sector = str((profile or {}).get("sector") or "").lower()
            if "technology" in sector:
                targets.append(
                    {"label": "Technology sector ETF", "symbol": "XLK", "reason": "Sector context for Technology names."}
                )
        return [
            {
                **target,
                "status": "reference_only",
                "source": "no_ai_route_rules",
            }
            for target in targets
        ]

    def _comparison_targets_with_reference_quotes(
        self,
        *,
        route: MarketRoute,
        profile: Optional[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        targets = self._comparison_targets_payload(route=route, profile=profile)
        quote_map = self._reference_quote_payloads_for_targets(targets[:3])
        enriched: list[Dict[str, Any]] = []
        for target in targets:
            payload = dict(target)
            reference_quote = quote_map.get(str(target.get("symbol") or ""))
            if reference_quote:
                payload["reference_quote"] = reference_quote
            enriched.append(payload)
        return enriched

    def _reference_quote_payloads_for_targets(
        self,
        targets: Iterable[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        target_list = [target for target in targets if target.get("symbol")]
        if not target_list:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        pending: Dict[concurrent.futures.Future, tuple[str, MarketRoute, float]] = {}

        for target in target_list:
            symbol = str(target.get("symbol") or "").strip()
            if not symbol:
                continue
            target_route = self._resolve_route(symbol)
            cache_key = f"quote:{target_route.normalized_code}"
            hit = self.cache.get(cache_key)
            if hit is not None:
                source = self._payload_source(hit.value, hit.source or target_route.quote_sources[0])
                results[symbol] = self._reference_quote_payload(
                    hit.value,
                    freshness=hit.freshness,
                    source=source,
                    status="available",
                )
                continue
            source_id = target_route.quote_sources[0]
            if self.source_health.should_skip(source_id):
                results[symbol] = self._unavailable_reference_quote_payload(
                    source=source_id,
                    error="cooling_down",
                )
                continue
            started = time.perf_counter()
            future = _BASIC_QUERY_FETCH_EXECUTOR.submit(self._fetch_reference_quote, target_route.normalized_code)
            pending[future] = (symbol, target_route, started)

        if pending:
            done, not_done = concurrent.futures.wait(
                pending,
                timeout=self.reference_quote_timeout_seconds,
                return_when=concurrent.futures.ALL_COMPLETED,
            )
            for future in not_done:
                future.cancel()
                symbol, target_route, started = pending[future]
                elapsed_ms = self._elapsed_ms(started)
                self.source_health.record_timeout(target_route.quote_sources[0], elapsed_ms=elapsed_ms)
                results[symbol] = self._unavailable_reference_quote_payload(
                    source=target_route.quote_sources[0],
                    error="timeout",
                )
            for future in done:
                symbol, target_route, started = pending[future]
                source_id = target_route.quote_sources[0]
                elapsed_ms = self._elapsed_ms(started)
                try:
                    quote = future.result()
                except Exception:
                    quote = None
                if isinstance(quote, dict) and quote:
                    quote = dict(quote)
                    quote.setdefault("source", source_id)
                    self.cache.set(
                        f"quote:{target_route.normalized_code}",
                        quote,
                        source=quote.get("source") or source_id,
                    )
                    self.source_health.record_success(source_id, elapsed_ms=elapsed_ms)
                    results[symbol] = self._reference_quote_payload(
                        quote,
                        freshness=str(quote.get("freshness") or "fresh"),
                        source=str(quote.get("source") or source_id),
                        status="available",
                    )
                else:
                    self.source_health.record_error(source_id, elapsed_ms=elapsed_ms)
                    results[symbol] = self._unavailable_reference_quote_payload(
                        source=source_id,
                        error="unavailable",
                    )
        return results

    def _fetch_reference_quote(self, code: str) -> Optional[Dict[str, Any]]:
        quote = self.stock_service.get_realtime_quote(code)
        if isinstance(quote, dict) and self._float_or_none(quote.get("current_price")) is not None:
            return quote
        yahoo_quote = self._fetch_reference_quote_from_yahoo_chart(code)
        if yahoo_quote:
            return yahoo_quote
        return quote if isinstance(quote, dict) else None

    def _fetch_reference_quote_from_yahoo_chart(self, code: str) -> Optional[Dict[str, Any]]:
        symbol = self._yahoo_reference_symbol(code)
        if not symbol:
            return None
        encoded = urllib.parse.quote(symbol, safe="")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1d&range=5d"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 DSA local free reference quote"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.reference_quote_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

        result = (((payload or {}).get("chart") or {}).get("result") or [None])[0]
        if not isinstance(result, dict):
            return None
        meta = result.get("meta") or {}
        indicators = result.get("indicators") or {}
        quote_rows = indicators.get("quote") or []
        quote_row = quote_rows[0] if quote_rows and isinstance(quote_rows[0], dict) else {}
        closes = [self._float_or_none(value) for value in (quote_row.get("close") or [])]
        closes = [value for value in closes if value is not None]
        current_price = self._float_or_none(meta.get("regularMarketPrice"))
        if current_price is None and closes:
            current_price = closes[-1]
        previous_close = self._float_or_none(meta.get("chartPreviousClose") or meta.get("previousClose"))
        if previous_close is None and len(closes) >= 2:
            previous_close = closes[-2]
        change = None
        change_percent = None
        if current_price is not None and previous_close not in (None, 0):
            change = round(current_price - previous_close, 4)
            change_percent = round((change / previous_close) * 100, 4)
        timestamps = result.get("timestamp") or []
        update_time = str(timestamps[-1]) if timestamps else None
        if current_price is None:
            return None
        return {
            "stock_code": code,
            "stock_name": meta.get("longName") or meta.get("shortName") or symbol,
            "current_price": current_price,
            "change": change,
            "change_percent": change_percent,
            "volume": (quote_row.get("volume") or [None])[-1] if quote_row.get("volume") else None,
            "amount": None,
            "update_time": update_time,
            "source": "yahoo_chart_reference",
            "freshness": "fresh",
        }

    def _yahoo_reference_symbol(self, code: str) -> str:
        raw = (code or "").strip()
        upper = raw.upper()
        if upper.endswith(".SH"):
            return f"{raw[:-3]}.SS"
        if upper.startswith("SH") and upper[2:].isdigit():
            return f"{upper[2:]}.SS"
        if upper.startswith("HK") and upper[2:].isdigit():
            return f"{int(upper[2:]):04d}.HK"
        if upper.endswith(".HK"):
            stem = upper[:-3]
            if stem.isdigit():
                return f"{int(stem):04d}.HK"
        return raw

    def _reference_quote_payload(
        self,
        quote: Optional[Dict[str, Any]],
        *,
        freshness: str,
        source: str,
        status: str,
    ) -> Dict[str, Any]:
        if not quote:
            return self._unavailable_reference_quote_payload(source=source, error="unavailable")
        normalized_freshness = freshness if freshness in {"fresh", "cached", "stale", "unavailable"} else "fresh"
        current_price = self._float_or_none(quote.get("current_price"))
        return {
            "stock_name": quote.get("stock_name") or quote.get("name"),
            "current_price": current_price,
            "price": current_price,
            "change": self._float_or_none(quote.get("change")),
            "change_percent": self._float_or_none(quote.get("change_percent")),
            "volume": self._float_or_none(quote.get("volume")),
            "amount": self._float_or_none(quote.get("amount")),
            "update_time": str(quote.get("update_time")) if quote.get("update_time") is not None else None,
            "freshness": normalized_freshness,
            "source": source or "reference_quote",
            "status": status,
        }

    def _unavailable_reference_quote_payload(self, *, source: str, error: str) -> Dict[str, Any]:
        return {
            "current_price": None,
            "price": None,
            "change": None,
            "change_percent": None,
            "volume": None,
            "amount": None,
            "update_time": None,
            "freshness": "unavailable",
            "source": source or "reference_quote",
            "status": "unavailable",
            "error": error,
        }

    def _financial_intelligence_summary(self, profile: Optional[Dict[str, Any]], *, route: MarketRoute) -> tuple[str, str]:
        if route.market == "crypto":
            return (
                "Equity financial statements do not apply to crypto assets; use trend, liquidity, and risk-event context instead.",
                "unavailable",
            )
        if not profile:
            return (
                "Company fundamentals are unavailable in this quick snapshot; free no-AI mode keeps the query fast.",
                "unavailable",
            )
        parts: list[str] = []
        market_cap = self._format_compact_number(profile.get("market_cap"))
        if market_cap != "-":
            parts.append(f"Market cap {market_cap}")
        pe_ratio = self._format_plain_number(profile.get("pe_ratio"))
        if pe_ratio != "-":
            parts.append(f"PE {pe_ratio}")
        pb_ratio = self._format_plain_number(profile.get("pb_ratio"))
        if pb_ratio != "-":
            parts.append(f"PB {pb_ratio}")
        dividend_yield = self._format_percent_value(profile.get("dividend_yield"))
        if dividend_yield != "-":
            parts.append(f"dividend yield {dividend_yield}")
        revenue = self._format_compact_number(profile.get("revenue"))
        if revenue != "-":
            parts.append(f"revenue {revenue}")
        net_profit = self._format_compact_number(profile.get("net_profit"))
        if net_profit != "-":
            parts.append(f"net profit {net_profit}")
        if not parts:
            return (
                "Company profile exists, but key valuation and financial fields are unavailable in quick mode.",
                "degraded",
            )
        return "; ".join(parts) + ".", "available"

    def _format_compact_number(self, value: Any) -> str:
        number = self._float_or_none(value)
        if number is None:
            return "-"
        absolute = abs(number)
        for threshold, suffix in ((1_000_000_000_000, "T"), (1_000_000_000, "B"), (1_000_000, "M")):
            if absolute >= threshold:
                return f"{self._format_plain_number(number / threshold)}{suffix}"
        return self._format_plain_number(number)

    def _format_plain_number(self, value: Any) -> str:
        number = self._float_or_none(value)
        if number is None:
            return "-"
        text = f"{number:.4f}".rstrip("0").rstrip(".")
        return text or "0"

    def _format_percent_value(self, value: Any) -> str:
        number = self._float_or_none(value)
        if number is None:
            return "-"
        return f"{self._format_plain_number(number)}%"

    def _format_signed_percent_value(self, value: Any) -> str:
        number = self._float_or_none(value)
        if number is None:
            return "-"
        prefix = "+" if number > 0 else ""
        return f"{prefix}{self._format_plain_number(number)}%"

    def _moving_average(self, values: list[float], window: int) -> Optional[float]:
        if len(values) < window:
            return None
        return round(sum(values[-window:]) / window, 4)

    def _percent_change(self, values: list[float], window: int) -> Optional[float]:
        if len(values) <= window:
            return None
        previous = values[-window - 1]
        current = values[-1]
        if previous == 0:
            return None
        return round(((current - previous) / previous) * 100, 4)

    def _volume_change_vs_ma(self, volumes: list[float], window: int) -> Optional[float]:
        if len(volumes) < window + 1:
            return None
        average = self._moving_average(volumes[:-1], window)
        if average in (None, 0):
            return None
        return round(((volumes[-1] - average) / average) * 100, 4)

    def _volume_price_signal(self, closes: list[float], volumes: list[float]) -> str:
        ma20 = self._moving_average(closes, 20)
        volume_ma5 = self._moving_average(volumes[:-1], 5) if len(volumes) > 5 else None
        if not closes or not volumes or ma20 is None or volume_ma5 in (None, 0):
            return "insufficient_data"
        price_above_trend = closes[-1] >= ma20
        volume_expanded = volumes[-1] >= volume_ma5
        if price_above_trend and volume_expanded:
            return "price_volume_confirmed"
        if price_above_trend:
            return "price_above_trend_volume_soft"
        if volume_expanded:
            return "volume_expanded_price_below_trend"
        return "neutral"

    def _float_or_none(self, value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _resolve_route(self, stock_code: str) -> MarketRoute:
        raw = (stock_code or "").strip()
        crypto = normalize_crypto_symbol(raw)
        code = crypto or normalize_stock_code(raw)
        market = self._market_for_code(code)

        if market == "cn":
            return MarketRoute(
                input_code=raw,
                normalized_code=code,
                market="cn",
                channel="a_share",
                data_source_lane="a_share_market_data",
                quote_sources=("a_share_realtime", "tencent", "akshare_sina", "efinance", "akshare_em"),
                history_sources=("a_share_history", "akshare", "tushare", "efinance"),
                profile_sources=("quote_profile",),
            )
        if market == "crypto":
            return MarketRoute(
                input_code=raw,
                normalized_code=code,
                market="crypto",
                channel="crypto_spot",
                data_source_lane="crypto_market_data",
                quote_sources=("crypto_yahoo_chart", "crypto_cache"),
                history_sources=("crypto_yahoo_chart", "crypto_cache"),
                profile_sources=("quote_profile",),
            )
        if market == "hk":
            return MarketRoute(
                input_code=raw,
                normalized_code=code,
                market="hk",
                channel="hk_equity",
                data_source_lane="hk_market_data",
                quote_sources=("hk_realtime", "longbridge", "akshare_hk"),
                history_sources=("hk_history", "longbridge", "yfinance", "akshare_hk"),
                profile_sources=("yfinance_profile",),
            )
        return MarketRoute(
            input_code=raw,
            normalized_code=code,
            market="us",
            channel="us_equity",
            data_source_lane="us_market_data",
            quote_sources=("us_realtime", "yfinance", "longbridge", "finnhub", "alphavantage"),
            history_sources=("us_history", "yfinance", "longbridge", "finnhub", "alphavantage"),
            profile_sources=("yfinance_profile",),
        )

    def _build_warnings(
        self,
        *,
        quote: Optional[Dict[str, Any]],
        quote_freshness: str,
        history: Optional[Dict[str, Any]],
        route: MarketRoute,
        quote_error: Optional[str] = None,
        history_error: Optional[str] = None,
        quote_fallback: str = "none",
    ) -> list[Dict[str, str]]:
        warnings: list[Dict[str, str]] = []
        history_rows = (history or {}).get("data", [])
        if quote_fallback == "history_last_close":
            warnings.append(
                {
                    "code": "quote_from_history_close",
                    "severity": "warning",
                    "message": (
                        f"{route.channel} realtime quote is unavailable; quick view uses the latest historical close "
                        "without invoking AI."
                    ),
                }
            )
        if quote_freshness == "stale":
            warnings.append(
                {
                    "code": "stale_quote",
                    "severity": "warning",
                    "message": "Quote is stale; quick view uses cached quote and latest available history.",
                }
            )
        if quote_error == "timeout":
            warnings.append(
                {
                    "code": "quote_timeout",
                    "severity": "warning",
                    "message": f"{route.channel} realtime quote source timed out; quick view degraded without invoking AI.",
                }
            )
        if quote_error == "cooling_down":
            warnings.append(
                {
                    "code": "quote_source_cooling_down",
                    "severity": "warning",
                    "message": f"{route.channel} realtime quote source is cooling down after repeated failures; quick view skipped the live call.",
                }
            )
        if not quote or quote_freshness == "unavailable":
            warnings.append(
                {
                    "code": "missing_quote",
                    "severity": "warning",
                    "message": f"{route.channel} realtime quote is unavailable; quick view keeps AI off and uses historical data when present.",
                }
            )
        if history_error == "timeout":
            warnings.append(
                {
                    "code": "history_timeout",
                    "severity": "warning",
                    "message": f"{route.channel} historical source timed out; moving averages may be incomplete.",
                }
            )
        if history_error == "cooling_down":
            warnings.append(
                {
                    "code": "history_source_cooling_down",
                    "severity": "warning",
                    "message": f"{route.channel} historical source is cooling down after repeated failures; moving averages may be incomplete.",
                }
            )
        if not history_rows:
            warnings.append(
                {
                    "code": "missing_history",
                    "severity": "warning",
                    "message": f"{route.channel} historical bars are unavailable; moving averages may be incomplete.",
                }
            )
        if not quote and not history_rows:
            warnings.append(
                {
                    "code": "market_data_unavailable",
                    "severity": "error",
                    "message": "No market quote or historical bars are available for this symbol.",
                }
            )
        return warnings

    def _degradation_payload(self, warnings: list[Dict[str, str]]) -> Dict[str, str]:
        if not warnings:
            return {"status": "ok", "severity": "info", "message": "Market data ready"}
        severity = "error" if any(item.get("severity") == "error" for item in warnings) else "warning"
        return {
            "status": "degraded",
            "severity": severity,
            "message": warnings[0].get("message") or "Market data is degraded",
        }

    def _market_for_code(self, code: str) -> str:
        upper = (code or "").upper()
        if normalize_crypto_symbol(upper) is not None:
            return "crypto"
        if upper.endswith((".SH", ".SZ", ".BJ")):
            return "cn"
        if upper.endswith(".HK") or upper.startswith("HK"):
            return "hk"
        if upper in {"BTC", "ETH"} or upper.endswith("-USD"):
            return "crypto"
        if upper.isdigit() and len(upper) == 6:
            return "cn"
        if upper.isdigit() and len(upper) <= 5:
            return "hk"
        return "us"
