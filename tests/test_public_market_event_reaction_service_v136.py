from __future__ import annotations

import unittest
from typing import Any, Dict, List
from unittest.mock import patch


def _event(
    event_id: str,
    *,
    market: str = "cn",
    symbol: str | None = "600519.SH",
    event_time: str = "2026-07-20T00:00:00+00:00",
    schedule_type: str = "earnings_release",
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "market": market,
        "category": "macro" if schedule_type == "macro_policy" else "earnings",
        "title": f"Event {event_id}",
        "summary": None,
        "symbol": symbol,
        "name": symbol or "FOMC",
        "sector": None,
        "event_time": event_time,
        "time_kind": "scheduled",
        "publisher": "public schedule",
        "url": "https://example.com/event",
        "source_state": {
            "source": "provider_schedule",
            "status": "fresh",
            "observed_at": event_time,
            "fetched_at": "2026-07-30T00:00:00+00:00",
            "delay_seconds": None,
            "warning_code": None,
        },
        "classification_source": "provider_schedule",
        "schedule_type": schedule_type,
        "relevance_score": 85,
        "importance": "high",
        "relevance_reasons": ["provider_schedule"],
        "source_count": 1,
        "source_publishers": ["public schedule"],
        "source_records": [],
    }


def _rows(
    closes: List[float],
    *,
    start_day: int = 13,
    volumes: List[float] | None = None,
) -> List[Dict[str, Any]]:
    result = []
    for index, close in enumerate(closes):
        day = start_day + index
        result.append({
            "date": f"2026-07-{day:02d}",
            "close": close,
            "volume": (volumes or [100.0] * len(closes))[index],
        })
    return result


class PublicMarketEventReactionServiceV136TestCase(unittest.TestCase):
    def test_calculates_observed_windows_against_market_benchmark(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        asset_rows = [
            {"date": "2026-07-13", "close": 96.0, "volume": 100.0},
            {"date": "2026-07-14", "close": 97.0, "volume": 100.0},
            {"date": "2026-07-15", "close": 98.0, "volume": 100.0},
            {"date": "2026-07-16", "close": 99.0, "volume": 100.0},
            {"date": "2026-07-17", "close": 100.0, "volume": 100.0},
            {"date": "2026-07-20", "close": 102.0, "volume": 200.0},
            {"date": "2026-07-21", "close": 103.0, "volume": 150.0},
            {"date": "2026-07-22", "close": 105.0, "volume": 100.0},
            {"date": "2026-07-23", "close": 104.0, "volume": 120.0},
            {"date": "2026-07-24", "close": 106.0, "volume": 130.0},
        ]
        benchmark_closes = [960.0, 970.0, 980.0, 990.0, 1000.0, 1010.0, 1020.0, 1030.0, 1040.0, 1050.0]
        benchmark_rows = [
            {"date": row["date"], "close": benchmark_closes[index], "volume": None}
            for index, row in enumerate(asset_rows)
        ]

        def history_loader(symbol: str) -> Dict[str, Any]:
            rows = benchmark_rows if symbol == "000001.SS" else asset_rows
            return {"symbol": symbol, "source": "yahoo_chart_public", "data": rows}

        payload = PublicMarketEventReactionService(
            event_loader=lambda: {"events": [_event("cn-1")]},
            history_loader=history_loader,
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build()

        self.assertFalse(payload["ai_used"])
        self.assertTrue(payload["informational_only"])
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["symbol"], "600519.SH")
        self.assertEqual(item["history_symbol"], "600519.SS")
        self.assertEqual(item["benchmark_symbol"], "000001.SS")
        self.assertEqual(item["baseline_date"], "2026-07-20")
        one_day = item["windows"][0]
        self.assertEqual(one_day["trading_days"], 1)
        self.assertEqual(one_day["status"], "available")
        self.assertEqual(one_day["observed_date"], "2026-07-21")
        self.assertEqual(one_day["symbol_return_percent"], 0.9804)
        self.assertEqual(one_day["benchmark_return_percent"], 0.9901)
        self.assertEqual(one_day["relative_return_percent"], -0.0097)
        self.assertEqual(one_day["volume_ratio"], 1.5)

    def test_waits_until_the_market_date_has_finished_before_selecting_event(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        payload = PublicMarketEventReactionService(
            event_loader=lambda: {
                "events": [
                    _event(
                        "same-us-date",
                        market="us",
                        symbol="AAPL",
                        event_time="2026-07-30T00:00:00+00:00",
                    )
                ]
            },
            history_loader=lambda symbol: {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": _rows([95, 96, 97, 98, 100, 101]),
            },
            clock=lambda: "2026-07-30T16:00:00+00:00",
        ).build()

        self.assertEqual(payload["items"], [])
        self.assertIn("event_reaction_no_eligible_events", payload["warnings"])

    def test_keeps_only_past_provider_schedules_and_caps_results(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        symbols = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "ORCL", "INTC"]
        events = [
            _event(f"valid-{index}", market="us", symbol=symbol)
            for index, symbol in enumerate(symbols)
        ]
        events.extend([
            {
                **_event("news-event"),
                "time_kind": "published",
                "classification_source": "keyword_rules",
            },
            _event("future-event", event_time="2026-08-05T00:00:00+00:00"),
        ])

        payload = PublicMarketEventReactionService(
            event_loader=lambda: {"events": events},
            history_loader=lambda symbol: {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": _rows([95, 96, 97, 98, 100, 101]),
            },
            clock=lambda: "2026-07-30T00:00:00+00:00",
            max_events=6,
        ).build()

        self.assertLessEqual(len(payload["items"]), 6)
        self.assertNotIn("news-event", {item["event_id"] for item in payload["items"]})
        self.assertNotIn("future-event", {item["event_id"] for item in payload["items"]})

    def test_marks_unobserved_windows_pending_without_inventing_values(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        rows = [
            {"date": "2026-07-13", "close": 96.0, "volume": 100.0},
            {"date": "2026-07-14", "close": 97.0, "volume": 100.0},
            {"date": "2026-07-15", "close": 98.0, "volume": 100.0},
            {"date": "2026-07-16", "close": 99.0, "volume": 100.0},
            {"date": "2026-07-17", "close": 100.0, "volume": 100.0},
            {"date": "2026-07-20", "close": 101.0, "volume": 110.0},
            {"date": "2026-07-21", "close": 102.0, "volume": 120.0},
        ]
        payload = PublicMarketEventReactionService(
            event_loader=lambda: {"events": [_event("recent")]},
            history_loader=lambda symbol: {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": rows,
            },
            clock=lambda: "2026-07-21T00:00:00+00:00",
        ).build()

        windows = payload["items"][0]["windows"]
        self.assertEqual(windows[0]["status"], "available")
        self.assertEqual(windows[1]["status"], "pending")
        self.assertIsNone(windows[1]["symbol_return_percent"])
        self.assertIsNone(windows[1]["relative_return_percent"])
        self.assertIsNone(windows[1]["volume_ratio"])

    def test_marks_old_incomplete_history_as_insufficient_instead_of_pending(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        rows = [
            {"date": "2026-06-30", "close": 100.0, "volume": 100.0},
            {"date": "2026-07-01", "close": 101.0, "volume": 110.0},
        ]
        payload = PublicMarketEventReactionService(
            event_loader=lambda: {
                "events": [_event("old", event_time="2026-07-01T00:00:00+00:00")]
            },
            history_loader=lambda symbol: {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": rows,
            },
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build()

        windows = payload["items"][0]["windows"]
        self.assertEqual(windows[0]["status"], "insufficient_data")
        self.assertEqual(windows[1]["status"], "insufficient_data")
        self.assertEqual(windows[3]["status"], "insufficient_data")

    def test_uses_market_sessions_instead_of_skipping_suspended_security_days(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        asset_rows = [
            {"date": "2026-07-17", "close": 99.0, "volume": 90.0},
            {"date": "2026-07-20", "close": 100.0, "volume": 100.0},
            {"date": "2026-07-24", "close": 110.0, "volume": 200.0},
        ]
        benchmark_rows = [
            {"date": f"2026-07-{day:02d}", "close": 1000.0 + index, "volume": None}
            for index, day in enumerate((17, 20, 21, 22, 23, 24))
        ]

        def history_loader(symbol: str) -> Dict[str, Any]:
            rows = benchmark_rows if symbol == "000001.SS" else asset_rows
            return {"symbol": symbol, "source": "yahoo_chart_public", "data": rows}

        payload = PublicMarketEventReactionService(
            event_loader=lambda: {"events": [_event("suspended")]},
            history_loader=history_loader,
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build()

        one_day = payload["items"][0]["windows"][0]
        self.assertEqual(one_day["status"], "insufficient_data")
        self.assertIsNone(one_day["observed_date"])
        self.assertIsNone(one_day["symbol_return_percent"])

    def test_keeps_weekend_window_pending_until_a_later_market_session_exists(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        rows = [
            {"date": "2026-07-16", "close": 99.0, "volume": 90.0},
            {"date": "2026-07-17", "close": 100.0, "volume": 100.0},
        ]
        payload = PublicMarketEventReactionService(
            event_loader=lambda: {
                "events": [_event("weekend", event_time="2026-07-17T00:00:00+00:00")]
            },
            history_loader=lambda symbol: {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": rows,
            },
            clock=lambda: "2026-07-19T12:00:00+00:00",
        ).build()

        self.assertEqual(payload["items"][0]["windows"][0]["status"], "pending")

    def test_calculates_twenty_sessions_after_the_event_date_close(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        rows = [
            {
                "date": f"2026-06-{day:02d}" if day <= 30 else f"2026-07-{day - 30:02d}",
                "close": 100.0 + index,
                "volume": 100.0,
            }
            for index, day in enumerate(range(25, 56))
        ]
        payload = PublicMarketEventReactionService(
            event_loader=lambda: {
                "events": [_event("twenty-day", event_time="2026-06-30T00:00:00+00:00")]
            },
            history_loader=lambda symbol: {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": rows,
            },
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build()

        item = payload["items"][0]
        self.assertEqual(item["baseline_date"], "2026-06-30")
        self.assertEqual(item["windows"][3]["status"], "available")
        self.assertEqual(item["windows"][3]["observed_date"], "2026-07-20")

    def test_normalizes_three_market_symbols_and_reuses_benchmarks(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        calls: List[str] = []
        events = [
            _event("cn", market="cn", symbol="600519.SH"),
            _event("hk", market="hk", symbol="0700.HK"),
            _event("us", market="us", symbol="AAPL"),
        ]

        def history_loader(symbol: str) -> Dict[str, Any]:
            calls.append(symbol)
            return {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": _rows([95, 96, 97, 98, 100, 101, 102, 103, 104, 105]),
            }

        payload = PublicMarketEventReactionService(
            event_loader=lambda: {"events": events},
            history_loader=history_loader,
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build()

        histories = {item["history_symbol"] for item in payload["items"]}
        benchmarks = {item["benchmark_symbol"] for item in payload["items"]}
        self.assertEqual(histories, {"600519.SS", "0700.HK", "AAPL"})
        self.assertEqual(benchmarks, {"000001.SS", "^HSI", "^GSPC"})
        self.assertEqual(len(calls), len(set(calls)))

    def test_uses_us_benchmark_as_macro_observation_subject(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        payload = PublicMarketEventReactionService(
            event_loader=lambda: {
                "events": [
                    _event(
                        "fomc",
                        market="us",
                        symbol=None,
                        schedule_type="macro_policy",
                    )
                ]
            },
            history_loader=lambda symbol: {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": _rows([95, 96, 97, 98, 100, 101, 102, 103]),
            },
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build()

        item = payload["items"][0]
        self.assertEqual(item["subject_type"], "market_benchmark")
        self.assertEqual(item["symbol"], "^GSPC")
        self.assertEqual(item["history_symbol"], "^GSPC")
        self.assertIsNone(item["benchmark_symbol"])
        self.assertIsNone(item["windows"][0]["benchmark_return_percent"])
        self.assertIsNone(item["windows"][0]["relative_return_percent"])

    def test_history_failure_is_isolated_and_reported_without_fake_values(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        def history_loader(symbol: str) -> Dict[str, Any]:
            if symbol == "AAPL":
                raise TimeoutError("source timeout")
            return {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": _rows([95, 96, 97, 98, 100, 101, 102]),
            }

        payload = PublicMarketEventReactionService(
            event_loader=lambda: {
                "events": [
                    _event(
                        "failed",
                        market="us",
                        symbol="AAPL",
                        event_time="2026-07-18T00:00:00+00:00",
                    ),
                    _event(
                        "available",
                        market="hk",
                        symbol="0700.HK",
                        event_time="2026-07-18T00:00:00+00:00",
                    ),
                ]
            },
            history_loader=history_loader,
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build()

        by_id = {item["event_id"]: item for item in payload["items"]}
        self.assertEqual(by_id["failed"]["status"], "unavailable")
        self.assertTrue(all(window["symbol_return_percent"] is None for window in by_id["failed"]["windows"]))
        self.assertEqual(by_id["available"]["windows"][0]["status"], "available")
        self.assertIn("event_reaction_source_unavailable", payload["warnings"])

    def test_reuses_response_cache_and_falls_back_to_bounded_stale_history(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        monotonic = [100.0]
        fail = [False]
        calls: List[str] = []

        def history_loader(symbol: str) -> Dict[str, Any]:
            calls.append(symbol)
            if fail[0]:
                raise TimeoutError("refresh failed")
            return {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": _rows([95, 96, 97, 98, 100, 101, 102, 103, 104, 105]),
            }

        service = PublicMarketEventReactionService(
            event_loader=lambda: {"events": [_event("cached")]},
            history_loader=history_loader,
            clock=lambda: "2026-07-30T00:00:00+00:00",
            monotonic_clock=lambda: monotonic[0],
            cache_ttl_seconds=10,
            stale_ttl_seconds=60,
        )
        first = service.build()
        cached = service.build()
        self.assertFalse(first["cache"]["hit"])
        self.assertTrue(cached["cache"]["hit"])
        self.assertEqual(len(calls), 2)

        monotonic[0] += 11
        fail[0] = True
        stale = service.build()
        self.assertEqual(stale["items"][0]["source_state"]["status"], "stale")
        self.assertEqual(stale["items"][0]["windows"][0]["status"], "available")
        self.assertIn("subject_history_stale", stale["items"][0]["warning_codes"])
        self.assertEqual(
            stale["items"][0]["source_state"]["fetched_at"],
            first["items"][0]["source_state"]["fetched_at"],
        )

    def test_event_loader_failure_is_not_cached_as_a_real_empty_result(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        calls = {"count": 0}

        def event_loader() -> Dict[str, Any]:
            calls["count"] += 1
            if calls["count"] == 1:
                raise TimeoutError("calendar timeout")
            return {"events": [_event("recovered")]}

        service = PublicMarketEventReactionService(
            event_loader=event_loader,
            history_loader=lambda symbol: {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": _rows([95, 96, 97, 98, 100, 101, 102, 103]),
            },
            clock=lambda: "2026-07-30T00:00:00+00:00",
        )

        failed = service.build()
        recovered = service.build()

        self.assertEqual(failed["items"], [])
        self.assertIn("event_reaction_events_unavailable", failed["warnings"])
        self.assertEqual(recovered["items"][0]["event_id"], "recovered")
        self.assertEqual(calls["count"], 2)

    def test_history_cache_has_a_global_entry_limit(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        service = PublicMarketEventReactionService(
            event_loader=lambda: {"events": []},
            max_history_cache_entries=2,
        )
        for symbol in ("AAPL", "MSFT", "NVDA"):
            service._write_history_cache(
                symbol,
                {
                    "symbol": symbol,
                    "source": "yahoo_chart_public",
                    "fetched_at": "2026-07-30T00:00:00+00:00",
                    "data": _rows([100, 101]),
                },
            )

        self.assertEqual(list(service._history_cache), ["MSFT", "NVDA"])

    def test_rejects_unsafe_symbols_and_oversized_yahoo_responses(self) -> None:
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        service = PublicMarketEventReactionService(event_loader=lambda: {"events": []})
        self.assertTrue(service._safe_yahoo_symbol("600519.SS"))
        self.assertTrue(service._safe_yahoo_symbol("^GSPC"))
        self.assertFalse(service._safe_yahoo_symbol("AAPL/../../secret"))

        class OversizedResponse:
            def raise_for_status(self) -> None:
                return None

            def iter_content(self, chunk_size: int):
                del chunk_size
                yield b"x" * (769 * 1024)

            def close(self) -> None:
                return None

        with patch(
            "src.services.public_market_event_reaction_service.requests.get",
            return_value=OversizedResponse(),
        ):
            with self.assertRaisesRegex(ValueError, "response too large"):
                service._fetch_yahoo_history("AAPL")


if __name__ == "__main__":
    unittest.main()
