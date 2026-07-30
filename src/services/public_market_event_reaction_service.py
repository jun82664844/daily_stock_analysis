# -*- coding: utf-8 -*-
"""Observed post-event market data for the public no-AI workspace."""

from __future__ import annotations

import copy
import json
import os
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import date, datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, Mapping, Optional, Sequence
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from src.services.public_event_reaction_cache import (
    PublicEventReactionSnapshotStore,
)


REACTION_WINDOWS = (1, 3, 5, 20)
MARKET_BENCHMARKS = {
    "cn": ("000001.SS", "上证指数"),
    "hk": ("^HSI", "恒生指数"),
    "us": ("^GSPC", "标普500指数"),
}
MARKET_TIMEZONES = {
    "cn": ZoneInfo("Asia/Shanghai"),
    "hk": ZoneInfo("Asia/Hong_Kong"),
    "us": ZoneInfo("America/New_York"),
}
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_MAX_RESPONSE_BYTES = 768 * 1024
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="event-reaction")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


HistoryLoader = Callable[[str], Mapping[str, Any]]
EventLoader = Callable[[], Mapping[str, Any]]


class PublicMarketEventReactionService:
    """Compare observed post-event bars with a broad market benchmark."""

    def __init__(
        self,
        *,
        event_loader: EventLoader,
        history_loader: Optional[HistoryLoader] = None,
        clock: Callable[[], str] = _utc_now,
        monotonic_clock: Callable[[], float] = time.monotonic,
        max_events: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        cache_ttl_seconds: Optional[int] = None,
        stale_ttl_seconds: Optional[int] = None,
        max_history_cache_entries: Optional[int] = None,
        executor: Optional[ThreadPoolExecutor] = None,
        snapshot_store: Optional[PublicEventReactionSnapshotStore] = None,
        refresh_executor: Optional[ThreadPoolExecutor] = None,
        allow_event_history: Optional[bool] = None,
    ) -> None:
        self.event_loader = event_loader
        self.history_loader = history_loader or self._fetch_yahoo_history
        self.clock = clock
        self.monotonic_clock = monotonic_clock
        self.max_events = max(
            1,
            min(
                int(max_events or os.getenv("PLATFORM_PUBLIC_EVENT_REACTIONS_V136_MAX_EVENTS", "6")),
                24,
            ),
        )
        self.timeout_seconds = max(
            0.2,
            min(
                float(
                    timeout_seconds
                    or os.getenv("PLATFORM_PUBLIC_EVENT_REACTIONS_V136_TIMEOUT_SECONDS", "4")
                ),
                6.0,
            ),
        )
        self.cache_ttl_seconds = max(
            1,
            int(
                cache_ttl_seconds
                or os.getenv("PLATFORM_PUBLIC_EVENT_REACTIONS_V136_CACHE_TTL_SECONDS", "900")
            ),
        )
        self.stale_ttl_seconds = max(
            self.cache_ttl_seconds,
            int(
                stale_ttl_seconds
                or os.getenv("PLATFORM_PUBLIC_EVENT_REACTIONS_V136_STALE_TTL_SECONDS", "21600")
            ),
        )
        self.max_history_cache_entries = max(
            1,
            min(
                int(
                    max_history_cache_entries
                    or os.getenv(
                        "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_HISTORY_CACHE_MAX_ENTRIES",
                        "32",
                    )
                ),
                128,
            ),
        )
        self.executor = executor or _EXECUTOR
        self.snapshot_store = snapshot_store
        self.refresh_executor = refresh_executor or _EXECUTOR
        self.allow_event_history = (
            allow_event_history
            if allow_event_history is not None
            else os.getenv(
                "PLATFORM_PUBLIC_EVENT_HISTORY_V138_ENABLED",
                "false",
            ).strip().lower() in {"1", "true", "yes", "on"}
        )
        self._history_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._response_cache: Optional[tuple[float, Dict[str, Any]]] = None
        self._refresh_future: Optional[Future[Dict[str, Any]]] = None
        self._lock = Lock()

    def build(self, *, cache_first: bool = False) -> Dict[str, Any]:
        cached = self._read_response_cache(allow_stale=False)
        if cached is not None:
            return cached
        if cache_first:
            return self._build_cache_first()
        return self._build_uncached(allow_stale_fallback=True)

    def observe_events(
        self,
        raw_events: Sequence[Mapping[str, Any]],
        *,
        max_events: int = 24,
    ) -> list[Dict[str, Any]]:
        """Observe one caller-supplied event set without changing response caches."""

        as_of = self.clock()
        now = self._parse_datetime(as_of) or datetime.now(timezone.utc)
        selected = self._select_events(
            raw_events,
            now,
            max_events=max_events,
            balance_markets=False,
        )
        histories = self._load_histories(selected)
        return [
            self._build_item(event, subject, benchmark, histories, as_of, now)
            for event, subject, benchmark in selected
        ]

    def _build_uncached(self, *, allow_stale_fallback: bool) -> Dict[str, Any]:
        as_of = self.clock()
        now = self._parse_datetime(as_of) or datetime.now(timezone.utc)
        warnings: list[str] = []
        market_sources: list[Dict[str, Any]] = []
        try:
            event_payload = self.event_loader()
            events = event_payload.get("events") if isinstance(event_payload, Mapping) else []
            if isinstance(event_payload, Mapping):
                market_sources = self._normalize_market_sources(
                    event_payload.get("market_sources"),
                    as_of,
                )
        except Exception:
            stale = (
                self._read_response_cache(allow_stale=True)
                if allow_stale_fallback
                else None
            )
            if stale is not None:
                stale["warnings"] = list(dict.fromkeys([
                    *(stale.get("warnings") or []),
                    "event_reaction_events_unavailable",
                    "event_reaction_response_stale",
                ]))
                return stale
            return self._empty_payload(
                as_of,
                warnings=[
                    "event_reaction_events_unavailable",
                    "event_reaction_no_eligible_events",
                ],
                market_sources=market_sources,
            )

        selected = self._select_events(events or [], now)
        histories = self._load_histories(selected)
        items = [
            self._build_item(event, subject, benchmark, histories, as_of, now)
            for event, subject, benchmark in selected
        ]
        if any(item["status"] == "unavailable" for item in items):
            warnings.append("event_reaction_source_unavailable")
        if not items:
            warnings.append("event_reaction_no_eligible_events")
        if not market_sources:
            market_sources = self._derive_market_sources(items, as_of)

        payload = {
            "as_of": as_of,
            "items": items[: self.max_events],
            "market_sources": market_sources,
            "warnings": list(dict.fromkeys(warnings)),
            "cache": {
                "hit": False,
                "age_seconds": 0,
                "ttl_seconds": self.cache_ttl_seconds,
                "storage": "memory",
                "refreshing": False,
            },
            "ai_used": False,
            "informational_only": True,
        }
        with self._lock:
            self._response_cache = (self.monotonic_clock(), copy.deepcopy(payload))
        return payload

    def _empty_payload(
        self,
        as_of: str,
        *,
        warnings: Sequence[str],
        market_sources: Optional[Sequence[Mapping[str, Any]]] = None,
        refreshing: bool = False,
    ) -> Dict[str, Any]:
        return {
            "as_of": as_of,
            "items": [],
            "market_sources": list(market_sources or self._derive_market_sources([], as_of)),
            "warnings": list(dict.fromkeys(warnings)),
            "cache": {
                "hit": False,
                "age_seconds": 0,
                "ttl_seconds": self.cache_ttl_seconds,
                "storage": "none",
                "refreshing": refreshing,
            },
            "ai_used": False,
            "informational_only": True,
        }

    def _build_cache_first(self) -> Dict[str, Any]:
        snapshot = self.snapshot_store.read() if self.snapshot_store else None
        if snapshot is not None:
            payload = copy.deepcopy(snapshot["payload"])
            age = max(0, int(snapshot["age_seconds"]))
            with self._lock:
                self._response_cache = (
                    self.monotonic_clock() - age,
                    copy.deepcopy(payload),
                )
            if snapshot["stale"]:
                self._start_background_refresh()
                payload["warnings"] = list(dict.fromkeys([
                    *(payload.get("warnings") or []),
                    "event_reaction_response_stale",
                ]))
                payload["cache"]["refreshing"] = self._refresh_in_progress()
            return payload

        self._start_background_refresh()
        return self._empty_payload(
            self.clock(),
            warnings=["event_reaction_refreshing"],
            refreshing=self._refresh_in_progress(),
        )

    def prewarm(self) -> bool:
        """Start one best-effort public refresh without blocking app startup."""
        return self._start_background_refresh()

    def wait_for_refresh(self, timeout: Optional[float] = None) -> bool:
        with self._lock:
            future = self._refresh_future
        if future is None:
            return True
        try:
            future.result(timeout=timeout)
        except Exception:
            return False
        return True

    def _start_background_refresh(self) -> bool:
        with self._lock:
            if self._refresh_future is not None and not self._refresh_future.done():
                return False
            self._refresh_future = self.refresh_executor.submit(
                self._refresh_and_store
            )
        return True

    def _refresh_in_progress(self) -> bool:
        with self._lock:
            return bool(
                self._refresh_future is not None
                and not self._refresh_future.done()
            )

    def _refresh_and_store(self) -> Dict[str, Any]:
        payload = self._build_uncached(allow_stale_fallback=False)
        market_sources = payload.get("market_sources")
        if (
            isinstance(market_sources, Sequence)
            and market_sources
            and not any(
                isinstance(source, Mapping)
                and source.get("status") in {"fresh", "cached", "stale"}
                for source in market_sources
            )
        ):
            raise RuntimeError("all event reaction market sources unavailable")
        if self.snapshot_store is not None:
            self.snapshot_store.write(payload)
        return payload

    def _read_response_cache(
        self,
        *,
        allow_stale: bool,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._response_cache
        if entry is None:
            return None
        age = max(0, int(self.monotonic_clock() - entry[0]))
        limit = self.stale_ttl_seconds if allow_stale else self.cache_ttl_seconds
        if age >= limit:
            return None
        payload = copy.deepcopy(entry[1])
        payload["cache"] = {
            "hit": True,
            "age_seconds": age,
            "ttl_seconds": self.cache_ttl_seconds,
            "storage": "memory",
            "refreshing": self._refresh_in_progress(),
        }
        return payload

    @staticmethod
    def _normalize_market_sources(
        value: Any,
        as_of: str,
    ) -> list[Dict[str, Any]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return []
        by_market: Dict[str, Dict[str, Any]] = {}
        for raw in value:
            if not isinstance(raw, Mapping):
                continue
            market = str(raw.get("market") or "").strip().lower()
            status = str(raw.get("status") or "").strip().lower()
            if market not in MARKET_BENCHMARKS:
                continue
            if status not in {"fresh", "cached", "stale", "unavailable"}:
                status = "unavailable"
            try:
                count = max(0, min(int(raw.get("event_count") or 0), 72))
            except (TypeError, ValueError):
                count = 0
            by_market[market] = {
                "market": market,
                "status": status,
                "event_count": count,
                "observed_at": raw.get("observed_at"),
                "fetched_at": str(raw.get("fetched_at") or as_of),
                "warning_code": raw.get("warning_code"),
            }
        return [
            by_market.get(
                market,
                {
                    "market": market,
                    "status": "unavailable",
                    "event_count": 0,
                    "observed_at": None,
                    "fetched_at": as_of,
                    "warning_code": "event_calendar_market_unavailable",
                },
            )
            for market in ("cn", "hk", "us")
        ]

    @staticmethod
    def _derive_market_sources(
        items: Sequence[Mapping[str, Any]],
        as_of: str,
    ) -> list[Dict[str, Any]]:
        priority = {"fresh": 3, "cached": 2, "stale": 1, "unavailable": 0}
        result = []
        for market in ("cn", "hk", "us"):
            market_items = [
                item
                for item in items
                if str(item.get("market") or "").lower() == market
            ]
            statuses = [
                str((item.get("source_state") or {}).get("status") or "unavailable")
                for item in market_items
            ]
            status = max(statuses, key=lambda item: priority.get(item, 0)) if statuses else "unavailable"
            observed = [
                str((item.get("source_state") or {}).get("observed_at") or "")
                for item in market_items
                if (item.get("source_state") or {}).get("observed_at")
            ]
            result.append({
                "market": market,
                "status": status,
                "event_count": len(market_items),
                "observed_at": max(observed) if observed else None,
                "fetched_at": as_of,
                "warning_code": (
                    None
                    if market_items
                    else "event_calendar_market_unavailable"
                ),
            })
        return result

    def _select_events(
        self,
        raw_events: Sequence[Mapping[str, Any]],
        now: datetime,
        *,
        max_events: Optional[int] = None,
        balance_markets: bool = True,
    ) -> list[tuple[Dict[str, Any], str, Optional[str]]]:
        result_limit = max(1, min(int(max_events or self.max_events), 24))
        selected: list[tuple[Dict[str, Any], str, Optional[str]]] = []
        seen: set[str] = set()
        for raw in raw_events:
            if not isinstance(raw, Mapping):
                continue
            event = dict(raw)
            event_id = str(event.get("event_id") or "").strip()
            if not event_id or event_id in seen:
                continue
            time_kind = str(event.get("time_kind") or "")
            classification_source = str(
                event.get("classification_source") or ""
            )
            is_provider_schedule = (
                time_kind == "scheduled"
                and classification_source == "provider_schedule"
            )
            is_provider_history = (
                self.allow_event_history
                and time_kind == "observed"
                and classification_source == "provider_event_history"
            )
            if not (is_provider_schedule or is_provider_history):
                continue
            event_time = self._parse_datetime(event.get("event_time"))
            market = str(event.get("market") or "").strip().lower()
            if market not in MARKET_BENCHMARKS:
                continue
            if event_time is None:
                continue
            market_today = now.astimezone(MARKET_TIMEZONES[market]).date()
            if event_time.date() >= market_today:
                continue
            schedule_type = str(event.get("schedule_type") or "")
            if schedule_type == "macro_policy" and market == "us":
                subject = "^GSPC"
                benchmark = None
                event["symbol"] = "^GSPC"
                event["name"] = event.get("name") or "S&P 500"
                event["_subject_type"] = "market_benchmark"
            else:
                subject = self._history_symbol(market, event.get("symbol"))
                if subject is None:
                    continue
                benchmark = MARKET_BENCHMARKS[market][0]
                event["_subject_type"] = "security"
            seen.add(event_id)
            selected.append((event, subject, benchmark))
        selected.sort(
            key=lambda item: (
                self._parse_datetime(item[0].get("event_time"))
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )
        if not balance_markets:
            return selected[:result_limit]
        reserved = []
        reserved_ids: set[str] = set()
        for market in ("cn", "hk", "us"):
            candidate = next(
                (
                    item
                    for item in selected
                    if item[0].get("market") == market
                ),
                None,
            )
            if candidate is None:
                continue
            reserved.append(candidate)
            reserved_ids.add(str(candidate[0].get("event_id") or ""))
        if result_limit < len(reserved):
            return selected[:result_limit]
        balanced = [
            *reserved,
            *[
                item
                for item in selected
                if str(item[0].get("event_id") or "") not in reserved_ids
            ],
        ][:result_limit]
        balanced.sort(
            key=lambda item: (
                self._parse_datetime(item[0].get("event_time"))
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )
        return balanced

    def _load_histories(
        self,
        selected: Sequence[tuple[Dict[str, Any], str, Optional[str]]],
    ) -> Dict[str, tuple[Optional[Dict[str, Any]], str]]:
        symbols = list(dict.fromkeys(
            symbol
            for _, subject, benchmark in selected
            for symbol in (subject, benchmark)
            if symbol
        ))
        result: Dict[str, tuple[Optional[Dict[str, Any]], str]] = {}
        pending: Dict[Future[Mapping[str, Any]], str] = {}
        for symbol in symbols:
            cached = self._read_history_cache(symbol, allow_stale=False)
            if cached is not None:
                result[symbol] = (cached, "cached")
            else:
                pending[self.executor.submit(self.history_loader, symbol)] = symbol

        completed, unfinished = wait(tuple(pending), timeout=self.timeout_seconds)
        for future in unfinished:
            future.cancel()
        for future, symbol in pending.items():
            if future in completed:
                try:
                    payload = self._normalize_history_payload(symbol, future.result())
                except Exception:
                    payload = None
                if payload is not None:
                    payload["fetched_at"] = self.clock()
                    self._write_history_cache(symbol, payload)
                    result[symbol] = (payload, "fresh")
                    continue
            stale = self._read_history_cache(symbol, allow_stale=True)
            result[symbol] = (stale, "stale" if stale is not None else "unavailable")
        return result

    def _read_history_cache(
        self,
        symbol: str,
        *,
        allow_stale: bool,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._history_cache.get(symbol)
        if entry is None:
            return None
        age = self.monotonic_clock() - entry[0]
        limit = self.stale_ttl_seconds if allow_stale else self.cache_ttl_seconds
        if age >= limit:
            return None
        return copy.deepcopy(entry[1])

    def _write_history_cache(self, symbol: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._history_cache.pop(symbol, None)
            self._history_cache[symbol] = (self.monotonic_clock(), copy.deepcopy(payload))
            while len(self._history_cache) > self.max_history_cache_entries:
                oldest_symbol = next(iter(self._history_cache))
                self._history_cache.pop(oldest_symbol, None)

    def _build_item(
        self,
        event: Dict[str, Any],
        subject: str,
        benchmark: Optional[str],
        histories: Mapping[str, tuple[Optional[Dict[str, Any]], str]],
        as_of: str,
        now: datetime,
    ) -> Dict[str, Any]:
        subject_payload, subject_status = histories.get(subject, (None, "unavailable"))
        benchmark_payload, benchmark_status = (
            histories.get(benchmark, (None, "unavailable"))
            if benchmark
            else (None, "unavailable")
        )
        market = str(event.get("market") or "")
        market_today = now.astimezone(
            MARKET_TIMEZONES.get(market, timezone.utc)
        ).date()
        event_time = self._parse_datetime(event.get("event_time"))
        event_date = event_time.date() if event_time else market_today
        subject_rows = list((subject_payload or {}).get("data") or [])
        benchmark_rows = list((benchmark_payload or {}).get("data") or [])
        baseline_index = self._baseline_index(subject_rows, event_date)
        baseline_date = (
            str(subject_rows[baseline_index]["date"])
            if baseline_index is not None
            else None
        )
        windows = [
            self._window(
                trading_days=trading_days,
                subject_rows=subject_rows,
                baseline_index=baseline_index,
                benchmark_rows=benchmark_rows,
                event_date=event_date,
                market_today=market_today,
            )
            for trading_days in REACTION_WINDOWS
        ]
        available_count = sum(window["status"] == "available" for window in windows)
        if subject_payload is None or baseline_index is None:
            status = "unavailable"
        elif available_count == len(windows):
            status = "available"
        elif available_count > 0:
            status = "partial"
        else:
            status = "pending"
        benchmark_name = MARKET_BENCHMARKS.get(market, (None, None))[1] if benchmark else None
        return {
            "event_id": str(event.get("event_id") or ""),
            "market": market,
            "title": str(event.get("title") or ""),
            "symbol": str(event.get("symbol") or subject),
            "name": str(event.get("name") or event.get("symbol") or subject),
            "subject_type": str(event.get("_subject_type") or "security"),
            "event_time": str(event.get("event_time") or ""),
            "event_time_kind": str(event.get("time_kind") or "scheduled"),
            "classification_source": str(
                event.get("classification_source") or "provider_schedule"
            ),
            "schedule_type": event.get("schedule_type"),
            "history_symbol": subject,
            "baseline_date": baseline_date,
            "benchmark_symbol": benchmark,
            "benchmark_name": benchmark_name,
            "status": status,
            "windows": windows,
            "source_state": self._source_state(
                subject_payload,
                subject_status,
                as_of,
            ),
            "benchmark_source_state": (
                self._source_state(benchmark_payload, benchmark_status, as_of)
                if benchmark
                else None
            ),
            "warning_codes": self._warning_codes(
                subject_payload,
                subject_status,
                benchmark,
                benchmark_payload,
                benchmark_status,
                available_count,
            ),
        }

    def _window(
        self,
        *,
        trading_days: int,
        subject_rows: Sequence[Mapping[str, Any]],
        baseline_index: Optional[int],
        benchmark_rows: Sequence[Mapping[str, Any]],
        event_date: date,
        market_today: date,
    ) -> Dict[str, Any]:
        empty = {
            "trading_days": trading_days,
            "status": "insufficient_data",
            "observed_date": None,
            "symbol_return_percent": None,
            "benchmark_return_percent": None,
            "relative_return_percent": None,
            "volume_ratio": None,
        }
        if baseline_index is None:
            return empty

        market_rows = benchmark_rows or subject_rows
        market_baseline_index = self._baseline_index(market_rows, event_date)
        if market_baseline_index is None:
            return empty
        market_target_index = market_baseline_index + trading_days
        if market_target_index >= len(market_rows):
            latest_market_date = self._parse_date(
                market_rows[-1].get("date") if market_rows else None
            )
            if (
                latest_market_date is not None
                and 0 <= (market_today - latest_market_date).days <= 10
            ):
                empty["status"] = "pending"
            return empty

        target_date = str(market_rows[market_target_index].get("date") or "")
        target_index = next(
            (
                index
                for index, row in enumerate(subject_rows)
                if str(row.get("date") or "") == target_date
            ),
            None,
        )
        if target_index is None or target_index <= baseline_index:
            return empty

        baseline = subject_rows[baseline_index]
        target = subject_rows[target_index]
        symbol_return = self._percent_change(baseline.get("close"), target.get("close"))
        if symbol_return is None:
            return empty
        observed_date = target_date
        benchmark_return = self._benchmark_return(
            benchmark_rows,
            str(baseline.get("date") or ""),
            observed_date,
        )
        volume_ratio = self._volume_ratio(
            subject_rows,
            baseline_index,
            target_index,
        )
        return {
            "trading_days": trading_days,
            "status": "available",
            "observed_date": observed_date,
            "symbol_return_percent": symbol_return,
            "benchmark_return_percent": benchmark_return,
            "relative_return_percent": (
                round(symbol_return - benchmark_return, 4)
                if benchmark_return is not None
                else None
            ),
            "volume_ratio": volume_ratio,
        }

    @classmethod
    def _benchmark_return(
        cls,
        rows: Sequence[Mapping[str, Any]],
        baseline_date: str,
        observed_date: str,
    ) -> Optional[float]:
        baseline = None
        target = None
        for row in rows:
            row_date = str(row.get("date") or "")
            if row_date <= baseline_date:
                baseline = row
            if baseline_date < row_date <= observed_date:
                target = row
        if baseline is None or target is None:
            return None
        return cls._percent_change(baseline.get("close"), target.get("close"))

    @staticmethod
    def _volume_ratio(
        rows: Sequence[Mapping[str, Any]],
        baseline_index: int,
        target_index: int,
    ) -> Optional[float]:
        before = [
            float(row["volume"])
            for row in rows[max(0, baseline_index - 5): baseline_index]
            if row.get("volume") not in (None, 0)
        ]
        after = [
            float(row["volume"])
            for row in rows[baseline_index + 1: target_index + 1]
            if row.get("volume") not in (None, 0)
        ]
        if not before or not after:
            return None
        previous_average = sum(before) / len(before)
        return round((sum(after) / len(after)) / previous_average, 4) if previous_average else None

    @staticmethod
    def _baseline_index(
        rows: Sequence[Mapping[str, Any]],
        event_date: date,
    ) -> Optional[int]:
        index = None
        for candidate_index, row in enumerate(rows):
            row_date = PublicMarketEventReactionService._parse_date(row.get("date"))
            if row_date is not None and row_date <= event_date:
                index = candidate_index
        return index

    @staticmethod
    def _source_state(
        payload: Optional[Mapping[str, Any]],
        status: str,
        as_of: str,
    ) -> Dict[str, Any]:
        normalized_status = status if status in {"fresh", "cached", "stale"} else "unavailable"
        return {
            "source": str((payload or {}).get("source") or "yahoo_chart_public"),
            "status": normalized_status,
            "observed_at": (
                str(((payload or {}).get("data") or [{}])[-1].get("date"))
                if (payload or {}).get("data")
                else None
            ),
            "fetched_at": str((payload or {}).get("fetched_at") or as_of),
            "delay_seconds": None,
            "warning_code": (
                "event_reaction_history_stale"
                if normalized_status == "stale"
                else "event_reaction_history_unavailable"
                if normalized_status == "unavailable"
                else None
            ),
        }

    @staticmethod
    def _warning_codes(
        subject_payload: Optional[Mapping[str, Any]],
        subject_status: str,
        benchmark: Optional[str],
        benchmark_payload: Optional[Mapping[str, Any]],
        benchmark_status: str,
        available_count: int,
    ) -> list[str]:
        warnings = []
        if subject_payload is None:
            warnings.append("subject_history_unavailable")
        elif subject_status == "stale":
            warnings.append("subject_history_stale")
        if benchmark and benchmark_payload is None:
            warnings.append("benchmark_history_unavailable")
        elif benchmark and benchmark_status == "stale":
            warnings.append("benchmark_history_stale")
        if subject_payload is not None and available_count < len(REACTION_WINDOWS):
            warnings.append("observation_window_incomplete")
        return warnings

    @classmethod
    def _normalize_history_payload(
        cls,
        symbol: str,
        payload: Mapping[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, Mapping):
            return None
        rows_by_date: Dict[str, Dict[str, Any]] = {}
        for raw in payload.get("data") or []:
            if not isinstance(raw, Mapping):
                continue
            row_date = cls._parse_date(raw.get("date"))
            close = cls._float(raw.get("close"))
            if row_date is None or close is None or close <= 0:
                continue
            rows_by_date[row_date.isoformat()] = {
                "date": row_date.isoformat(),
                "close": close,
                "volume": cls._float(raw.get("volume")),
            }
        rows = [rows_by_date[key] for key in sorted(rows_by_date)][-560:]
        if not rows:
            return None
        return {
            "symbol": symbol,
            "source": str(payload.get("source") or "yahoo_chart_public"),
            "data": rows,
        }

    @staticmethod
    def _history_symbol(market: str, raw_symbol: Any) -> Optional[str]:
        symbol = str(raw_symbol or "").strip().upper()
        if market == "cn":
            match = re.fullmatch(r"(\d{6})\.(SH|SZ)", symbol)
            if match is None:
                return None
            code, exchange = match.groups()
            return f"{code}.{'SS' if exchange == 'SH' else 'SZ'}"
        if market == "hk":
            return symbol if re.fullmatch(r"\d{4,5}\.HK", symbol) else None
        if market == "us":
            return symbol if re.fullmatch(r"[A-Z]{1,5}(?:[-.][A-Z])?", symbol) else None
        return None

    def _fetch_yahoo_history(self, symbol: str) -> Mapping[str, Any]:
        if not self._safe_yahoo_symbol(symbol):
            raise ValueError("unsupported event reaction symbol")
        response = requests.get(
            YAHOO_CHART_URL.format(symbol=quote(symbol, safe="")),
            params={"interval": "1d", "range": "2y", "events": "history"},
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
            },
            timeout=(min(1.0, self.timeout_seconds), self.timeout_seconds),
            allow_redirects=False,
            stream=True,
        )
        try:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _MAX_RESPONSE_BYTES:
                    raise ValueError("event reaction response too large")
                chunks.append(chunk)
            payload = json.loads(b"".join(chunks).decode("utf-8-sig"))
        finally:
            response.close()
        chart = payload.get("chart") if isinstance(payload, Mapping) else None
        results = chart.get("result") if isinstance(chart, Mapping) else None
        result = results[0] if isinstance(results, list) and results else None
        if not isinstance(result, Mapping):
            raise ValueError("invalid Yahoo chart payload")
        timestamps = result.get("timestamp") if isinstance(result.get("timestamp"), list) else []
        indicators = result.get("indicators") if isinstance(result.get("indicators"), Mapping) else {}
        quotes = indicators.get("quote") if isinstance(indicators.get("quote"), list) else []
        quote_block = quotes[0] if quotes and isinstance(quotes[0], Mapping) else {}
        closes = quote_block.get("close") if isinstance(quote_block.get("close"), list) else []
        volumes = quote_block.get("volume") if isinstance(quote_block.get("volume"), list) else []
        rows = []
        for index, timestamp in enumerate(timestamps):
            close = closes[index] if index < len(closes) else None
            if close is None:
                continue
            try:
                row_date = datetime.fromtimestamp(float(timestamp), tz=timezone.utc).date().isoformat()
            except (OSError, OverflowError, TypeError, ValueError):
                continue
            rows.append({
                "date": row_date,
                "close": close,
                "volume": volumes[index] if index < len(volumes) else None,
            })
        return {"symbol": symbol, "source": "yahoo_chart_public", "data": rows}

    @staticmethod
    def _safe_yahoo_symbol(symbol: str) -> bool:
        return bool(
            re.fullmatch(
                r"(?:\d{6}\.(?:SS|SZ)|\d{4,5}\.HK|[A-Z]{1,5}(?:[-.][A-Z])?|\^(?:HSI|GSPC))",
                symbol,
            )
        )

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float(value: Any) -> Optional[float]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number

    @classmethod
    def _percent_change(cls, start: Any, end: Any) -> Optional[float]:
        start_value = cls._float(start)
        end_value = cls._float(end)
        if start_value in (None, 0) or end_value is None:
            return None
        return round((end_value - start_value) / start_value * 100, 4)
