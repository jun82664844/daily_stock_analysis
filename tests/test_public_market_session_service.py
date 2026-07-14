from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace


def _context(
    phase: str,
    *,
    minutes_to_open: int | None = None,
    minutes_to_close: int | None = None,
    warnings: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        phase=SimpleNamespace(value=phase),
        market_local_time=datetime(2026, 7, 14, 9, 30, tzinfo=timezone.utc),
        minutes_to_open=minutes_to_open,
        minutes_to_close=minutes_to_close,
        warnings=list(warnings or []),
    )


class PublicMarketSessionServiceTestCase(unittest.TestCase):
    def test_maps_exchange_phases_without_guessing(self) -> None:
        from src.services.public_market_session_service import PublicMarketSessionService

        expected = {
            "premarket": "closed",
            "intraday": "open",
            "lunch_break": "closed",
            "closing_auction": "open",
            "postmarket": "closed",
            "non_trading": "closed",
            "unknown": "unknown",
        }
        for phase, session_state in expected.items():
            with self.subTest(phase=phase):
                service = PublicMarketSessionService(
                    context_builder=lambda **_: _context(phase)
                )
                payload = service.resolve("cn", "2026-07-14T01:30:00Z")
                self.assertEqual(payload["session_phase"], phase)
                self.assertEqual(payload["session_state"], session_state)

    def test_exposes_market_local_time_countdown_and_calendar_source(self) -> None:
        from src.services.public_market_session_service import PublicMarketSessionService

        service = PublicMarketSessionService(
            context_builder=lambda **_: _context(
                "premarket",
                minutes_to_open=30,
                warnings=["calendar_notice"],
            )
        )

        payload = service.resolve("us", "2026-07-14T12:00:00Z")

        self.assertEqual(payload["market_local_time"], "2026-07-14T09:30:00+00:00")
        self.assertEqual(payload["minutes_to_open"], 30)
        self.assertIsNone(payload["minutes_to_close"])
        self.assertEqual(payload["session_source"], "exchange_calendar")
        self.assertEqual(payload["session_warning_codes"], ["calendar_notice"])

    def test_calendar_failure_degrades_to_unknown(self) -> None:
        from src.services.public_market_session_service import PublicMarketSessionService

        def fail(**_: object) -> object:
            raise RuntimeError("calendar unavailable")

        payload = PublicMarketSessionService(context_builder=fail).resolve(
            "hk", datetime(2026, 7, 14, tzinfo=timezone.utc)
        )

        self.assertEqual(payload["session_state"], "unknown")
        self.assertEqual(payload["session_phase"], "unknown")
        self.assertEqual(payload["session_source"], "unavailable")
        self.assertIn("calendar_error", payload["session_warning_codes"])


if __name__ == "__main__":
    unittest.main()
