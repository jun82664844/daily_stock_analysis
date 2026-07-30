# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _source_state(source: str = "cninfo_report_history") -> dict:
    return {
        "source": source,
        "status": "fresh",
        "observed_at": "2026-07-01T00:00:00+00:00",
        "fetched_at": "2026-07-30T00:00:00+00:00",
        "delay_seconds": 0,
        "warning_code": None,
    }


def _event(
    event_id: str,
    *,
    symbol: str = "600519.SH",
    market: str = "cn",
    schedule_type: str = "earnings_release",
    event_time: str = "2026-07-01T00:00:00Z",
    url: str = "https://www.cninfo.com.cn/",
) -> dict:
    return {
        "event_id": event_id,
        "market": market,
        "category": "earnings",
        "title": f"{symbol} event",
        "summary": "Public source event.",
        "symbol": symbol,
        "name": symbol,
        "event_time": event_time,
        "time_kind": "observed",
        "publisher": "Public source",
        "url": url,
        "source_state": _source_state(),
        "classification_source": "provider_event_history",
        "schedule_type": schedule_type,
        "source_records": [{
            "publisher": "Public source",
            "source": "cninfo_report_history",
            "url": url,
            "event_time": event_time,
            "time_kind": "observed",
        }],
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
        "history_symbol": "600519.SS",
        "baseline_date": "2026-06-30",
        "benchmark_symbol": "000001.SS",
        "benchmark_name": "上证指数",
        "status": "partial",
        "windows": [{
            "trading_days": trading_days,
            "status": "available" if trading_days in {1, 3} else "insufficient_data",
            "observed_date": f"2026-07-{trading_days + 1:02d}" if trading_days in {1, 3} else None,
            "symbol_return_percent": float(trading_days) if trading_days in {1, 3} else None,
            "benchmark_return_percent": 0.5 if trading_days in {1, 3} else None,
            "relative_return_percent": float(trading_days) - 0.5 if trading_days in {1, 3} else None,
            "volume_ratio": 1.2 if trading_days in {1, 3} else None,
        } for trading_days in (1, 3, 5, 20)],
        "source_state": _source_state("yahoo_chart_public"),
        "benchmark_source_state": _source_state("yahoo_chart_public"),
        "warning_codes": ["observation_window_incomplete"],
    }


def _archive_payload(symbol: str = "AAPL", months: int = 12) -> dict:
    event = _event(
        "aapl-earnings",
        symbol=symbol,
        market="us",
        url="https://finance.yahoo.com/",
    )
    item = {
        **_reaction(event),
        "event_type": "earnings",
        "summary": event["summary"],
        "publisher": event["publisher"],
        "source_url": event["url"],
        "event_source_state": _source_state("yahoo_earnings_history"),
    }
    item["history_symbol"] = symbol
    item["benchmark_symbol"] = "^GSPC"
    item["benchmark_name"] = "标普500指数"
    return {
        "symbol": symbol,
        "name": symbol,
        "market": "us",
        "months": months,
        "as_of": "2026-07-30T00:00:00+00:00",
        "items": [item],
        "available_event_types": ["earnings"],
        "warnings": [],
        "ai_used": False,
        "informational_only": True,
        "causality_disclaimer": True,
    }


class PublicSymbolEventArchiveServiceV139TestCase(unittest.TestCase):
    def test_accepts_bare_a_share_symbol_from_market_workspace(self) -> None:
        from src.services.public_symbol_event_archive_service import (
            PublicSymbolEventArchiveService,
        )

        requested: dict = {}

        def calendar_loader(sections, as_of, **kwargs):
            requested["symbol"] = sections[0]["attention"][0]["symbol"]
            return [_event("target", symbol="300750.SZ")]

        class Reactions:
            @staticmethod
            def observe_events(events, *, max_events):
                return [_reaction(events[0])]

        payload = PublicSymbolEventArchiveService(
            calendar_loader=calendar_loader,
            reaction_service=Reactions(),
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build("300750", months=12)

        self.assertEqual(requested["symbol"], "300750.SZ")
        self.assertEqual(payload["symbol"], "300750.SZ")
        self.assertEqual([item["symbol"] for item in payload["items"]], ["300750.SZ"])

    def test_accepts_prefixed_hk_symbol_from_market_workspace(self) -> None:
        from src.services.public_symbol_event_archive_service import (
            PublicSymbolEventArchiveService,
        )

        requested: dict = {}

        def calendar_loader(sections, as_of, **kwargs):
            requested["symbol"] = sections[0]["attention"][0]["symbol"]
            return [_event("target", symbol="9988.HK", market="hk")]

        class Reactions:
            @staticmethod
            def observe_events(events, *, max_events):
                reaction = _reaction(events[0])
                reaction["symbol"] = "9988.HK"
                reaction["market"] = "hk"
                return [reaction]

        payload = PublicSymbolEventArchiveService(
            calendar_loader=calendar_loader,
            reaction_service=Reactions(),
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build("HK09988", months=12)

        self.assertEqual(requested["symbol"], "9988.HK")
        self.assertEqual(payload["symbol"], "9988.HK")
        self.assertEqual(payload["market"], "hk")
        self.assertEqual([item["symbol"] for item in payload["items"]], ["9988.HK"])

    def test_loads_only_the_requested_symbol_and_maps_24_month_window(self) -> None:
        from src.services.public_symbol_event_archive_service import (
            PublicSymbolEventArchiveService,
        )

        requested: dict = {}

        def calendar_loader(sections, as_of, **kwargs):
            requested.update({"sections": sections, "as_of": as_of, **kwargs})
            return [
                _event("target", event_time="2025-01-15T00:00:00Z"),
                _event("other", symbol="000001.SZ"),
            ]

        class Reactions:
            def observe_events(self, events, *, max_events):
                self.events = list(events)
                self.max_events = max_events
                return [_reaction(event) for event in self.events]

        reactions = Reactions()
        payload = PublicSymbolEventArchiveService(
            calendar_loader=calendar_loader,
            reaction_service=reactions,
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build("600519.SH", months=24)

        self.assertEqual(payload["symbol"], "600519.SH")
        self.assertEqual(payload["market"], "cn")
        self.assertEqual(payload["months"], 24)
        self.assertEqual(requested["past_days"], 732)
        self.assertEqual(requested["future_days"], 0)
        self.assertTrue(requested["include_historical"])
        self.assertTrue(requested["include_observed_history"])
        self.assertEqual([item["symbol"] for item in reactions.events], ["600519.SH"])
        self.assertEqual(reactions.max_events, 24)
        self.assertEqual([item["event_id"] for item in payload["items"]], ["target"])
        self.assertFalse(payload["ai_used"])
        self.assertTrue(payload["informational_only"])
        self.assertTrue(payload["causality_disclaimer"])

    def test_preserves_event_metadata_and_rejects_unsafe_source_url(self) -> None:
        from src.services.public_symbol_event_archive_service import (
            PublicSymbolEventArchiveService,
        )

        event = _event("unsafe", url="javascript:alert(1)")

        class Reactions:
            @staticmethod
            def observe_events(events, *, max_events):
                return [_reaction(events[0])]

        payload = PublicSymbolEventArchiveService(
            calendar_loader=lambda *args, **kwargs: [event],
            reaction_service=Reactions(),
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build("600519.SH", months=6)

        item = payload["items"][0]
        self.assertEqual(item["publisher"], "Public source")
        self.assertEqual(item["summary"], "Public source event.")
        self.assertIsNone(item["source_url"])
        self.assertEqual(item["event_type"], "earnings")
        self.assertEqual(item["windows"][0]["trading_days"], 1)

    def test_keeps_an_event_when_price_observations_are_unavailable(self) -> None:
        from src.services.public_symbol_event_archive_service import (
            PublicSymbolEventArchiveService,
        )

        event = _event("without-history", schedule_type="ex_dividend")

        class Reactions:
            @staticmethod
            def observe_events(events, *, max_events):
                return []

        payload = PublicSymbolEventArchiveService(
            calendar_loader=lambda *args, **kwargs: [event],
            reaction_service=Reactions(),
            clock=lambda: "2026-07-30T00:00:00+00:00",
        ).build("600519.SH", months=12)

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["event_type"], "dividend")
        self.assertEqual(payload["items"][0]["status"], "unavailable")
        self.assertEqual(payload["items"][0]["windows"], [])
        self.assertIn("event_price_observation_unavailable", payload["items"][0]["warning_codes"])

    def test_rejects_unsupported_symbols_and_months(self) -> None:
        from src.services.public_symbol_event_archive_service import (
            PublicSymbolEventArchiveService,
        )

        service = PublicSymbolEventArchiveService(
            calendar_loader=lambda *args, **kwargs: [],
            reaction_service=object(),
        )
        with self.assertRaisesRegex(ValueError, "invalid_symbol"):
            service.build("BTC-USD", months=12)
        with self.assertRaisesRegex(ValueError, "invalid_months"):
            service.build("AAPL", months=18)


class PublicSymbolEventArchiveApiV139TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_archive_endpoint_is_public_no_ai_and_independently_rate_limited(self) -> None:
        env = {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "v139.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_SYMBOL_EVENT_ARCHIVE_V139_ENABLED": "true",
            "PLATFORM_USER_AUTH_ENABLED": "true",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "api.v1.endpoints.market_workspace._public_symbol_event_archive_service.build",
                return_value=_archive_payload(),
            ) as build,
            patch(
                "api.v1.endpoints.market_workspace.check_platform_rate_limit",
                return_value=None,
            ) as rate_limit,
            patch(
                "api.v1.endpoints.market_workspace.platform_identity_from_request",
                side_effect=AssertionError("V139 archive must stay anonymous"),
            ),
        ):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get(
                "/api/v1/market-workspace/symbol/AAPL/event-archive",
                params={"months": 12},
            )
            client.close()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ai_used"])
        self.assertTrue(response.json()["causality_disclaimer"])
        build.assert_called_once_with("AAPL", months=12)
        self.assertEqual(
            rate_limit.call_args.args[1],
            "market_workspace_symbol_event_archive",
        )
        self.assertTrue(rate_limit.call_args.kwargs["enforce"])

    def test_archive_endpoint_rejects_disabled_feature(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
                "PLATFORM_PUBLIC_SYMBOL_EVENT_ARCHIVE_V139_ENABLED": "false",
            },
            clear=False,
        ):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get(
                "/api/v1/market-workspace/symbol/AAPL/event-archive"
            )
            client.close()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "http_error")
        self.assertIn("symbol_event_archive_disabled", response.json()["message"])


if __name__ == "__main__":
    unittest.main()
