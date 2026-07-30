from __future__ import annotations

import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

from src.services.public_market_calendar_service import PublicMarketCalendarService


def _scheduled_event(market: str, symbol: str) -> dict:
    return {
        "event_id": f"{market}-{symbol}",
        "market": market,
        "category": "earnings",
        "title": f"{symbol} scheduled event",
        "summary": None,
        "symbol": symbol,
        "name": symbol,
        "sector": None,
        "event_time": "2026-07-20T00:00:00Z",
        "time_kind": "scheduled",
        "publisher": "unit source",
        "url": "https://example.com/event",
        "source_state": {
            "source": "unit_calendar",
            "status": "fresh",
            "observed_at": "2026-07-20T00:00:00Z",
            "fetched_at": "2026-07-30T00:00:00Z",
            "delay_seconds": None,
            "warning_code": None,
        },
        "classification_source": "provider_schedule",
        "schedule_type": "earnings_release",
        "relevance_score": 80,
        "importance": "high",
        "relevance_reasons": ["provider_schedule"],
        "source_count": 1,
        "source_publishers": ["unit source"],
        "source_records": [],
    }


class PublicEventReactionAvailabilityV137TestCase(unittest.TestCase):
    def test_market_event_candidates_are_loaded_independently(self) -> None:
        from api.v1.endpoints.market_workspace import (
            _load_event_reaction_events,
        )

        def load(sections, _as_of, **_kwargs):
            market = sections[0]["market"]
            if market == "cn":
                raise TimeoutError("CN source timeout")
            symbol = "0700.HK" if market == "hk" else "AAPL"
            return [_scheduled_event(market, symbol)]

        with (
            patch(
                "api.v1.endpoints.market_workspace._public_market_calendar_service.load",
                side_effect=load,
            ),
            patch(
                "api.v1.endpoints.market_workspace._public_home_service.build",
                side_effect=AssertionError(
                    "V137 cold event loading must not build the full market home"
                ),
            ),
        ):
            payload = _load_event_reaction_events()

        self.assertEqual(
            {event["market"] for event in payload["events"]},
            {"hk", "us"},
        )
        sources = {item["market"]: item for item in payload["market_sources"]}
        self.assertEqual(sources["cn"]["status"], "unavailable")
        self.assertEqual(
            sources["cn"]["warning_code"],
            "event_calendar_market_unavailable",
        )
        self.assertEqual(sources["hk"]["status"], "fresh")
        self.assertEqual(sources["hk"]["event_count"], 1)
        self.assertEqual(sources["us"]["status"], "fresh")
        self.assertEqual(sources["us"]["event_count"], 1)

    def test_calendar_reuses_timed_out_inflight_job_instead_of_resubmitting(self) -> None:
        release = threading.Event()
        calls = {"count": 0}

        def slow_history(_symbol: str):
            calls["count"] += 1
            release.wait(timeout=1)
            return [date(2026, 7, 20)]

        sections = [{
            "market": "hk",
            "attention": [{"symbol": "0700.HK", "name": "Tencent"}],
        }]
        with ThreadPoolExecutor(max_workers=1) as executor:
            service = PublicMarketCalendarService(
                yahoo_loader=lambda _symbol: {},
                historical_earnings_loader=slow_history,
                timeout_seconds=0.01,
                executor=executor,
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "calendar_sources_unavailable",
            ):
                service.load(
                    sections,
                    "2026-07-30T00:00:00Z",
                    past_days=45,
                    future_days=0,
                    include_historical=True,
                    fail_on_source_unavailable=True,
                )
            with self.assertRaisesRegex(
                RuntimeError,
                "calendar_sources_unavailable",
            ):
                service.load(
                    sections,
                    "2026-07-30T00:00:00Z",
                    past_days=45,
                    future_days=0,
                    include_historical=True,
                    fail_on_source_unavailable=True,
                )

            self.assertEqual(calls["count"], 1)
            self.assertEqual(len(service._inflight), 1)

            release.set()
            time.sleep(0.03)
            events = service.load(
                sections,
                "2026-07-30T00:00:00Z",
                past_days=45,
                future_days=0,
                include_historical=True,
                fail_on_source_unavailable=True,
            )

        self.assertEqual(calls["count"], 1)
        self.assertEqual(events[0]["market"], "hk")
        self.assertEqual(service._inflight, {})


if __name__ == "__main__":
    unittest.main()
