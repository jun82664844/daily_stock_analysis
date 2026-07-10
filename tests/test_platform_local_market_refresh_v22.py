# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache
from src.services.market_source_health import MarketSourceHealthRegistry
from src.storage import DatabaseManager
from scripts.verify_platform_local_market_refresh_v22 import (
    evaluate_market_refresh_summary,
    run_local_market_refresh_v22_checks,
)


def _history_rows(count: int = 24) -> list[dict]:
    return [
        {
            "date": f"2026-06-{day:02d}",
            "close": 100.0 + day,
            "volume": 1000 + day,
        }
        for day in range(1, count + 1)
    ]


def _quote(code: str, *, price: float, source: str) -> dict:
    return {
        "stock_code": code,
        "stock_name": code,
        "current_price": price,
        "change_percent": 1.0,
        "volume": 12345,
        "amount": price * 12345,
        "source": source,
        "update_time": "2026-07-03T09:30:00",
    }


class PlatformLocalMarketRefreshV22TestCase(unittest.TestCase):
    def test_force_refresh_bypasses_snapshot_cache_and_marks_no_ai_diagnostics(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=60)
        cache.set("quote:AAPL", _quote("AAPL", price=100.0, source="cached_quote"), source="cached_quote")
        cache.set(
            "history:AAPL:daily:30",
            {"stock_code": "AAPL", "stock_name": "AAPL", "source": "cached_history", "data": _history_rows()},
            source="cached_history",
        )
        stock_service = MagicMock()
        stock_service.get_realtime_quote.return_value = _quote("AAPL", price=210.0, source="live_quote")
        stock_service.get_history_data.return_value = {
            "stock_code": "AAPL",
            "stock_name": "AAPL",
            "source": "live_history",
            "data": _history_rows(),
        }

        snapshot = BasicQueryService(
            stock_service=stock_service,
            cache=cache,
            source_health=MarketSourceHealthRegistry(),
        ).get_snapshot(
            "AAPL",
            force_refresh=True,
        )

        self.assertEqual(snapshot["quote"]["current_price"], 210.0)
        self.assertEqual(snapshot["diagnostics"]["cache"]["quote"], "refresh")
        self.assertEqual(snapshot["diagnostics"]["cache"]["history"], "refresh")
        self.assertEqual(snapshot["diagnostics"]["freshness"]["quote"], "fresh")
        self.assertEqual(snapshot["diagnostics"]["refresh"]["mode"], "force_refresh")
        self.assertEqual(snapshot["diagnostics"]["refresh"]["requested"], True)
        self.assertFalse(snapshot["ai_used"])
        self.assertEqual(
            [call.args for call in stock_service.get_realtime_quote.call_args_list].count(("AAPL",)),
            1,
        )
        stock_service.get_history_data.assert_called_once_with("AAPL", period="daily", days=30)


class PlatformLocalMarketRefreshEndpointV22TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "market-refresh-v22.sqlite"
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(self.db_path),
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_USER_AUTH_ENABLED": "true",
            },
            clear=False,
        )
        self.env_patch.start()
        self.cache_patch = patch(
            "src.services.basic_query_service.default_persistent_market_data_cache",
            MarketDataCache(default_ttl_seconds=60),
        )
        self.cache_patch.start()
        self.health_patch = patch(
            "src.services.basic_query_service.default_market_source_health",
            MarketSourceHealthRegistry(),
        )
        self.health_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.health_patch.stop()
        self.cache_patch.stop()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_snapshot_endpoint_refresh_true_bypasses_cached_snapshot_without_ai(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "market-refresh-v22@example.com", "password": "password123"},
        )
        self.assertEqual(register.status_code, 200)
        stock_service = MagicMock()
        aapl_quote_calls = 0

        def quote_for_code(code: str) -> dict:
            nonlocal aapl_quote_calls
            if code == "AAPL":
                aapl_quote_calls += 1
                if aapl_quote_calls == 1:
                    return _quote(code, price=100.0, source="first_live")
                return _quote(code, price=210.0, source="refresh_live")
            return _quote(code, price=150.0, source="reference_live")

        stock_service.get_realtime_quote.side_effect = quote_for_code
        stock_service.get_history_data.side_effect = [
            {"stock_code": "AAPL", "stock_name": "AAPL", "source": "first_history", "data": _history_rows()},
            {"stock_code": "AAPL", "stock_name": "AAPL", "source": "refresh_history", "data": _history_rows()},
        ]

        with patch("src.services.basic_query_service.StockService", return_value=stock_service):
            cached = self.client.get("/api/v1/stocks/AAPL/snapshot")
            refreshed = self.client.get("/api/v1/stocks/AAPL/snapshot?refresh=true")

        self.assertEqual(cached.status_code, 200)
        self.assertEqual(refreshed.status_code, 200)
        cached_body = cached.json()
        refreshed_body = refreshed.json()
        self.assertEqual(cached_body["quote"]["current_price"], 100.0)
        self.assertEqual(cached_body["diagnostics"]["refresh"]["mode"], "cache_first")
        self.assertEqual(refreshed_body["quote"]["current_price"], 210.0)
        self.assertEqual(refreshed_body["diagnostics"]["cache"]["quote"], "refresh")
        self.assertEqual(refreshed_body["diagnostics"]["refresh"]["mode"], "force_refresh")
        self.assertTrue(refreshed_body["diagnostics"]["refresh"]["requested"])
        self.assertFalse(refreshed_body["ai_used"])


class PlatformLocalMarketRefreshVerifierV22TestCase(unittest.TestCase):
    def test_current_source_shape_passes_v22_static_check(self) -> None:
        from scripts.verify_platform_local_market_refresh_v22 import _run_source_shape_check

        result = _run_source_shape_check(Path(__file__).resolve().parents[1])

        self.assertEqual(result.status, "passed", result.error)

    def test_evaluate_market_refresh_summary_accepts_complete_shape(self) -> None:
        summary = {
            "service": {
                "accepts_force_refresh": True,
                "bypasses_cache": True,
                "refresh_mode": "force_refresh",
                "ai_used": False,
            },
            "endpoint": {
                "accepts_refresh_query": True,
                "passes_force_refresh": True,
            },
            "frontend": {
                "api_uses_refresh_query": True,
                "refresh_button_visible": True,
                "refresh_diagnostics_visible": True,
                "ai_submission_guard": True,
            },
        }

        self.assertEqual(evaluate_market_refresh_summary(summary), [])

    def test_evaluate_market_refresh_summary_rejects_missing_refresh_controls(self) -> None:
        summary = {
            "service": {
                "accepts_force_refresh": True,
                "bypasses_cache": False,
                "refresh_mode": "cache_first",
                "ai_used": False,
            },
            "endpoint": {
                "accepts_refresh_query": False,
                "passes_force_refresh": True,
            },
            "frontend": {
                "api_uses_refresh_query": True,
                "refresh_button_visible": False,
                "refresh_diagnostics_visible": False,
                "ai_submission_guard": True,
            },
        }

        problems = evaluate_market_refresh_summary(summary)

        self.assertIn("service:does_not_bypass_cache", problems)
        self.assertIn("service:refresh_mode_not_force", problems)
        self.assertIn("endpoint:refresh_query_missing", problems)
        self.assertIn("frontend:refresh_button_missing", problems)
        self.assertIn("frontend:refresh_diagnostics_missing", problems)

    def test_required_files_check_reports_missing_v22_plan(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_local_market_refresh_v22_checks(
                project_root=Path(temp_dir),
                run_subprocess=False,
                run_live=False,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v22_required_files_present"].status, "failed")
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v22-market-refresh.md",
            by_id["v22_required_files_present"].metadata["missing_files"],
        )


if __name__ == "__main__":
    unittest.main()
