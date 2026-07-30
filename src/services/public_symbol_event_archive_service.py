# -*- coding: utf-8 -*-
"""Public, no-AI event archive for one supported equity symbol."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional, Sequence
from urllib.parse import urlparse


ArchiveCalendarLoader = Callable[..., Sequence[Mapping[str, Any]]]

_MONTH_TO_DAYS = {6: 183, 12: 366, 24: 732}
_EVENT_TYPE_BY_SCHEDULE = {
    "earnings_release": "earnings",
    "ex_dividend": "dividend",
    "stock_split": "split",
    "share_buyback": "buyback",
    "important_announcement": "announcement",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PublicSymbolEventArchiveService:
    """Load traceable events and attach objective post-event observations."""

    def __init__(
        self,
        *,
        calendar_loader: ArchiveCalendarLoader,
        reaction_service: Any,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self.calendar_loader = calendar_loader
        self.reaction_service = reaction_service
        self.clock = clock

    def build(self, symbol: str, *, months: int = 12) -> Dict[str, Any]:
        canonical, market = self._symbol_identity(symbol)
        if months not in _MONTH_TO_DAYS:
            raise ValueError("invalid_months")

        as_of = self.clock()
        section = {
            "market": market,
            "attention": [{
                "symbol": canonical,
                "name": canonical,
                "market": market,
            }],
        }
        warnings: list[str] = []
        try:
            loaded = list(self.calendar_loader(
                [section],
                as_of,
                past_days=_MONTH_TO_DAYS[months],
                future_days=0,
                max_events=48,
                newest_first=True,
                include_historical=True,
                include_observed_history=True,
                fail_on_source_unavailable=True,
            ) or [])
        except Exception:
            loaded = []
            warnings.append("symbol_event_archive_source_unavailable")

        events = [
            dict(event)
            for event in loaded
            if isinstance(event, Mapping)
            and str(event.get("symbol") or "").strip().upper() == canonical
        ][:24]
        try:
            reactions = list(
                self.reaction_service.observe_events(events, max_events=24)
            )
        except Exception:
            reactions = []
            if events:
                warnings.append("symbol_event_archive_observation_unavailable")
        reactions_by_id = {
            str(item.get("event_id") or ""): dict(item)
            for item in reactions
            if isinstance(item, Mapping) and item.get("event_id")
        }

        items = [
            self._archive_item(
                event,
                reactions_by_id.get(str(event.get("event_id") or "")),
                as_of,
            )
            for event in events
        ]
        chart = self._empty_chart(canonical, market, as_of)
        load_price_chart = getattr(self.reaction_service, "load_price_chart", None)
        if callable(load_price_chart):
            try:
                chart = dict(load_price_chart(
                    market,
                    canonical,
                    days=_MONTH_TO_DAYS[months],
                    max_points=560,
                ))
            except Exception:
                warnings.append("symbol_event_timeline_unavailable")
        else:
            warnings.append("symbol_event_timeline_unavailable")
        if not items and "symbol_event_archive_source_unavailable" not in warnings:
            warnings.append("symbol_event_archive_empty")
        name = next(
            (
                str(event.get("name") or "").strip()
                for event in events
                if str(event.get("name") or "").strip()
            ),
            canonical,
        )
        return {
            "symbol": canonical,
            "name": name,
            "market": market,
            "months": months,
            "as_of": as_of,
            "items": items,
            "chart": chart,
            "available_event_types": list(dict.fromkeys(
                item["event_type"] for item in items
            )),
            "warnings": list(dict.fromkeys(warnings)),
            "ai_used": False,
            "informational_only": True,
            "causality_disclaimer": True,
        }

    @staticmethod
    def _empty_chart(symbol: str, market: str, as_of: str) -> Dict[str, Any]:
        benchmark_by_market = {
            "cn": ("000001.SS", "上证指数"),
            "hk": ("^HSI", "恒生指数"),
            "us": ("^GSPC", "标普500指数"),
        }
        history_symbol = (
            symbol.replace(".SH", ".SS")
            if market == "cn"
            else symbol
        )
        benchmark_symbol, benchmark_name = benchmark_by_market[market]
        unavailable_source = {
            "source": "yahoo_chart_public",
            "status": "unavailable",
            "observed_at": None,
            "fetched_at": as_of,
            "delay_seconds": None,
            "warning_code": "event_reaction_history_unavailable",
        }
        return {
            "status": "unavailable",
            "history_symbol": history_symbol,
            "benchmark_symbol": benchmark_symbol,
            "benchmark_name": benchmark_name,
            "points": [],
            "source_state": dict(unavailable_source),
            "benchmark_source_state": dict(unavailable_source),
            "warning_codes": ["subject_history_unavailable"],
        }

    @classmethod
    def _archive_item(
        cls,
        event: Mapping[str, Any],
        reaction: Optional[Mapping[str, Any]],
        as_of: str,
    ) -> Dict[str, Any]:
        schedule_type = str(event.get("schedule_type") or "")
        event_type = _EVENT_TYPE_BY_SCHEDULE.get(
            schedule_type,
            "announcement",
        )
        event_source_state = cls._source_state(
            event.get("source_state"),
            as_of,
        )
        base = dict(reaction) if reaction is not None else cls._empty_reaction(
            event,
            as_of,
        )
        base.update({
            "event_type": event_type,
            "summary": (
                str(event.get("summary")).strip()
                if event.get("summary") is not None
                else None
            ),
            "publisher": str(
                event.get("publisher")
                or event_source_state["source"]
                or "public_source"
            ),
            "source_url": cls._safe_http_url(
                event.get("url") or cls._record_url(event.get("source_records"))
            ),
            "event_source_state": event_source_state,
        })
        return base

    @classmethod
    def _empty_reaction(
        cls,
        event: Mapping[str, Any],
        as_of: str,
    ) -> Dict[str, Any]:
        source_state = {
            "source": "yahoo_chart_public",
            "status": "unavailable",
            "observed_at": None,
            "fetched_at": as_of,
            "delay_seconds": None,
            "warning_code": "event_reaction_history_unavailable",
        }
        return {
            "event_id": str(event.get("event_id") or ""),
            "market": str(event.get("market") or ""),
            "title": str(event.get("title") or ""),
            "symbol": str(event.get("symbol") or ""),
            "name": str(event.get("name") or event.get("symbol") or ""),
            "subject_type": "security",
            "event_time": str(event.get("event_time") or ""),
            "event_time_kind": str(event.get("time_kind") or "observed"),
            "classification_source": str(
                event.get("classification_source") or "provider_event_history"
            ),
            "schedule_type": event.get("schedule_type"),
            "history_symbol": str(event.get("symbol") or ""),
            "baseline_date": None,
            "benchmark_symbol": None,
            "benchmark_name": None,
            "status": "unavailable",
            "windows": [],
            "source_state": source_state,
            "benchmark_source_state": None,
            "warning_codes": ["event_price_observation_unavailable"],
        }

    @staticmethod
    def _source_state(value: Any, as_of: str) -> Dict[str, Any]:
        raw = value if isinstance(value, Mapping) else {}
        status = str(raw.get("status") or "unavailable")
        if status not in {"fresh", "cached", "stale", "unavailable"}:
            status = "unavailable"
        delay = raw.get("delay_seconds")
        try:
            delay_seconds = max(0, int(delay)) if delay is not None else None
        except (TypeError, ValueError):
            delay_seconds = None
        return {
            "source": str(raw.get("source") or "public_event_source"),
            "status": status,
            "observed_at": raw.get("observed_at"),
            "fetched_at": str(raw.get("fetched_at") or as_of),
            "delay_seconds": delay_seconds,
            "warning_code": raw.get("warning_code"),
        }

    @staticmethod
    def _record_url(value: Any) -> Optional[str]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return None
        for record in value:
            if isinstance(record, Mapping) and record.get("url"):
                return str(record["url"])
        return None

    @staticmethod
    def _safe_http_url(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        try:
            parsed = urlparse(text)
        except ValueError:
            return None
        return text if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc else None

    @staticmethod
    def _symbol_identity(value: str) -> tuple[str, str]:
        symbol = str(value or "").strip().upper()
        if re.fullmatch(r"[036]\d{5}", symbol):
            exchange = "SH" if symbol.startswith("6") else "SZ"
            return f"{symbol}.{exchange}", "cn"
        if re.fullmatch(r"\d{6}\.(?:SH|SZ)", symbol):
            return symbol, "cn"
        hk_prefixed = re.fullmatch(r"HK(\d{4,5})", symbol)
        if hk_prefixed and int(hk_prefixed.group(1)) > 0:
            code = str(int(hk_prefixed.group(1))).zfill(4)
            return f"{code}.HK", "hk"
        if re.fullmatch(r"\d{4,5}\.HK", symbol):
            return symbol, "hk"
        if re.fullmatch(r"[A-Z]{1,5}(?:[-.][A-Z])?", symbol):
            return symbol, "us"
        raise ValueError("invalid_symbol")
