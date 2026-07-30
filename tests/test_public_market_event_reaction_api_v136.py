# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Request
from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _reaction_payload() -> dict:
    return {
        "as_of": "2026-07-30T00:00:00+00:00",
        "items": [{
            "event_id": "event-aapl",
            "market": "us",
            "title": "Apple earnings release",
            "symbol": "AAPL",
            "name": "Apple",
            "subject_type": "security",
            "event_time": "2026-07-20T00:00:00+00:00",
            "schedule_type": "earnings_release",
            "history_symbol": "AAPL",
            "baseline_date": "2026-07-17",
            "benchmark_symbol": "^GSPC",
            "benchmark_name": "标普500指数",
            "status": "partial",
            "windows": [{
                "trading_days": 1,
                "status": "available",
                "observed_date": "2026-07-20",
                "symbol_return_percent": 2.0,
                "benchmark_return_percent": 1.0,
                "relative_return_percent": 1.0,
                "volume_ratio": 1.5,
            }, {
                "trading_days": 3,
                "status": "pending",
                "observed_date": None,
                "symbol_return_percent": None,
                "benchmark_return_percent": None,
                "relative_return_percent": None,
                "volume_ratio": None,
            }, {
                "trading_days": 5,
                "status": "pending",
                "observed_date": None,
                "symbol_return_percent": None,
                "benchmark_return_percent": None,
                "relative_return_percent": None,
                "volume_ratio": None,
            }, {
                "trading_days": 20,
                "status": "pending",
                "observed_date": None,
                "symbol_return_percent": None,
                "benchmark_return_percent": None,
                "relative_return_percent": None,
                "volume_ratio": None,
            }],
            "source_state": {
                "source": "yahoo_chart_public",
                "status": "fresh",
                "observed_at": "2026-07-20",
                "fetched_at": "2026-07-30T00:00:00+00:00",
            },
            "benchmark_source_state": {
                "source": "yahoo_chart_public",
                "status": "fresh",
                "observed_at": "2026-07-20",
                "fetched_at": "2026-07-30T00:00:00+00:00",
            },
            "warning_codes": ["observation_window_incomplete"],
        }],
        "warnings": [],
        "cache": {"hit": False, "age_seconds": 0, "ttl_seconds": 900},
        "ai_used": False,
        "informational_only": True,
    }


class PublicMarketEventReactionApiV136TestCase(unittest.TestCase):
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

    def test_schema_accepts_bounded_observed_reaction_payload(self) -> None:
        from api.v1.schemas.market_workspace import PublicMarketEventReactionResponse

        body = PublicMarketEventReactionResponse.model_validate(_reaction_payload())

        self.assertEqual(body.items[0].windows[0].trading_days, 1)
        self.assertEqual(body.items[0].windows[0].relative_return_percent, 1.0)
        self.assertFalse(body.ai_used)
        self.assertTrue(body.informational_only)

    def test_event_reactions_are_public_and_use_an_independent_rate_bucket(self) -> None:
        env = {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "event-reactions.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED": "true",
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED": "true",
            "PLATFORM_USER_AUTH_ENABLED": "true",
            "ADMIN_AUTH_ENABLED": "true",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "api.v1.endpoints.market_workspace._public_event_reaction_service.build",
                return_value=_reaction_payload(),
            ),
            patch(
                "api.v1.endpoints.market_workspace.check_platform_rate_limit",
                return_value=None,
            ) as rate_limit,
            patch(
                "api.v1.endpoints.market_workspace.platform_identity_from_request",
                side_effect=AssertionError("public V136 endpoint must stay anonymous"),
            ),
        ):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get("/api/v1/market-workspace/event-reactions")
            client.close()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ai_used"])
        self.assertEqual(response.json()["items"][0]["event_id"], "event-aapl")
        self.assertEqual(rate_limit.call_args.args[1], "market_workspace_event_reactions")
        self.assertTrue(rate_limit.call_args.kwargs["enforce"])

    def test_event_reaction_loader_requests_a_bounded_historical_calendar(self) -> None:
        from api.v1.endpoints.market_workspace import _load_event_reaction_events

        with (
            patch(
                "api.v1.endpoints.market_workspace._public_home_service.build",
                return_value={
                    "as_of": "2026-07-30T00:00:00+00:00",
                    "markets": [{"market": "cn"}, {"market": "hk"}, {"market": "us"}],
                },
            ),
            patch(
                "api.v1.endpoints.market_workspace._public_market_calendar_service.load",
                return_value=[{"event_id": "historical-event"}],
            ) as calendar_load,
        ):
            payload = _load_event_reaction_events()

        self.assertEqual(payload["events"][0]["event_id"], "historical-event")
        self.assertEqual(calendar_load.call_args.kwargs["past_days"], 45)
        self.assertEqual(calendar_load.call_args.kwargs["future_days"], 0)
        self.assertTrue(calendar_load.call_args.kwargs["newest_first"])
        self.assertTrue(calendar_load.call_args.kwargs["fail_on_source_unavailable"])

    def test_event_reaction_rate_limit_is_enforced_when_global_limiter_is_disabled(self) -> None:
        from src.platform_rate_limit import reset_platform_rate_limits

        env = {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "event-reactions-limit.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED": "true",
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED": "true",
            "PLATFORM_RATE_LIMIT_ENABLED": "false",
            "PLATFORM_RATE_LIMIT_MARKET_WORKSPACE_EVENT_REACTIONS_MAX": "1",
            "PLATFORM_RATE_LIMIT_WINDOW_SECONDS": "60",
        }
        reset_platform_rate_limits()
        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "api.v1.endpoints.market_workspace._public_event_reaction_service.build",
                return_value=_reaction_payload(),
            ),
        ):
            client = TestClient(create_app(static_dir=self.static_dir))
            first = client.get("/api/v1/market-workspace/event-reactions")
            second = client.get("/api/v1/market-workspace/event-reactions")
            client.close()
        reset_platform_rate_limits()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error"], "rate_limited")

    def test_public_rate_limit_bucket_count_is_bounded(self) -> None:
        from src.platform_rate_limit import (
            _buckets,
            check_platform_rate_limit,
            reset_platform_rate_limits,
        )

        reset_platform_rate_limits()
        with patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "bounded-limit.sqlite"),
                "PLATFORM_RATE_LIMIT_MAX_BUCKETS": "2",
                "PLATFORM_RATE_LIMIT_WINDOW_SECONDS": "60",
            },
            clear=False,
        ):
            for index in range(3):
                request = Request({
                    "type": "http",
                    "client": (f"198.51.100.{index + 1}", 12345),
                    "headers": [],
                })
                limited = check_platform_rate_limit(
                    request,
                    "market_workspace_event_reactions",
                    enforce=True,
                )
                if index < 2:
                    self.assertIsNone(limited)
                else:
                    self.assertEqual(limited.status_code, 429)

        self.assertLessEqual(len(_buckets), 2)
        reset_platform_rate_limits()

    def test_new_identity_cannot_flush_an_active_rate_limit_bucket(self) -> None:
        from src.platform_rate_limit import (
            _buckets,
            check_platform_rate_limit,
            reset_platform_rate_limits,
        )

        def request_for(address: str) -> Request:
            return Request({
                "type": "http",
                "client": (address, 12345),
                "headers": [],
            })

        reset_platform_rate_limits()
        with patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "stable-limit.sqlite"),
                "PLATFORM_RATE_LIMIT_MAX_BUCKETS": "2",
                "PLATFORM_RATE_LIMIT_MARKET_WORKSPACE_EVENT_REACTIONS_MAX": "1",
                "PLATFORM_RATE_LIMIT_WINDOW_SECONDS": "60",
            },
            clear=False,
        ):
            self.assertIsNone(check_platform_rate_limit(
                request_for("198.51.100.1"),
                "market_workspace_event_reactions",
                enforce=True,
            ))
            self.assertIsNone(check_platform_rate_limit(
                request_for("198.51.100.2"),
                "market_workspace_event_reactions",
                enforce=True,
            ))
            capacity_limited = check_platform_rate_limit(
                request_for("198.51.100.3"),
                "market_workspace_event_reactions",
                enforce=True,
            )
            original_limited = check_platform_rate_limit(
                request_for("198.51.100.1"),
                "market_workspace_event_reactions",
                enforce=True,
            )

        self.assertEqual(capacity_limited.status_code, 429)
        self.assertEqual(original_limited.status_code, 429)
        self.assertEqual(len(_buckets), 2)
        reset_platform_rate_limits()

    def test_event_reactions_are_404_when_v136_is_disabled(self) -> None:
        env = {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "event-reactions-disabled.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED": "true",
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get("/api/v1/market-workspace/event-reactions")
            client.close()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["error"],
            "public_event_reactions_disabled",
        )

    def test_event_reaction_service_failure_returns_safe_503(self) -> None:
        env = {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "event-reactions-failed.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED": "true",
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED": "true",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "api.v1.endpoints.market_workspace._public_event_reaction_service.build",
                side_effect=RuntimeError("secret provider detail"),
            ),
        ):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get("/api/v1/market-workspace/event-reactions")
            client.close()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"],
            "event_reactions_unavailable",
        )
        self.assertNotIn("secret provider detail", response.text)


if __name__ == "__main__":
    unittest.main()
