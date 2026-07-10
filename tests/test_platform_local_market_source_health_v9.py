# -*- coding: utf-8 -*-
import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache
from src.services.market_source_health import MarketSourceHealthRegistry
from src.storage import DatabaseManager


def _history_rows(count: int = 24) -> list[dict]:
    return [
        {
            "date": f"2026-06-{day:02d}",
            "open": 90.0 + day,
            "high": 92.0 + day,
            "low": 89.0 + day,
            "close": 91.0 + day,
            "volume": 1000 + day * 10,
        }
        for day in range(1, count + 1)
    ]


def _quote(code: str = "AAPL", *, source: str = "unit_quote") -> dict:
    return {
        "stock_code": code,
        "stock_name": code,
        "current_price": 200.0,
        "change_percent": 1.5,
        "volume": 1000,
        "amount": 200000.0,
        "source": source,
        "update_time": "2026-07-02T09:30:00",
    }


def _history(code: str = "AAPL", *, source: str = "unit_history") -> dict:
    return {
        "stock_code": code,
        "stock_name": code,
        "source": source,
        "period": "daily",
        "data": _history_rows(),
    }


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class PlatformLocalMarketSourceHealthV9TestCase(unittest.TestCase):
    def test_source_health_cools_down_after_repeated_failures_and_recovers_on_success(self) -> None:
        clock = FakeClock()
        health = MarketSourceHealthRegistry(failure_threshold=2, cooling_seconds=30, clock=clock)

        self.assertFalse(health.should_skip("quote:yahoo_chart"))
        health.record_timeout("quote:yahoo_chart", elapsed_ms=20)
        self.assertEqual(health.snapshot("quote:yahoo_chart")["status"], "ok")
        health.record_error("quote:yahoo_chart", elapsed_ms=25)

        cooling = health.snapshot("quote:yahoo_chart")
        self.assertEqual(cooling["status"], "cooling_down")
        self.assertEqual(cooling["last_error"], "error")
        self.assertTrue(health.should_skip("quote:yahoo_chart"))

        clock.advance(31)
        self.assertFalse(health.should_skip("quote:yahoo_chart"))
        health.record_success("quote:yahoo_chart", elapsed_ms=12)

        recovered = health.snapshot("quote:yahoo_chart")
        self.assertEqual(recovered["status"], "ok")
        self.assertEqual(recovered["consecutive_failures"], 0)
        self.assertIsNone(recovered["last_error"])

    def test_basic_snapshot_skips_cooling_quote_source_without_extra_live_call(self) -> None:
        stock_service = MagicMock()

        def slow_quote(_code: str):
            time.sleep(0.2)
            return _quote(_code, source="slow_quote")

        stock_service.get_realtime_quote.side_effect = slow_quote
        stock_service.get_history_data.return_value = _history("AAPL", source="unit_history")
        health = MarketSourceHealthRegistry(failure_threshold=2, cooling_seconds=60)
        service = BasicQueryService(
            stock_service=stock_service,
            cache=MarketDataCache(default_ttl_seconds=60),
            fetch_timeout_seconds=0.01,
            source_health=health,
        )

        with patch.object(service, "_comparison_targets_with_reference_quotes", return_value=[]):
            service.get_snapshot("AAPL")
            service.get_snapshot("AAPL")
        self.assertEqual(stock_service.get_realtime_quote.call_count, 2)

        with patch.object(service, "_comparison_targets_with_reference_quotes", return_value=[]):
            snapshot = service.get_snapshot("AAPL")

        self.assertEqual(stock_service.get_realtime_quote.call_count, 2)
        self.assertFalse(snapshot["ai_used"])
        self.assertEqual(snapshot["quote"]["freshness"], "unavailable")
        self.assertEqual(snapshot["diagnostics"]["errors"]["quote"], "cooling_down")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["quote"], "none")
        self.assertEqual(snapshot["diagnostics"]["source_health"]["quote"]["status"], "cooling_down")
        self.assertTrue(any(warning["code"] == "quote_source_cooling_down" for warning in snapshot["warnings"]))

    def test_prewarm_snapshots_populates_cache_without_ai_usage(self) -> None:
        stock_service = MagicMock()
        stock_service.get_realtime_quote.side_effect = lambda code: _quote(code, source="unit_quote")
        stock_service.get_history_data.side_effect = lambda code, **_kwargs: _history(code, source="unit_history")
        service = BasicQueryService(
            stock_service=stock_service,
            cache=MarketDataCache(default_ttl_seconds=60),
            source_health=MarketSourceHealthRegistry(),
        )

        prewarm = service.prewarm_snapshots(["AAPL", "BTC-USD"])

        self.assertEqual(prewarm["requested"], 2)
        self.assertEqual(prewarm["warmed"], 2)
        self.assertFalse(prewarm["ai_used"])
        stock_service.get_realtime_quote.reset_mock()
        stock_service.get_history_data.reset_mock()

        snapshot = service.get_snapshot("AAPL")

        self.assertFalse(snapshot["ai_used"])
        self.assertEqual(snapshot["diagnostics"]["cache"]["quote"], "hit")
        self.assertEqual(snapshot["diagnostics"]["cache"]["history"], "hit")
        stock_service.get_realtime_quote.assert_not_called()
        stock_service.get_history_data.assert_not_called()

    def test_prewarm_endpoint_returns_local_no_ai_summary(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "v9-prewarm.sqlite"
            static_dir = Path(temp_dir) / "static"
            static_dir.mkdir()
            (static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
            DatabaseManager.reset_instance()
            Config.reset_instance()
            with patch.dict(
                os.environ,
                {
                    "DATABASE_PATH": str(db_path),
                    "ADMIN_AUTH_ENABLED": "true",
                    "PLATFORM_USER_AUTH_ENABLED": "true",
                },
                clear=False,
            ):
                with patch("src.services.stock_service.StockService.get_realtime_quote", side_effect=lambda code: _quote(code)), \
                     patch("src.services.stock_service.StockService.get_history_data", side_effect=lambda code, **_kwargs: _history(code)):
                    client = TestClient(create_app(static_dir=static_dir))
                    register = client.post(
                        "/api/v1/platform/register",
                        json={"email": "v9-prewarm@example.com", "password": "password123"},
                    )
                    self.assertEqual(register.status_code, 200)
                    response = client.post("/api/v1/stocks/prewarm", json={"symbols": ["AAPL", "BTC-USD"]})
                    client.close()

            DatabaseManager.reset_instance()
            Config.reset_instance()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["requested"], 2)
        self.assertEqual(body["warmed"], 2)
        self.assertFalse(body["ai_used"])
        self.assertIn("AAPL", body["symbols"])

    def test_v9_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_market_source_health_v9.py"

        self.assertTrue(verifier.exists(), "V9 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_market_source_health_v9"))

        from scripts.verify_platform_local_market_source_health_v9 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_MARKET_SOURCE_HEALTH_V9_OK")

    def test_v9_evaluator_requires_source_health_diagnostics(self) -> None:
        from scripts.verify_platform_local_market_source_health_v9 import evaluate_snapshot_source_health

        missing = evaluate_snapshot_source_health(
            {
                "AAPL": {
                    "status_code": 200,
                    "diagnostics": {
                        "elapsed_ms": 10,
                        "fallback": {"quote": "live", "history": "live"},
                    },
                }
            }
        )
        valid = evaluate_snapshot_source_health(
            {
                "AAPL": {
                    "status_code": 200,
                    "diagnostics": {
                        "elapsed_ms": 10,
                        "fallback": {"quote": "live", "history": "live"},
                        "source_health": {
                            "quote": {"status": "ok", "source": "unit_quote"},
                            "history": {"status": "ok", "source": "unit_history"},
                        },
                    },
                }
            }
        )

        self.assertIn("AAPL", missing)
        self.assertEqual(valid, [])


if __name__ == "__main__":
    unittest.main()
