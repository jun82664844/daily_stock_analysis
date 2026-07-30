# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from src.services.public_market_event_reaction_service import (
    PublicMarketEventReactionService,
)
from src.services.public_symbol_event_archive_service import (
    PublicSymbolEventArchiveService,
)


def _history(symbol: str, rows: list[tuple[str, float, float | None]]) -> dict:
    return {
        "symbol": symbol,
        "source": "yahoo_chart_public",
        "data": [
            {"date": date, "close": close, "volume": volume}
            for date, close, volume in rows
        ],
    }


def _source_state(source: str) -> dict:
    return {
        "source": source,
        "status": "fresh",
        "observed_at": "2026-07-30T00:00:00+00:00",
        "fetched_at": "2026-07-30T00:00:00+00:00",
        "delay_seconds": 0,
        "warning_code": None,
    }


def _event() -> dict:
    return {
        "event_id": "aapl-earnings",
        "market": "us",
        "category": "earnings",
        "title": "Apple earnings release",
        "summary": "Public earnings date.",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "event_time": "2026-07-01T00:00:00Z",
        "time_kind": "observed",
        "publisher": "Yahoo Finance",
        "url": "https://finance.yahoo.com/quote/AAPL",
        "source_state": _source_state("yahoo_earnings_history"),
        "classification_source": "provider_event_history",
        "schedule_type": "earnings_release",
    }


def _reaction(event: dict) -> dict:
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
        "baseline_date": "2026-07-01",
        "benchmark_symbol": "^GSPC",
        "benchmark_name": "标普500指数",
        "status": "partial",
        "windows": [],
        "source_state": _source_state("yahoo_chart_public"),
        "benchmark_source_state": _source_state("yahoo_chart_public"),
        "warning_codes": [],
    }


class PublicMarketEventPriceChartV140TestCase(unittest.TestCase):
    def _service(self, histories: dict[str, dict]) -> PublicMarketEventReactionService:
        def loader(symbol: str) -> dict:
            value = histories[symbol]
            if isinstance(value, Exception):
                raise value
            return value

        return PublicMarketEventReactionService(
            event_loader=lambda: {},
            history_loader=loader,
            clock=lambda: "2026-07-30T00:00:00+00:00",
            timeout_seconds=1,
        )

    def test_builds_normalized_symbol_benchmark_and_relative_series(self) -> None:
        service = self._service({
            "AAPL": _history("AAPL", [
                ("2026-07-01", 100, 1_000),
                ("2026-07-02", 110, 1_200),
                ("2026-07-03", 105, 900),
            ]),
            "^GSPC": _history("^GSPC", [
                ("2026-07-01", 200, None),
                ("2026-07-02", 210, None),
                ("2026-07-03", 220, None),
            ]),
        })

        chart = service.load_price_chart("us", "AAPL", days=366, max_points=560)

        self.assertEqual(chart["status"], "available")
        self.assertEqual(chart["history_symbol"], "AAPL")
        self.assertEqual(chart["benchmark_symbol"], "^GSPC")
        self.assertEqual(chart["benchmark_name"], "标普500指数")
        self.assertEqual(len(chart["points"]), 3)
        self.assertEqual(chart["points"][0]["symbol_change_percent"], 0)
        self.assertEqual(chart["points"][1]["symbol_change_percent"], 10)
        self.assertEqual(chart["points"][1]["benchmark_change_percent"], 5)
        self.assertEqual(chart["points"][1]["relative_change_percent"], 5)
        self.assertEqual(chart["points"][1]["volume"], 1_200)
        self.assertEqual(chart["source_state"]["source"], "yahoo_chart_public")

    def test_uses_exact_dates_and_keeps_missing_benchmark_values_unavailable(self) -> None:
        service = self._service({
            "AAPL": _history("AAPL", [
                ("2026-07-01", 100, 1_000),
                ("2026-07-02", 110, 1_200),
            ]),
            "^GSPC": _history("^GSPC", [
                ("2026-07-01", 200, None),
            ]),
        })

        chart = service.load_price_chart("us", "AAPL", days=366, max_points=560)

        self.assertEqual(chart["status"], "available")
        self.assertIsNone(chart["points"][1]["benchmark_close"])
        self.assertIsNone(chart["points"][1]["benchmark_change_percent"])
        self.assertIsNone(chart["points"][1]["relative_change_percent"])

    def test_applies_day_and_point_bounds(self) -> None:
        service = self._service({
            "AAPL": _history("AAPL", [
                ("2025-01-01", 80, 800),
                ("2026-07-27", 100, 1_000),
                ("2026-07-28", 101, 1_100),
                ("2026-07-29", 102, 1_200),
            ]),
            "^GSPC": _history("^GSPC", [
                ("2025-01-01", 180, None),
                ("2026-07-27", 200, None),
                ("2026-07-28", 202, None),
                ("2026-07-29", 204, None),
            ]),
        })

        chart = service.load_price_chart("us", "AAPL", days=183, max_points=2)

        self.assertEqual(
            [point["date"] for point in chart["points"]],
            ["2026-07-28", "2026-07-29"],
        )
        self.assertEqual(chart["points"][0]["symbol_change_percent"], 0)
        self.assertEqual(chart["points"][1]["symbol_change_percent"], 0.9901)

    def test_keeps_symbol_series_when_benchmark_is_unavailable(self) -> None:
        service = self._service({
            "AAPL": _history("AAPL", [
                ("2026-07-01", 100, 1_000),
                ("2026-07-02", 110, 1_200),
            ]),
            "^GSPC": RuntimeError("benchmark offline"),
        })

        chart = service.load_price_chart("us", "AAPL", days=366, max_points=560)

        self.assertEqual(chart["status"], "partial")
        self.assertEqual(len(chart["points"]), 2)
        self.assertTrue(all(
            point["benchmark_close"] is None
            for point in chart["points"]
        ))
        self.assertIn("benchmark_history_unavailable", chart["warning_codes"])


class PublicSymbolEventArchiveTimelineV140TestCase(unittest.TestCase):
    def test_archive_includes_chart_without_a_second_public_endpoint(self) -> None:
        event = _event()

        class Reactions:
            @staticmethod
            def observe_events(events, *, max_events):
                return [_reaction(events[0])]

            @staticmethod
            def load_price_chart(market, symbol, *, days, max_points):
                return {
                    "status": "available",
                    "history_symbol": symbol,
                    "benchmark_symbol": "^GSPC",
                    "benchmark_name": "标普500指数",
                    "points": [{
                        "date": "2026-07-01",
                        "symbol_close": 100,
                        "benchmark_close": 200,
                        "symbol_change_percent": 0,
                        "benchmark_change_percent": 0,
                        "relative_change_percent": 0,
                        "volume": 1_000,
                    }],
                    "source_state": _source_state("yahoo_chart_public"),
                    "benchmark_source_state": _source_state("yahoo_chart_public"),
                    "warning_codes": [],
                }

        payload = PublicSymbolEventArchiveService(
            calendar_loader=lambda *args, **kwargs: [event],
            reaction_service=Reactions(),
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build("AAPL", months=12)

        self.assertEqual(payload["chart"]["status"], "available")
        self.assertEqual(payload["chart"]["points"][0]["symbol_close"], 100)
        self.assertFalse(payload["ai_used"])
        self.assertTrue(payload["informational_only"])
        self.assertTrue(payload["causality_disclaimer"])

    def test_chart_failure_does_not_remove_event_archive(self) -> None:
        event = _event()

        class Reactions:
            @staticmethod
            def observe_events(events, *, max_events):
                return [_reaction(events[0])]

            @staticmethod
            def load_price_chart(market, symbol, *, days, max_points):
                raise RuntimeError("chart unavailable")

        payload = PublicSymbolEventArchiveService(
            calendar_loader=lambda *args, **kwargs: [event],
            reaction_service=Reactions(),
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build("AAPL", months=12)

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["chart"]["status"], "unavailable")
        self.assertEqual(payload["chart"]["points"], [])
        self.assertIn("symbol_event_timeline_unavailable", payload["warnings"])


if __name__ == "__main__":
    unittest.main()
