# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import unittest

from src.services.public_symbol_event_archive_service import (
    PublicSymbolEventArchiveService,
)


def _source_state(source: str = "yahoo_chart_public") -> dict:
    return {
        "source": source,
        "status": "fresh",
        "observed_at": "2026-07-30T00:00:00+00:00",
        "fetched_at": "2026-07-30T00:00:00+00:00",
        "delay_seconds": 0,
        "warning_code": None,
    }


def _event(event_id: str, schedule_type: str, event_time: str) -> dict:
    return {
        "event_id": event_id,
        "market": "us",
        "category": "earnings",
        "title": f"Public event {event_id}",
        "summary": "Traceable public event.",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "event_time": event_time,
        "time_kind": "observed",
        "publisher": "Yahoo Finance",
        "url": "https://finance.yahoo.com/quote/AAPL",
        "source_state": _source_state("yahoo_event_history"),
        "classification_source": "provider_event_history",
        "schedule_type": schedule_type,
    }


def _window(
    trading_days: int,
    symbol_return: object,
    benchmark_return: object,
    relative_return: object,
) -> dict:
    return {
        "trading_days": trading_days,
        "status": "available",
        "observed_date": "2026-07-29",
        "symbol_return_percent": symbol_return,
        "benchmark_return_percent": benchmark_return,
        "relative_return_percent": relative_return,
        "volume_ratio": 1.0,
    }


def _reaction(event: dict, windows: list[dict]) -> dict:
    return {
        "event_id": event["event_id"],
        "market": event["market"],
        "title": event["title"],
        "symbol": event["symbol"],
        "name": event["name"],
        "subject_type": "security",
        "event_time": event["event_time"],
        "event_time_kind": event["time_kind"],
        "classification_source": event["classification_source"],
        "schedule_type": event["schedule_type"],
        "history_symbol": "AAPL",
        "baseline_date": event["event_time"][:10],
        "benchmark_symbol": "^GSPC",
        "benchmark_name": "标普500指数",
        "status": "available" if windows else "unavailable",
        "windows": windows,
        "source_state": _source_state(),
        "benchmark_source_state": _source_state(),
        "warning_codes": [],
    }


class _Reactions:
    def __init__(self, reactions: list[dict]) -> None:
        self.reactions = reactions

    def observe_events(self, events, *, max_events):
        return self.reactions[:max_events]

    @staticmethod
    def load_price_chart(market, symbol, *, days, max_points):
        return {
            "status": "unavailable",
            "history_symbol": symbol,
            "benchmark_symbol": "^GSPC",
            "benchmark_name": "标普500指数",
            "points": [],
            "source_state": _source_state(),
            "benchmark_source_state": _source_state(),
            "warning_codes": ["subject_history_unavailable"],
        }


class PublicSymbolEventComparisonV141TestCase(unittest.TestCase):
    def _build(self, events: list[dict], reactions: list[dict]) -> dict:
        return PublicSymbolEventArchiveService(
            calendar_loader=lambda *args, **kwargs: events,
            reaction_service=_Reactions(reactions),
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build("AAPL", months=24)

    def test_groups_same_type_events_and_calculates_bounded_statistics(self) -> None:
        earnings = [
            _event("earnings-1", "earnings_release", "2026-07-20T00:00:00Z"),
            _event("earnings-2", "earnings_release", "2026-04-20T00:00:00Z"),
            _event("earnings-3", "earnings_release", "2026-01-20T00:00:00Z"),
        ]
        dividend = _event(
            "dividend-1",
            "ex_dividend",
            "2025-12-01T00:00:00Z",
        )
        reactions = [
            _reaction(earnings[0], [
                _window(1, 2.0, 1.0, 1.0),
                _window(20, 8.0, 3.0, 5.0),
            ]),
            _reaction(earnings[1], [_window(1, -1.0, 0.0, -1.0)]),
            _reaction(earnings[2], [_window(1, 5.0, None, None)]),
            _reaction(dividend, []),
        ]

        payload = self._build([*earnings, dividend], reactions)

        summaries = payload["comparison_summaries"]
        self.assertEqual(
            [item["event_type"] for item in summaries],
            ["earnings", "dividend"],
        )
        earnings_summary = summaries[0]
        self.assertEqual(earnings_summary["event_count"], 3)
        self.assertEqual(earnings_summary["observed_event_count"], 3)

        one_day = earnings_summary["windows"][0]
        self.assertEqual(one_day["trading_days"], 1)
        self.assertEqual(one_day["sample_size"], 3)
        self.assertEqual(one_day["benchmark_sample_size"], 2)
        self.assertEqual(one_day["relative_sample_size"], 2)
        self.assertEqual(one_day["positive_count"], 2)
        self.assertEqual(one_day["negative_count"], 1)
        self.assertEqual(one_day["flat_count"], 0)
        self.assertEqual(one_day["symbol_median_return_percent"], 2.0)
        self.assertEqual(one_day["symbol_min_return_percent"], -1.0)
        self.assertEqual(one_day["symbol_max_return_percent"], 5.0)
        self.assertEqual(one_day["benchmark_median_return_percent"], 0.5)
        self.assertEqual(one_day["relative_median_return_percent"], 0.0)
        self.assertEqual(one_day["completeness_percent"], 100.0)

        twenty_day = earnings_summary["windows"][3]
        self.assertEqual(twenty_day["sample_size"], 1)
        self.assertEqual(twenty_day["completeness_percent"], 33.3333)

        dividend_summary = summaries[1]
        self.assertEqual(dividend_summary["event_count"], 1)
        self.assertEqual(dividend_summary["observed_event_count"], 0)
        self.assertEqual(dividend_summary["windows"][0]["sample_size"], 0)
        self.assertIsNone(
            dividend_summary["windows"][0]["symbol_median_return_percent"]
        )
        self.assertFalse(payload["ai_used"])
        self.assertTrue(payload["informational_only"])
        self.assertTrue(payload["causality_disclaimer"])

    def test_rejects_boolean_non_finite_and_missing_values_from_samples(self) -> None:
        events = [
            _event("earnings-1", "earnings_release", "2026-07-20T00:00:00Z"),
            _event("earnings-2", "earnings_release", "2026-04-20T00:00:00Z"),
        ]
        reactions = [
            _reaction(events[0], [_window(1, True, 1.0, 1.0)]),
            _reaction(events[1], [_window(1, math.nan, 1.0, 1.0)]),
        ]

        payload = self._build(events, reactions)

        one_day = payload["comparison_summaries"][0]["windows"][0]
        self.assertEqual(one_day["sample_size"], 0)
        self.assertEqual(one_day["benchmark_sample_size"], 2)
        self.assertEqual(one_day["relative_sample_size"], 2)
        self.assertIsNone(one_day["symbol_median_return_percent"])
        self.assertEqual(one_day["benchmark_median_return_percent"], 1.0)
        self.assertEqual(one_day["relative_median_return_percent"], 1.0)
        self.assertEqual(one_day["completeness_percent"], 0.0)


if __name__ == "__main__":
    unittest.main()
